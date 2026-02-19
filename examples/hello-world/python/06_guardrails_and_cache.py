"""
Example 6: Guardrails & Semantic Cache

Demonstrates two enterprise features:
  1. Guardrails — content filtering before/after LLM calls
  2. Semantic Cache — cache similar queries to save cost
"""

import os
import time

import httpx
from openai import OpenAI

ADMIN_API = "http://localhost:8086"
MASTER_KEY = os.getenv("LITELLM_KEY") or os.getenv("LITELLM_MASTER_KEY", "")


def print_section(title: str):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}\n")


# Authenticate
resp = httpx.post(f"{ADMIN_API}/auth/login", json={"api_key": MASTER_KEY})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --------------------------------------------------------------------------
# Part 1: Guardrails
# --------------------------------------------------------------------------
print_section("Guardrails Configuration")

# List existing guardrails
guardrails = httpx.get(f"{ADMIN_API}/api/v1/guardrails", headers=headers).json()
print(f"  Active guardrails: {len(guardrails) if isinstance(guardrails, list) else 0}")

if isinstance(guardrails, list):
    for g in guardrails[:5]:
        name = g.get("guardrail_name", "unnamed")
        mode = g.get("mode", "unknown")
        print(f"    - {name} ({mode})")

# Create a DLP content detector
print("\n  Creating PII detector...")
detector = httpx.post(
    f"{ADMIN_API}/api/v1/detectors",
    headers=headers,
    json={
        "name": "pii-detector-demo",
        "description": "Detects SSNs, credit cards, and emails",
        "detector_type": "regex",
        "config": {
            "patterns": [
                {"name": "SSN", "pattern": r"\d{3}-\d{2}-\d{4}", "action": "block"},
                {"name": "Credit Card", "pattern": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "action": "block"},
                {"name": "Email", "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "action": "redact"},
            ]
        },
    },
).json()
print(f"  Created detector: {detector.get('name', detector)}")


# --------------------------------------------------------------------------
# Part 2: Semantic Cache
# --------------------------------------------------------------------------
print_section("Semantic Cache")

# Check cache stats
cache_stats = httpx.get(f"{ADMIN_API}/api/v1/cache/stats", headers=headers).json()
print(f"  Cache entries:  {cache_stats.get('total_entries', 0)}")
print(f"  Hit rate:       {cache_stats.get('hit_rate', 0):.1f}%")
print(f"  Total hits:     {cache_stats.get('total_hits', 0)}")
print(f"  Cost saved:     ${cache_stats.get('cost_saved', 0):.4f}")

# Demonstrate cache behavior: same question twice
print("\n  Sending same question twice to show caching...")

client = OpenAI(base_url="http://localhost:4000", api_key=MASTER_KEY)

question = "What are the three laws of thermodynamics?"

# First request (cache miss)
start = time.time()
r1 = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": question}],
    max_tokens=150,
)
t1 = int((time.time() - start) * 1000)

# Second request (potential cache hit if semantic cache is enabled)
start = time.time()
r2 = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": question}],
    max_tokens=150,
)
t2 = int((time.time() - start) * 1000)

print(f"\n  Request 1: {t1}ms (tokens: {r1.usage.total_tokens})")
print(f"  Request 2: {t2}ms (tokens: {r2.usage.total_tokens})")

if t2 < t1 * 0.5:
    print(f"\n  Cache hit! Second request was {t1 - t2}ms faster.")
else:
    print("\n  Semantic cache may not be enabled or threshold wasn't met.")
    print("  Enable it in Admin UI: http://localhost:5173 → Settings")


# --------------------------------------------------------------------------
# Part 3: Audit Trail
# --------------------------------------------------------------------------
print_section("Audit Trail")

audit = httpx.get(
    f"{ADMIN_API}/api/v1/audit-logs",
    headers=headers,
    params={"limit": 5},
).json()

if isinstance(audit, list) and audit:
    print("  Recent audit events:")
    for entry in audit:
        ts = entry.get("timestamp", "")[:19]
        action = entry.get("action", "unknown")
        resource = entry.get("resource_type", "unknown")
        actor = entry.get("actor_email", entry.get("actor_id", "unknown"))
        print(f"    {ts}  {action:<10} {resource:<15} by {actor}")
else:
    print("  No audit logs yet. Every Admin API mutation is logged.")

print("\n  Full audit log: http://localhost:5173/audit-log\n")
