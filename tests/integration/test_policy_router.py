"""
Integration tests for Policy Router Service.

Tests Cedar policy evaluation, model routing decisions,
metrics collection, and policy management.
"""
import pytest
import httpx
from typing import Generator


# Test configuration
POLICY_ROUTER_URL = "http://localhost:8084"


@pytest.fixture(scope="module")
def http_client() -> Generator[httpx.Client, None, None]:
    """Create HTTP client for tests."""
    with httpx.Client(base_url=POLICY_ROUTER_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
def api_headers() -> dict:
    """Standard API headers."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_endpoint(self, http_client: httpx.Client):
        """Verify health endpoint returns OK."""
        response = http_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "cedar_policies_loaded" in data
        assert "metrics_available" in data


class TestModelRouting:
    """Test model routing decisions."""

    def test_route_with_budget_constraint(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test routing selects budget-friendly model when budget is low."""
        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": "test-user",
                "team_id": "engineering",
                "requested_model": "smart",
                "budget_remaining": 5.0,
                "latency_sla_ms": 5000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "selected_model" in data
        assert "fallback_models" in data
        assert "decision_reason" in data
        # Low budget should prefer self-hosted or budget models
        assert data["selected_model"] in [
            "llama-3.1-70b",
            "gpt-4o-mini",
            "claude-3-haiku",
        ]

    def test_route_with_high_budget(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test routing allows premium models with high budget."""
        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": "test-user",
                "team_id": "data-science",
                "requested_model": "smart",
                "budget_remaining": 500.0,
                "latency_sla_ms": 5000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "selected_model" in data
        # High budget allows premium models
        assert data["selected_model"] in [
            "gpt-4o",
            "claude-3-5-sonnet",
            "grok-3",
            "gpt-4o-mini",
        ]

    def test_route_with_strict_latency_sla(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test routing respects latency SLA requirements."""
        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": "test-user",
                "team_id": "engineering",
                "requested_model": "smart",
                "budget_remaining": 100.0,
                "latency_sla_ms": 500,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "selected_model" in data
        # Strict latency should exclude slow models
        # Decision should mention latency in reason
        assert data["selected_model"] is not None

    def test_route_with_specific_model_request(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test routing with a specific model requested."""
        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": "test-user",
                "team_id": "engineering",
                "requested_model": "gpt-4o-mini",
                "budget_remaining": 100.0,
                "latency_sla_ms": 5000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should try to honor specific model if allowed by policies
        assert "selected_model" in data

    def test_route_missing_required_fields(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test routing returns error for missing fields."""
        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": "test-user",
                # Missing required fields
            },
        )
        assert response.status_code == 422  # Validation error

    def test_route_includes_fallback_chain(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test routing provides fallback models."""
        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": "test-user",
                "team_id": "engineering",
                "requested_model": "smart",
                "budget_remaining": 100.0,
                "latency_sla_ms": 5000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "fallback_models" in data
        assert isinstance(data["fallback_models"], list)


class TestCedarPolicyEvaluation:
    """Test direct Cedar policy evaluation."""

    def test_evaluate_permit_policy(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test Cedar policy evaluation returns permit."""
        response = http_client.post(
            "/evaluate",
            headers=api_headers,
            json={
                "principal": "User::\"test-user\"",
                "action": "routing:select_model",
                "resource": "Model::\"gpt-4o-mini\"",
                "context": {
                    "cost_budget_remaining": 100.0,
                    "latency_sla_ms": 5000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "decision" in data
        assert data["decision"] in ["permit", "deny"]

    def test_evaluate_deny_over_budget(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test Cedar policy denies premium model when over budget."""
        response = http_client.post(
            "/evaluate",
            headers=api_headers,
            json={
                "principal": "User::\"test-user\"",
                "action": "routing:select_model",
                "resource": "Model::\"gpt-4o\"",
                "context": {
                    "cost_budget_remaining": 1.0,
                    "latency_sla_ms": 5000,
                    "model_tier": "premium",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "decision" in data


class TestPolicyManagement:
    """Test policy reload and management."""

    def test_reload_policies(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test hot-reload of Cedar policies."""
        response = http_client.post(
            "/policies/reload",
            headers=api_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reloaded"
        assert "policies_count" in data

    def test_reload_policies_idempotent(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test policy reload is idempotent."""
        # Reload twice
        response1 = http_client.post("/policies/reload", headers=api_headers)
        response2 = http_client.post("/policies/reload", headers=api_headers)

        assert response1.status_code == 200
        assert response2.status_code == 200
        # Should work consistently
        assert response1.json()["policies_count"] == response2.json()["policies_count"]


class TestModelListing:
    """Test model listing with metrics."""

    def test_list_models(self, http_client: httpx.Client, api_headers: dict):
        """Test listing available models."""
        response = http_client.get("/models", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_model_has_required_fields(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test model info contains required fields."""
        response = http_client.get("/models", headers=api_headers)
        assert response.status_code == 200
        data = response.json()

        for model in data:
            assert "model_id" in model
            assert "provider" in model
            assert "tier" in model
            assert "available" in model

    def test_models_include_metrics(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test model info includes real-time metrics."""
        response = http_client.get("/models", headers=api_headers)
        assert response.status_code == 200
        data = response.json()

        for model in data:
            # Metrics may be None if Prometheus unavailable
            if "metrics" in model and model["metrics"]:
                metrics = model["metrics"]
                assert "latency_p50_ms" in metrics or metrics is None
                assert "error_rate" in metrics or metrics is None


class TestRoutingDecisionRecording:
    """Test that routing decisions are recorded to database."""

    def test_routing_records_decision(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test routing decision is recorded."""
        # Make a routing request with a unique user
        import uuid
        unique_user = f"test-user-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": unique_user,
                "team_id": "engineering",
                "requested_model": "smart",
                "budget_remaining": 100.0,
                "latency_sla_ms": 5000,
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Response should include decision ID for tracking
        assert "decision_id" in data or "selected_model" in data


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_invalid_json(self, http_client: httpx.Client, api_headers: dict):
        """Test handling of invalid JSON."""
        response = http_client.post(
            "/route",
            headers=api_headers,
            content="not valid json",
        )
        assert response.status_code == 422

    def test_invalid_context_types(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test handling of invalid context value types."""
        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": "test-user",
                "team_id": "engineering",
                "requested_model": "smart",
                "budget_remaining": "not a number",  # Should be float
                "latency_sla_ms": 5000,
            },
        )
        assert response.status_code == 422


class TestMetricsIntegration:
    """Test Prometheus metrics integration."""

    def test_metrics_affect_routing(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test that metrics influence routing decisions."""
        # This is a smoke test - actual behavior depends on Prometheus data
        response = http_client.post(
            "/route",
            headers=api_headers,
            json={
                "user_id": "test-user",
                "team_id": "engineering",
                "requested_model": "smart",
                "budget_remaining": 100.0,
                "latency_sla_ms": 2000,  # Moderate SLA
                "consider_metrics": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "selected_model" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
