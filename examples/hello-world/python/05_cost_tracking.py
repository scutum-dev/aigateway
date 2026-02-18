"""
Example 5: Cost Tracking & Reporting

Shows how FinOps teams query spending data through the Admin API.
The AI Control Plane tracks cost for every request automatically via LiteLLM.
"""

import httpx

ADMIN_API = "http://localhost:8086"
MASTER_KEY = "$LITELLM_KEY"

# Authenticate
resp = httpx.post(f"{ADMIN_API}/auth/login", json={"api_key": MASTER_KEY})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}


def print_section(title: str):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}\n")


# --------------------------------------------------------------------------
# 1. Summary Stats (today / this week / this month)
# --------------------------------------------------------------------------
print_section("Spend Summary")

summary = httpx.get(f"{ADMIN_API}/api/v1/reports/summary", headers=headers).json()
print(
    f"  Today:       ${summary.get('today', {}).get('cost', 0):.4f}  ({summary.get('today', {}).get('requests', 0)} requests)"
)
print(
    f"  This Week:   ${summary.get('this_week', {}).get('cost', 0):.4f}  ({summary.get('this_week', {}).get('requests', 0)} requests)"
)
print(
    f"  This Month:  ${summary.get('this_month', {}).get('cost', 0):.4f}  ({summary.get('this_month', {}).get('requests', 0)} requests)"
)

top = summary.get("top_models", [])
if top:
    print("\n  Top models this month:")
    for m in top:
        print(f"    {m.get('model', 'unknown'):<30} ${m.get('cost', 0):>10.4f}")


# --------------------------------------------------------------------------
# 2. Cost Report — breakdown by model
# --------------------------------------------------------------------------
print_section("Spend by Model (this month)")

report = httpx.get(
    f"{ADMIN_API}/api/v1/reports/cost",
    headers=headers,
    params={"period": "monthly"},
).json()

by_model = report.get("breakdown_by_model", [])
if by_model:
    for entry in by_model[:10]:
        model = entry.get("value", "unknown")
        spend = entry.get("total_cost", 0) or 0
        requests = entry.get("request_count", 0) or 0
        print(f"  {model:<30} ${spend:>10.4f}  ({requests} requests)")
else:
    print("  No spend data yet. Run examples 1-4 first to generate usage.")


# --------------------------------------------------------------------------
# 3. Cost Report — breakdown by team
# --------------------------------------------------------------------------
print_section("Spend by Team (this month)")

by_team = report.get("breakdown_by_team", [])
if by_team:
    for entry in by_team[:10]:
        team = entry.get("value", "unknown")
        spend = entry.get("total_cost", 0) or 0
        print(f"  {team:<30} ${spend:>10.4f}")
else:
    print("  No team spend data yet. Run example 04 first.")


# --------------------------------------------------------------------------
# 4. Daily Spend Trend (last 7 days)
# --------------------------------------------------------------------------
print_section("Daily Spend Trend (last 7 days)")

trend = httpx.get(
    f"{ADMIN_API}/api/v1/reports/trend",
    headers=headers,
    params={"days": 7},
).json()

data_points = trend.get("data_points", [])
if data_points:
    for day in data_points:
        dt = day.get("date", "unknown")
        spend = day.get("cost", 0) or 0
        bar = "#" * int(spend * 100)  # Simple bar chart
        print(f"  {dt}  ${spend:>8.4f}  {bar}")
    print(f"\n  Trend: {trend.get('trend_direction', 'N/A')} ({trend.get('percent_change', 0):+.1f}%)")
else:
    print("  No daily data yet.")


# --------------------------------------------------------------------------
# 5. Chargeback Report
# --------------------------------------------------------------------------
print_section("Chargeback / Cost Allocation")

rules = httpx.get(f"{ADMIN_API}/api/v1/cost-allocation/rules", headers=headers).json()

if isinstance(rules, list) and rules:
    for rule in rules:
        print(f"  {rule.get('name')}: {rule.get('allocation_target')} ({rule.get('allocation_percent')}%)")
else:
    print("  No allocation rules configured.")
    print("  Create them in the Admin UI: http://localhost:5173/chargeback")


# --------------------------------------------------------------------------
# 6. SLA Health
# --------------------------------------------------------------------------
print_section("Provider SLA Health")

try:
    health = httpx.get(f"{ADMIN_API}/api/v1/sla/health", headers=headers).json()
    if isinstance(health, list) and health:
        for h in health[:5]:
            provider = h.get("provider", "unknown")
            status = h.get("status", "unknown")
            p95 = h.get("p95_latency_ms", "N/A")
            print(f"  {provider:<20} Status: {status:<10} P95: {p95}ms")
    else:
        print("  No health metrics yet. Metrics are collected every 5 minutes.")
except Exception:
    print("  SLA monitoring endpoint not available.")


print(f"\n{'=' * 50}")
print("  Full dashboard: http://localhost:5173")
print(f"{'=' * 50}\n")
