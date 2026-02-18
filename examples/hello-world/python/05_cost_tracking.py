"""
Example 5: Cost Tracking & Reporting

Shows how FinOps teams query spending data through the Admin API.
The AI Control Plane tracks cost for every request automatically via LiteLLM.
"""

import httpx
import json
from datetime import datetime, timedelta

ADMIN_API = "http://localhost:8086"
MASTER_KEY = "$LITELLM_KEY"

# Authenticate
resp = httpx.post(f"{ADMIN_API}/auth/login", json={"api_key": MASTER_KEY})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}


def print_section(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}\n")


# --------------------------------------------------------------------------
# 1. Dashboard Summary
# --------------------------------------------------------------------------
print_section("Dashboard Summary")

dashboard = httpx.get(f"{ADMIN_API}/api/v1/dashboard", headers=headers).json()
print(f"  Total Models:    {dashboard.get('total_models', 'N/A')}")
print(f"  Active Teams:    {dashboard.get('total_teams', 'N/A')}")
print(f"  Active Keys:     {dashboard.get('total_keys', 'N/A')}")
print(f"  Total Spend:     ${dashboard.get('total_spend', 0):.4f}")
print(f"  Total Requests:  {dashboard.get('total_requests', 0)}")


# --------------------------------------------------------------------------
# 2. Spend by Model
# --------------------------------------------------------------------------
print_section("Spend by Model")

reports = httpx.get(
    f"{ADMIN_API}/api/v1/reports/spend-by-model",
    headers=headers,
    params={"days": 30},
).json()

if isinstance(reports, list) and reports:
    for entry in reports[:10]:
        model = entry.get("model", "unknown")
        spend = entry.get("total_spend", 0) or 0
        requests = entry.get("total_requests", 0) or 0
        print(f"  {model:<30} ${spend:>10.4f}  ({requests} requests)")
else:
    print("  No spend data yet. Run examples 1-4 first to generate usage.")


# --------------------------------------------------------------------------
# 3. Spend by Team
# --------------------------------------------------------------------------
print_section("Spend by Team")

team_spend = httpx.get(
    f"{ADMIN_API}/api/v1/reports/spend-by-team",
    headers=headers,
    params={"days": 30},
).json()

if isinstance(team_spend, list) and team_spend:
    for entry in team_spend[:10]:
        team = entry.get("team_alias", entry.get("team_id", "unknown"))
        spend = entry.get("total_spend", 0) or 0
        print(f"  {team:<30} ${spend:>10.4f}")
else:
    print("  No team spend data yet. Run example 04 first.")


# --------------------------------------------------------------------------
# 4. Daily Spend Trend
# --------------------------------------------------------------------------
print_section("Daily Spend Trend (last 7 days)")

daily = httpx.get(
    f"{ADMIN_API}/api/v1/reports/daily-spend",
    headers=headers,
    params={"days": 7},
).json()

if isinstance(daily, list) and daily:
    for day in daily:
        date = day.get("date", "unknown")
        spend = day.get("total_spend", 0) or 0
        bar = "#" * int(spend * 100)  # Simple bar chart
        print(f"  {date}  ${spend:>8.4f}  {bar}")
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


print(f"\n{'='*50}")
print("  Full dashboard: http://localhost:5173")
print(f"{'='*50}\n")
