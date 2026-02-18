"""
Example 4: Enterprise Setup via Admin API

This shows what a platform admin does on Day 1:
  1. Create an organization
  2. Create teams under it
  3. Generate team-scoped API keys with budgets
  4. Set up guardrails
  5. Use the team key to make a request

This is the "control plane" — managing WHO can use WHAT and HOW MUCH.
"""

import httpx
from openai import OpenAI

ADMIN_API = "http://localhost:8086"
LITELLM = "http://localhost:4000"
MASTER_KEY = "$LITELLM_KEY"


def admin_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def litellm_headers() -> dict:
    return {"Authorization": f"Bearer {MASTER_KEY}", "Content-Type": "application/json"}


def step(n: int, title: str):
    print(f"\n{'=' * 60}")
    print(f"  Step {n}: {title}")
    print(f"{'=' * 60}\n")


# --------------------------------------------------------------------------
# Authenticate with the Admin API
# --------------------------------------------------------------------------
step(0, "Authenticate")

resp = httpx.post(f"{ADMIN_API}/auth/login", json={"api_key": MASTER_KEY})
token = resp.json()["access_token"]
print(f"Got admin token: {token[:20]}...")


# --------------------------------------------------------------------------
# Step 1: Create an Organization
# --------------------------------------------------------------------------
step(1, "Create Organization")

org = httpx.post(
    f"{ADMIN_API}/api/v1/organizations",
    headers=admin_headers(token),
    json={
        "name": "Acme Corp",
        "slug": "acme-corp",
        "description": "Example enterprise customer",
        "max_budget": 1000.00,
        "allowed_models": ["gpt-4o-mini", "gpt-4o", "claude-haiku-4.5", "claude-sonnet-4.5"],
    },
).json()
print(f"Created org: {org['name']} (id: {org['id']})")


# --------------------------------------------------------------------------
# Step 2: Create Business Units
# --------------------------------------------------------------------------
step(2, "Create Business Units")

for bu_name, bu_slug in [("Engineering", "engineering"), ("Data Science", "data-science")]:
    bu = httpx.post(
        f"{ADMIN_API}/api/v1/organizations/{org['id']}/business-units",
        headers=admin_headers(token),
        json={
            "name": bu_name,
            "slug": bu_slug,
            "max_budget": 500.00,
        },
    ).json()
    print(f"  Created BU: {bu['name']} (id: {bu['id']})")


# --------------------------------------------------------------------------
# Step 3: Create Teams via LiteLLM (the data plane)
# --------------------------------------------------------------------------
step(3, "Create Teams with Budgets")

teams = {}
for team_name, budget in [("acme-engineering", 200.0), ("acme-data-science", 300.0)]:
    team = httpx.post(
        f"{LITELLM}/team/new",
        headers=litellm_headers(),
        json={
            "team_alias": team_name,
            "max_budget": budget,
            "budget_duration": "30d",
            "models": ["gpt-4o-mini", "gpt-4o", "claude-haiku-4.5", "claude-sonnet-4.5"],
        },
    ).json()
    teams[team_name] = team
    print(f"  Created team: {team_name} (budget: ${budget}/30d)")
    print(f"    team_id: {team.get('team_id', 'N/A')}")


# --------------------------------------------------------------------------
# Step 4: Generate API Keys for Each Team
# --------------------------------------------------------------------------
step(4, "Generate Team API Keys")

keys = {}
for team_name, team_data in teams.items():
    key = httpx.post(
        f"{LITELLM}/key/generate",
        headers=litellm_headers(),
        json={
            "team_id": team_data.get("team_id"),
            "key_alias": f"{team_name}-key",
            "max_budget": 50.0,
            "budget_duration": "30d",
            "models": ["gpt-4o-mini", "gpt-4o", "claude-haiku-4.5"],
            "metadata": {"team": team_name, "env": "development"},
        },
    ).json()
    keys[team_name] = key.get("key")
    print(f"  {team_name}: {key.get('key', 'N/A')[:30]}...")


# --------------------------------------------------------------------------
# Step 5: Use a Team Key to Make a Request
# --------------------------------------------------------------------------
step(5, "Developer Makes a Request with Team Key")

team_key = keys.get("acme-engineering")
if team_key:
    client = OpenAI(base_url="http://localhost:4000", api_key=team_key)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What is 2+2?"}],
        max_tokens=50,
    )

    print(f"  Model: {response.model}")
    print(f"  Response: {response.choices[0].message.content}")
    print(f"  Tokens used: {response.usage.total_tokens}")
    print("\n  This request was tracked against the acme-engineering team budget.")
else:
    print("  Skipped — no team key generated (check LiteLLM is running)")


# --------------------------------------------------------------------------
# Step 6: Set Up a Guardrail
# --------------------------------------------------------------------------
step(6, "Create Guardrail (Block PII)")

guardrail = httpx.post(
    f"{ADMIN_API}/api/v1/guardrails",
    headers=admin_headers(token),
    json={
        "name": "block-pii-acme",
        "description": "Block PII in prompts (SSN, credit cards, emails)",
        "enable_pii_detection": True,
        "pii_action": "block",
        "pii_entities": ["US_SSN", "CREDIT_CARD", "EMAIL_ADDRESS", "PERSON"],
        "enable_prompt_injection": True,
        "prompt_injection_threshold": 0.90,
    },
).json()
print(f"  Created guardrail: {guardrail.get('name', guardrail)}")


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
print(f"\n{'=' * 60}")
print("  Setup Complete!")
print(f"{'=' * 60}")
print("""
  Organization: Acme Corp
  Teams:        acme-engineering, acme-data-science
  API Keys:     1 per team, budget-capped
  Guardrails:   PII blocking enabled

  Developers now use their team key with the standard OpenAI SDK.
  All usage is tracked, budget-controlled, and audited.

  View the dashboard: http://localhost:5173
""")
