"""
Example 7: Routing Policies & A/B Testing

Demonstrates two intelligence features:
  1. Routing Policies — fallback chains, model groups, and routing strategies
  2. A/B Testing — compare two models with traffic splitting
"""

import os

import httpx

ADMIN_API = "http://localhost:8086"
LITELLM = "http://localhost:4000"
MASTER_KEY = os.getenv("LITELLM_KEY") or os.getenv("LITELLM_MASTER_KEY", "")

# Authenticate
resp = httpx.post(f"{ADMIN_API}/auth/login", json={"api_key": MASTER_KEY})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


# --------------------------------------------------------------------------
# Part 1: Routing Policies
# --------------------------------------------------------------------------
print_section("Routing Policies")

# 1a. Check current LiteLLM router status
status = httpx.get(f"{ADMIN_API}/api/v1/routing-policies/litellm-status", headers=headers).json()
print(f"  Current routing strategy: {status.get('routing_strategy', 'N/A')}")
print(f"  Active fallbacks:         {len(status.get('fallbacks', []))}")
print(f"  Model group aliases:      {len(status.get('model_group_aliases', {}))}")
print(f"  Total models:             {status.get('num_models', 0)}")

# 1b. Create a fallback chain: gpt-4o → claude-sonnet-4.5 → gpt-4o-mini
print("\n  Creating fallback chain: gpt-4o → claude-sonnet-4.5 → gpt-4o-mini")
fallback = httpx.post(
    f"{ADMIN_API}/api/v1/routing-policies",
    headers=headers,
    json={
        "name": "gpt4o-fallback-demo",
        "description": "Falls back through claude-sonnet-4.5 then gpt-4o-mini",
        "policy_type": "fallback",
        "config": {
            "model": "gpt-4o",
            "fallbacks": ["claude-sonnet-4.5", "gpt-4o-mini"],
        },
        "priority": 10,
    },
).json()
print(f"  Created: {fallback.get('name', fallback)} (id: {fallback.get('id', 'N/A')[:8]}...)")

# 1c. Create a model group alias: "fast" → routes to mini models
print("\n  Creating model group: 'fast' → gpt-4o-mini + claude-haiku-4.5")
group = httpx.post(
    f"{ADMIN_API}/api/v1/routing-policies",
    headers=headers,
    json={
        "name": "fast-models-demo",
        "description": "Alias 'fast' routes to cheap, fast models",
        "policy_type": "model_group",
        "config": {
            "alias": "fast",
            "models": ["gpt-4o-mini", "claude-haiku-4.5"],
        },
    },
).json()
print(f"  Created: {group.get('name', group)} (id: {group.get('id', 'N/A')[:8]}...)")

# 1d. Set routing strategy to cost-based
print("\n  Setting routing strategy: cost-based-routing")
strategy = httpx.post(
    f"{ADMIN_API}/api/v1/routing-policies",
    headers=headers,
    json={
        "name": "cost-routing-demo",
        "description": "Route to cheapest available model in each group",
        "policy_type": "routing_strategy",
        "config": {
            "strategy": "cost-based-routing",
        },
    },
).json()
print(f"  Created: {strategy.get('name', strategy)} (id: {strategy.get('id', 'N/A')[:8]}...)")

# 1e. Sync all policies to LiteLLM and verify
print("\n  Syncing all policies to LiteLLM...")
sync = httpx.post(f"{ADMIN_API}/api/v1/routing-policies/sync", headers=headers).json()
print(f"  Sync result: {sync.get('status')} ({sync.get('synced', 0)} types synced)")

# Check updated status
status = httpx.get(f"{ADMIN_API}/api/v1/routing-policies/litellm-status", headers=headers).json()
print(f"\n  Updated routing strategy: {status.get('routing_strategy', 'N/A')}")
print(f"  Active fallbacks:         {len(status.get('fallbacks', []))}")
print(f"  Model group aliases:      {list(status.get('model_group_aliases', {}).keys())}")

# 1f. List all policies
policies = httpx.get(f"{ADMIN_API}/api/v1/routing-policies", headers=headers).json()
print(f"\n  Total policies configured: {len(policies)}")
for p in policies:
    synced = "synced" if p.get("synced_at") else "not synced"
    print(f"    - {p['name']} ({p['policy_type']}, {synced})")


# --------------------------------------------------------------------------
# Part 2: A/B Testing
# --------------------------------------------------------------------------
print_section("A/B Testing")

# 2a. Create an A/B test: gpt-4o-mini vs claude-haiku-4.5
print("  Creating A/B test: gpt-4o-mini (base) vs claude-haiku-4.5 (variant)")
ab_test = httpx.post(
    f"{ADMIN_API}/api/v1/ab-tests",
    headers=headers,
    json={
        "name": "mini-vs-haiku-demo",
        "base_model": "gpt-4o-mini",
        "variant_model": "claude-haiku-4.5",
        "traffic_split_percent": 30,
        "success_metric": "cost_efficiency",
        "auto_promote": False,
        "auto_rollback": True,
    },
).json()
test_id = ab_test.get("id", "")
print(f"  Created: {ab_test.get('name')} (status: {ab_test.get('status')})")
print(f"  Traffic split: {ab_test.get('traffic_split_percent')}% to variant")

# 2b. Start the test (registers variant in LiteLLM)
if test_id:
    print("\n  Starting A/B test...")
    started = httpx.post(f"{ADMIN_API}/api/v1/ab-tests/{test_id}/start", headers=headers).json()
    print(f"  Status: {started.get('status')}")
    print(f"  Started at: {started.get('started_at', 'N/A')}")

    # 2c. Generate some traffic to both models
    print("\n  Generating traffic (5 requests)...")
    from openai import OpenAI

    client = OpenAI(base_url=LITELLM, api_key=MASTER_KEY)
    for i in range(5):
        try:
            r = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Say 'test {i}' in one word."}],
                max_tokens=10,
            )
            print(f"    Request {i + 1}: {r.model} ({r.usage.total_tokens} tokens)")
        except Exception as e:
            print(f"    Request {i + 1}: error — {e}")

    # 2d. Collect metrics snapshot
    print("\n  Collecting metrics...")
    snapshot = httpx.post(
        f"{ADMIN_API}/api/v1/ab-tests/{test_id}/collect-metrics",
        headers=headers,
    ).json()
    base_m = snapshot.get("base_metrics", {})
    var_m = snapshot.get("variant_metrics", {})
    print(f"  Base ({ab_test['base_model']}):")
    print(f"    Requests: {base_m.get('requests', 0)}, Avg cost: ${base_m.get('avg_cost', 0):.6f}")
    print(f"  Variant ({ab_test['variant_model']}):")
    print(f"    Requests: {var_m.get('requests', 0)}, Avg cost: ${var_m.get('avg_cost', 0):.6f}")
    print(f"  Recommendation: {snapshot.get('recommendation', 'N/A')}")

    # 2e. Stop the test
    print("\n  Stopping A/B test...")
    stopped = httpx.post(f"{ADMIN_API}/api/v1/ab-tests/{test_id}/stop", headers=headers).json()
    print(f"  Final status: {stopped.get('status')}")


# --------------------------------------------------------------------------
# Cleanup: remove demo policies
# --------------------------------------------------------------------------
print_section("Cleanup")

for p in policies:
    if p["name"].endswith("-demo"):
        httpx.delete(f"{ADMIN_API}/api/v1/routing-policies/{p['id']}", headers=headers)
        print(f"  Deleted policy: {p['name']}")

if test_id:
    httpx.delete(f"{ADMIN_API}/api/v1/ab-tests/{test_id}", headers=headers)
    print(f"  Deleted A/B test: {ab_test.get('name')}")

print("\n  Manage routing & tests in the Admin UI: http://localhost:5173/routing")
print("  A/B test dashboard: http://localhost:5173/ab-tests\n")
