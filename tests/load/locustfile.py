"""Load tests for the AI Control Plane platform.

Three user classes simulate different traffic shapes:

- LiteLLMUser     — the customer hot path. /health, /v1/models, /key/info.
- AdminAPIUser    — operator traffic. JWT login, leads + SRE reads, audit.
- LandingUser     — public marketing surface. /health, demo availability.

Defaults are conservative so you can iterate locally without melting the box.
Override hosts via env vars. Authentication uses LITELLM_MASTER_KEY from
config/.env (read once at start).

Run examples
------------

# Mixed-workload smoke (30s, 30 users, 5 spawn/sec)
locust -f tests/load/locustfile.py --headless -u 30 -r 5 -t 30s \\
  --host http://localhost --html out.html

# Hammer just the LLM proxy
locust -f tests/load/locustfile.py LiteLLMUser --headless -u 100 -r 10 -t 1m \\
  --host http://localhost:4000

# Long sustained run with HTML report
locust -f tests/load/locustfile.py --headless -u 200 -r 10 -t 5m \\
  --html /tmp/load.html

Read tests/load/README.md for interpretation guidance.
"""

import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from locust import HttpUser, between, events, task

# ---------------------------------------------------------------------------
# Config — read once. Override via env or by editing config/.env.
# ---------------------------------------------------------------------------

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
ADMIN_API_URL = os.getenv("ADMIN_API_URL", "http://localhost:8086")
LANDING_URL = os.getenv("LANDING_URL", "http://localhost:9999")

# Pull master key from config/.env if not in environment.
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
if not LITELLM_MASTER_KEY:
    env_path = Path(__file__).resolve().parents[2] / "config" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("LITELLM_MASTER_KEY="):
                LITELLM_MASTER_KEY = line.split("=", 1)[1].strip()
                break


# ---------------------------------------------------------------------------
# Hot path: LiteLLM proxy
# ---------------------------------------------------------------------------


class LiteLLMUser(HttpUser):
    """Simulates a customer client hitting the LLM proxy.

    We deliberately avoid /v1/chat/completions in the default mix because real
    chat calls cost money and measure the upstream provider, not the platform.
    Uncomment the chat task to add it (you'll need provider keys configured).
    """

    host = LITELLM_URL
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        self.headers = {
            "Authorization": f"Bearer {LITELLM_MASTER_KEY}",
            "Content-Type": "application/json",
        }

    @task(1)
    def health(self) -> None:
        self.client.get("/health/liveliness", name="LiteLLM /health/liveliness")

    @task(8)
    def list_models(self) -> None:
        with self.client.get(
            "/v1/models",
            headers=self.headers,
            name="LiteLLM /v1/models",
            catch_response=True,
        ) as resp:
            if resp.status_code == 401:
                resp.failure("auth failed — check LITELLM_MASTER_KEY")
            elif resp.status_code >= 500:
                resp.failure(f"5xx: {resp.status_code}")

    @task(2)
    def model_info(self) -> None:
        self.client.get(
            "/model/info",
            headers=self.headers,
            name="LiteLLM /model/info",
        )

    # Uncomment if you want to exercise the actual chat path against a local
    # mock or self-hosted model. Keep weight low to avoid burning credits.
    # @task(0)
    # def chat_completion(self) -> None:
    #     self.client.post(
    #         "/v1/chat/completions",
    #         headers=self.headers,
    #         json={
    #             "model": "claude-sonnet-4-6",
    #             "messages": [{"role": "user", "content": "ping"}],
    #             "max_tokens": 8,
    #         },
    #         name="LiteLLM /v1/chat/completions",
    #     )


# ---------------------------------------------------------------------------
# Operator path: Admin API
# ---------------------------------------------------------------------------


class AdminAPIUser(HttpUser):
    """Simulates an operator browsing the admin UI.

    JWT-authenticated. Logs in once at user start, reuses the token. Hits
    the read-heavy endpoints the admin UI polls (leads, SRE incidents,
    settings, audit log).
    """

    host = ADMIN_API_URL
    wait_time = between(0.5, 2.0)
    token: Optional[str] = None

    def on_start(self) -> None:
        if not LITELLM_MASTER_KEY:
            return
        with self.client.post(
            "/auth/login",
            json={"api_key": LITELLM_MASTER_KEY},
            name="Admin /auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
            else:
                resp.failure(f"login failed: {resp.status_code}")

    @property
    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(2)
    def health(self) -> None:
        self.client.get("/health", name="Admin /health")

    @task(5)
    def list_leads(self) -> None:
        self.client.get("/api/v1/leads", headers=self.auth_headers, name="Admin /leads")

    @task(5)
    def list_incidents(self) -> None:
        self.client.get(
            "/api/v1/sre/incidents",
            headers=self.auth_headers,
            name="Admin /sre/incidents",
        )

    @task(3)
    def list_models(self) -> None:
        self.client.get("/api/v1/models", headers=self.auth_headers, name="Admin /models")

    @task(2)
    def reports_summary(self) -> None:
        self.client.get(
            "/api/v1/reports/summary",
            headers=self.auth_headers,
            name="Admin /reports/summary",
        )

    @task(1)
    def audit_log(self) -> None:
        self.client.get(
            "/api/v1/audit-logs?limit=50",
            headers=self.auth_headers,
            name="Admin /audit-logs",
        )


# ---------------------------------------------------------------------------
# Public path: Landing backend (via nginx proxy)
# ---------------------------------------------------------------------------


class LandingUser(HttpUser):
    """Simulates anonymous traffic to the public landing page + form."""

    host = LANDING_URL
    wait_time = between(1.0, 3.0)

    @task(20)
    def get_landing(self) -> None:
        self.client.get("/", name="Landing /")

    @task(2)
    def health(self) -> None:
        self.client.get("/health", name="Landing /health")

    @task(3)
    def availability(self) -> None:
        d_from = (datetime.utcnow()).strftime("%Y-%m-%d")
        d_to = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")
        self.client.get(
            f"/api/demo-availability?date_from={d_from}&date_to={d_to}",
            name="Landing /api/demo-availability",
        )

    @task(1)
    def submit_demo(self) -> None:
        # Hits the full DB write path. Honeypot field unset so it persists.
        suffix = random.randint(1_000_000, 9_999_999)
        self.client.post(
            "/api/demo-request",
            json={
                "name": f"Locust Tester {suffix}",
                "work_email": f"loadtest+{suffix}@example.com",
                "company": "Locust Co",
                "role": "Load Test",
                "team_size": "2–10",
                "use_case": "Locust load test — please ignore",
            },
            name="Landing POST /api/demo-request",
        )


# ---------------------------------------------------------------------------
# Lifecycle hooks — friendly summary at run end
# ---------------------------------------------------------------------------


@events.test_start.add_listener
def on_test_start(environment, **_kwargs):
    print("=" * 70)
    print("AI Control Plane — Load Test")
    print(f"  LiteLLM:    {LITELLM_URL}")
    print(f"  Admin API:  {ADMIN_API_URL}")
    print(f"  Landing:    {LANDING_URL}")
    print(f"  Auth:       {'configured' if LITELLM_MASTER_KEY else 'MISSING (admin/llm tasks will 401)'}")
    print("=" * 70)


@events.test_stop.add_listener
def on_test_stop(environment, **_kwargs):
    stats = environment.stats.total
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  Total requests:     {stats.num_requests}")
    print(f"  Total failures:     {stats.num_failures} ({stats.fail_ratio * 100:.2f}%)")
    print(f"  RPS (avg):          {stats.total_rps:.1f}")
    print(f"  Median latency:     {stats.median_response_time} ms")
    print(f"  p95 latency:        {stats.get_response_time_percentile(0.95):.0f} ms")
    print(f"  p99 latency:        {stats.get_response_time_percentile(0.99):.0f} ms")
    print(f"  Max latency:        {stats.max_response_time} ms")
    print("=" * 70)
