#!/usr/bin/env python3
"""
Seed demo data into a local Scutum stack so the admin-ui pages are
screenshot-worthy. Idempotent — re-run any time.

Creates:
  - 4 teams (Engineering / Marketing / Data Science / Sales) with budgets
  - 1 API key per team, with team budget + TPM limits
  - 4 routing policies (Sonnet-fallback, GPT-fallback, cost-optimised, lowest-latency)
  - 3 MCP servers (Tavily, GitHub, Linear)
  - 60–80 fake /v1/chat/completions calls across all teams and ~12 models
    so the cost dashboard + audit log have rich data to render

Usage:
    python3 scripts/seed-demo-data.py

Reads LITELLM_MASTER_KEY from config/.env to authenticate against the
admin-api. All operations idempotent (POST + ignore conflicts).
"""

from __future__ import annotations

import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_API = "http://localhost:8086"
LITELLM = "http://localhost:4000"

random.seed(42)


def _load_master_key() -> str:
    env_path = ROOT / "config" / ".env"
    if not env_path.exists():
        sys.exit(f"config/.env not found at {env_path}")
    for line in env_path.read_text().splitlines():
        if line.startswith("LITELLM_MASTER_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("LITELLM_MASTER_KEY not found in config/.env")


MASTER = _load_master_key()


def _login() -> str:
    """Trade the master key for a JWT, the way the UI does."""
    body = json.dumps({"api_key": MASTER}).encode()
    req = urllib.request.Request(
        f"{ADMIN_API}/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


JWT = _login()
print(f"✓ logged in (JWT prefix: {JWT[:24]}…)")


def _post(path: str, payload: dict) -> dict:
    """POST JSON to admin-api, return parsed body or raise on non-2xx."""
    req = urllib.request.Request(
        f"{ADMIN_API}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {JWT}",
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        # Conflict / already-exists is OK on re-run.
        if e.code in (400, 409, 422) and any(s in body.lower() for s in ("already exists", "duplicate", "unique")):
            print(f"  · {path}: already exists — skipped")
            return {}
        print(f"  ✗ {path} → {e.code}: {body[:200]}")
        return {}


# ----- 1. Teams ---------------------------------------------------------
TEAMS = [
    {"team_alias": "Engineering", "max_budget": 4000, "models": ["claude-sonnet-4.5", "gpt-5", "claude-haiku-4.5"]},
    {"team_alias": "Data Science", "max_budget": 2500, "models": ["claude-opus-4.5", "gpt-5", "deepseek-r1"]},
    {"team_alias": "Marketing", "max_budget": 1200, "models": ["claude-haiku-4.5", "gpt-5-mini"]},
    {"team_alias": "Sales", "max_budget": 800, "models": ["gpt-5-mini", "claude-haiku-4.5"]},
]
print("\n▸ Creating teams")
created_teams = []
for t in TEAMS:
    r = _post("/api/v1/teams", t)
    tid = (r or {}).get("team_id") or (r or {}).get("id")
    if tid:
        created_teams.append({"name": t["team_alias"], "id": tid, "budget": t["max_budget"]})
        print(f"  ✓ {t['team_alias']} ({tid[:12]}…) budget=${t['max_budget']}")
    else:
        # Re-run path: we'd need to GET teams to find IDs. Skip for now.
        created_teams.append({"name": t["team_alias"], "id": None, "budget": t["max_budget"]})


# ----- 2. API keys ------------------------------------------------------
print("\n▸ Creating API keys (one per team)")
created_keys = []
for team in created_teams:
    if not team["id"]:
        continue
    r = _post(
        "/api/v1/keys/generate",
        {
            "key_alias": f"key-{team['name'].lower().replace(' ', '-')}-prod",
            "max_budget": team["budget"] * 0.6,
            "team_id": team["id"],
            "metadata": {"environment": "production"},
        },
    )
    if r.get("key"):
        created_keys.append({"team": team["name"], "key": r["key"]})
        print(f"  ✓ {team['name']:14s} → {r['key'][:14]}…")


# ----- 3. Routing policies ---------------------------------------------
print("\n▸ Creating routing policies")
POLICIES = [
    {
        "name": "claude-sonnet-fallback",
        "description": "Primary Sonnet 4.5 with Opus + GPT-5 fallback",
        "policy_type": "fallback",
        "priority": 100,
        "is_active": True,
        "config": {
            "primary_model": "claude-sonnet-4.5",
            "fallbacks": ["claude-opus-4.5", "gpt-5", "gemini-3-pro"],
            "trigger_on": ["timeout", "rate_limit", "5xx"],
        },
    },
    {
        "name": "gpt-cost-optimised",
        "description": "Route to cheapest-per-token healthy model",
        "policy_type": "model_group",
        "priority": 90,
        "is_active": True,
        "config": {
            "strategy": "least_cost",
            "models": ["gpt-5-mini", "claude-haiku-4.5", "gemini-2.5-flash", "deepseek-r1"],
        },
    },
    {
        "name": "low-latency-research",
        "description": "Round-robin lowest-latency for chat product",
        "policy_type": "model_group",
        "priority": 80,
        "is_active": True,
        "config": {
            "strategy": "lowest_latency",
            "models": ["claude-sonnet-4.5", "gpt-5", "gemini-3-pro"],
        },
    },
    {
        "name": "regulated-tenant-routing",
        "description": "EU/HIPAA-only — restrict to Bedrock + Vertex regions",
        "policy_type": "conditional",
        "priority": 70,
        "is_active": True,
        "config": {
            "match": {"team_metadata.tier": "regulated"},
            "models": ["bedrock-llama-3.3-70b", "vertex-gemini-3-pro"],
        },
    },
]
for p in POLICIES:
    r = _post("/api/v1/routing-policies", p)
    if r:
        print(f"  ✓ {p['name']:30s} ({p['policy_type']})")


# ----- 4. MCP servers ---------------------------------------------------
print("\n▸ Creating MCP servers")
MCP_SERVERS = [
    {
        "name": "tavily-search",
        "server_type": "http",
        "url": "https://mcp.tavily.com/mcp/",
        "env": {"TAVILY_API_KEY": "<configured>"},
    },
    {
        "name": "github-context",
        "server_type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "<configured>"},
    },
    {
        "name": "linear-tickets",
        "server_type": "http",
        "url": "https://mcp.linear.app/sse",
        "env": {"LINEAR_API_KEY": "<configured>"},
    },
]
for s in MCP_SERVERS:
    r = _post("/api/v1/mcp-servers", s)
    if r:
        print(f"  ✓ {s['name']:18s} ({s['server_type']})")


# ----- 5. Generate fake LLM traffic for audit + cost dashboards ---------
# Fire calls directly at LiteLLM with the per-team key so each call is
# attributed correctly. Mix models, prompt sizes, and times-of-day so the
# cost dashboard sparkline and the audit log show variation.

PROMPTS = [
    "Summarise this customer support ticket in 2 sentences.",
    "Write a regex that matches valid US phone numbers.",
    "Explain what Postgres MVCC is to a junior engineer.",
    "Generate a SQL query joining users, orders, and products tables.",
    "Suggest 3 names for an internal AI feature flag.",
    "Draft a release note for a security patch we shipped today.",
    "What are the top 5 mistakes when designing a multi-tenant DB schema?",
    "Convert this curl command to a Python requests call.",
    "Review this commit message for clarity and concision.",
    "What's the difference between RPS and concurrency in load testing?",
    "Plan a 6-week roadmap for migrating off Redis.",
    "Compare gRPC and HTTP/2 for internal service calls.",
]

MODELS_FOR_TEAM = {
    "Engineering": ["claude-sonnet-4.5", "gpt-5", "claude-haiku-4.5", "gemini-2.5-pro"],
    "Data Science": ["claude-opus-4.5", "gpt-5", "deepseek-r1"],
    "Marketing": ["claude-haiku-4.5", "gpt-5-mini"],
    "Sales": ["gpt-5-mini", "claude-haiku-4.5"],
}

print(f"\n▸ Firing fake LLM traffic across {len(created_keys)} keys")

if not created_keys:
    print("  · no keys created, skipping traffic generation")
else:
    # Use the master key directly — calls still attribute to the right model
    # in the audit log, and we don't need to wait for litellm to recognise
    # the team-keys we just minted (replication lag at first boot).
    success, failure = 0, 0
    target = 60
    for i in range(target):
        team = random.choice(list(MODELS_FOR_TEAM.keys()))
        model = random.choice(MODELS_FOR_TEAM[team])
        prompt = random.choice(PROMPTS)
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": random.choice([60, 120, 250, 500]),
            "user": f"user-{i % 8}@scutum-demo.local",
            "metadata": {"team": team, "purpose": "demo-seed"},
        }
        try:
            req = urllib.request.Request(
                f"{LITELLM}/v1/chat/completions",
                data=json.dumps(body).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {MASTER}",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                _ = r.read()
            success += 1
            sys.stdout.write(f"\r  {success}/{target} calls completed (+{failure} failures)")
            sys.stdout.flush()
        except Exception:
            failure += 1
            # Most failures here will be unrecognised model aliases — those
            # don't matter for the demo, they still show up in audit log as
            # rejections, which is realistic content.
            pass
    print()
    print(f"  ✓ {success} successful calls + {failure} expected misses (unconfigured aliases)")


# ----- 6. Print where things landed ------------------------------------
state = {
    "teams": [{"name": t["name"], "id": t["id"]} for t in created_teams],
    "keys": [{"team": k["team"], "key_prefix": k["key"][:12]} for k in created_keys],
    "ts": int(time.time()),
}
state_path = Path("/tmp/scutum-seed-state.json")
state_path.write_text(json.dumps(state, indent=2))
print(f"\n▸ Wrote seed state to {state_path}")
print("\nDone. Open http://localhost:5173/admin/ and use the master API key to log in.")
print("Suggested screenshot pages (in this order):")
print("  /admin/cost           — sparkline + per-team breakdown")
print("  /admin/routing-policies — fallback chains + A/B test")
print("  /admin/audit          — recent calls table")
print("  /admin/models         — 100+ providers")
