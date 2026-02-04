"""
Integration tests for Admin API Service.

Tests authentication, model configuration, budget management,
team management, MCP server configuration, and platform settings.
"""
import pytest
import httpx
from typing import Generator
import uuid


# Test configuration
ADMIN_API_URL = "http://localhost:8086"
TEST_API_KEY = "$LITELLM_KEY"


@pytest.fixture(scope="module")
def http_client() -> Generator[httpx.Client, None, None]:
    """Create HTTP client for tests."""
    with httpx.Client(base_url=ADMIN_API_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
def api_headers() -> dict:
    """Standard API headers."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.fixture(scope="module")
def auth_token(http_client: httpx.Client, api_headers: dict) -> str:
    """Get authentication token for tests."""
    response = http_client.post(
        "/auth/login",
        headers=api_headers,
        json={"api_key": TEST_API_KEY},
    )
    if response.status_code == 200:
        return response.json().get("access_token", "")
    return ""


@pytest.fixture(scope="module")
def auth_headers(auth_token: str) -> dict:
    """Headers with authentication token."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {auth_token}",
    }


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_endpoint(self, http_client: httpx.Client):
        """Verify health endpoint returns OK."""
        response = http_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuthentication:
    """Test authentication endpoints."""

    def test_login_with_valid_key(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test login with valid API key."""
        response = http_client.post(
            "/auth/login",
            headers=api_headers,
            json={"api_key": TEST_API_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    def test_login_with_invalid_key(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test login with invalid API key."""
        response = http_client.post(
            "/auth/login",
            headers=api_headers,
            json={"api_key": "invalid-key"},
        )
        assert response.status_code in [401, 403]

    def test_login_missing_key(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test login without API key."""
        response = http_client.post(
            "/auth/login",
            headers=api_headers,
            json={},
        )
        assert response.status_code == 422

    def test_protected_endpoint_without_auth(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test protected endpoint requires authentication."""
        response = http_client.get("/api/v1/models", headers=api_headers)
        assert response.status_code == 401

    def test_protected_endpoint_with_auth(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test protected endpoint with valid token."""
        response = http_client.get("/api/v1/models", headers=auth_headers)
        assert response.status_code == 200


class TestModelConfiguration:
    """Test model configuration endpoints."""

    def test_list_models(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test listing all models."""
        response = http_client.get("/api/v1/models", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_model_has_required_fields(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test model info contains required fields."""
        response = http_client.get("/api/v1/models", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        if len(data) > 0:
            model = data[0]
            assert "model_id" in model
            assert "provider" in model

    def test_get_model_by_id(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test getting model by ID."""
        # First list models
        list_response = http_client.get("/api/v1/models", headers=auth_headers)
        if list_response.status_code == 200 and len(list_response.json()) > 0:
            model_id = list_response.json()[0]["model_id"]

            response = http_client.get(
                f"/api/v1/models/{model_id}",
                headers=auth_headers,
            )
            assert response.status_code == 200

    def test_update_model_config(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test updating model configuration."""
        # First list models
        list_response = http_client.get("/api/v1/models", headers=auth_headers)
        if list_response.status_code == 200 and len(list_response.json()) > 0:
            model_id = list_response.json()[0]["model_id"]

            response = http_client.put(
                f"/api/v1/models/{model_id}",
                headers=auth_headers,
                json={
                    "default_latency_sla_ms": 3000,
                },
            )
            assert response.status_code in [200, 204]


class TestRoutingPolicies:
    """Test routing policy endpoints."""

    def test_list_routing_policies(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test listing routing policies."""
        response = http_client.get(
            "/api/v1/routing-policies",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_routing_policy(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test creating a routing policy."""
        policy_name = f"test-policy-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/api/v1/routing-policies",
            headers=auth_headers,
            json={
                "name": policy_name,
                "description": "Test routing policy",
                "priority": 50,
                "condition": "context.budget_remaining > 0",
                "action": "permit",
                "target_models": ["gpt-4o-mini", "claude-3-haiku"],
                "is_active": True,
            },
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
        assert data["name"] == policy_name

    def test_update_routing_policy(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test updating a routing policy."""
        # First create a policy
        policy_name = f"test-policy-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/routing-policies",
            headers=auth_headers,
            json={
                "name": policy_name,
                "description": "Original description",
                "priority": 50,
                "condition": "true",
                "action": "permit",
            },
        )
        if create_response.status_code in [200, 201]:
            policy_id = create_response.json()["id"]

            response = http_client.put(
                f"/api/v1/routing-policies/{policy_id}",
                headers=auth_headers,
                json={
                    "description": "Updated description",
                    "priority": 75,
                },
            )
            assert response.status_code in [200, 204]

    def test_delete_routing_policy(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test deleting a routing policy."""
        # First create a policy
        policy_name = f"test-policy-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/routing-policies",
            headers=auth_headers,
            json={
                "name": policy_name,
                "condition": "true",
                "action": "permit",
            },
        )
        if create_response.status_code in [200, 201]:
            policy_id = create_response.json()["id"]

            response = http_client.delete(
                f"/api/v1/routing-policies/{policy_id}",
                headers=auth_headers,
            )
            assert response.status_code in [200, 204]


class TestBudgetManagement:
    """Test budget management endpoints."""

    def test_list_budgets(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test listing budgets."""
        response = http_client.get("/api/v1/budgets", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_budget(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test creating a budget."""
        budget_name = f"test-budget-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            json={
                "name": budget_name,
                "entity_type": "user",
                "entity_id": f"user-{uuid.uuid4().hex[:8]}",
                "monthly_limit": 100.00,
                "soft_limit_percent": 0.80,
                "hard_limit_percent": 1.00,
                "is_active": True,
            },
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
        assert data["name"] == budget_name

    def test_get_budget_by_id(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test getting budget by ID."""
        # First create a budget
        budget_name = f"test-budget-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            json={
                "name": budget_name,
                "entity_type": "user",
                "entity_id": f"user-{uuid.uuid4().hex[:8]}",
                "monthly_limit": 100.00,
            },
        )
        if create_response.status_code in [200, 201]:
            budget_id = create_response.json()["id"]

            response = http_client.get(
                f"/api/v1/budgets/{budget_id}",
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == budget_id

    def test_update_budget(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test updating a budget."""
        # First create a budget
        budget_name = f"test-budget-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            json={
                "name": budget_name,
                "entity_type": "user",
                "entity_id": f"user-{uuid.uuid4().hex[:8]}",
                "monthly_limit": 100.00,
            },
        )
        if create_response.status_code in [200, 201]:
            budget_id = create_response.json()["id"]

            response = http_client.put(
                f"/api/v1/budgets/{budget_id}",
                headers=auth_headers,
                json={
                    "monthly_limit": 200.00,
                },
            )
            assert response.status_code in [200, 204]

    def test_budget_validation(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test budget creation validates required fields."""
        response = http_client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            json={
                "name": "incomplete-budget",
                # Missing required fields
            },
        )
        assert response.status_code == 422


class TestTeamManagement:
    """Test team management endpoints."""

    def test_list_teams(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test listing teams."""
        response = http_client.get("/api/v1/teams", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_team(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test creating a team."""
        team_name = f"test-team-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/api/v1/teams",
            headers=auth_headers,
            json={
                "name": team_name,
                "description": "Test team for integration testing",
                "monthly_budget": 500.00,
                "default_model": "gpt-4o-mini",
                "is_active": True,
            },
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
        assert data["name"] == team_name

    def test_get_team_by_id(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test getting team by ID."""
        # First create a team
        team_name = f"test-team-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/teams",
            headers=auth_headers,
            json={
                "name": team_name,
                "description": "Test team",
            },
        )
        if create_response.status_code in [200, 201]:
            team_id = create_response.json()["id"]

            response = http_client.get(
                f"/api/v1/teams/{team_id}",
                headers=auth_headers,
            )
            assert response.status_code == 200

    def test_add_team_member(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test adding member to team."""
        # First create a team
        team_name = f"test-team-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/teams",
            headers=auth_headers,
            json={
                "name": team_name,
                "description": "Test team",
            },
        )
        if create_response.status_code in [200, 201]:
            team_id = create_response.json()["id"]
            user_id = f"user-{uuid.uuid4().hex[:8]}"

            response = http_client.post(
                f"/api/v1/teams/{team_id}/members",
                headers=auth_headers,
                json={
                    "user_id": user_id,
                    "role": "member",
                },
            )
            assert response.status_code in [200, 201]

    def test_list_team_members(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test listing team members."""
        # First create a team and add a member
        team_name = f"test-team-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/teams",
            headers=auth_headers,
            json={
                "name": team_name,
                "description": "Test team",
            },
        )
        if create_response.status_code in [200, 201]:
            team_id = create_response.json()["id"]

            response = http_client.get(
                f"/api/v1/teams/{team_id}/members",
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


class TestMCPServerConfiguration:
    """Test MCP server configuration endpoints."""

    def test_list_mcp_servers(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test listing MCP servers."""
        response = http_client.get(
            "/api/v1/mcp-servers",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_mcp_server(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test creating an MCP server configuration."""
        server_name = f"test-mcp-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/api/v1/mcp-servers",
            headers=auth_headers,
            json={
                "name": server_name,
                "server_type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-test"],
                "is_active": True,
            },
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
        assert data["name"] == server_name

    def test_update_mcp_server(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test updating MCP server configuration."""
        # First create an MCP server
        server_name = f"test-mcp-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/mcp-servers",
            headers=auth_headers,
            json={
                "name": server_name,
                "server_type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-test"],
            },
        )
        if create_response.status_code in [200, 201]:
            server_id = create_response.json()["id"]

            response = http_client.put(
                f"/api/v1/mcp-servers/{server_id}",
                headers=auth_headers,
                json={
                    "is_active": False,
                },
            )
            assert response.status_code in [200, 204]

    def test_delete_mcp_server(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test deleting MCP server configuration."""
        # First create an MCP server
        server_name = f"test-mcp-{uuid.uuid4().hex[:8]}"
        create_response = http_client.post(
            "/api/v1/mcp-servers",
            headers=auth_headers,
            json={
                "name": server_name,
                "server_type": "stdio",
                "command": "echo",
            },
        )
        if create_response.status_code in [200, 201]:
            server_id = create_response.json()["id"]

            response = http_client.delete(
                f"/api/v1/mcp-servers/{server_id}",
                headers=auth_headers,
            )
            assert response.status_code in [200, 204]


class TestWorkflowTemplates:
    """Test workflow template endpoints via Admin API."""

    def test_list_workflow_templates(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test listing workflow templates."""
        response = http_client.get(
            "/api/v1/workflows",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_workflow_template(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test creating a workflow template."""
        workflow_name = f"test-workflow-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/api/v1/workflows",
            headers=auth_headers,
            json={
                "name": workflow_name,
                "description": "Test workflow template",
                "template_type": "custom",
                "graph_definition": {
                    "nodes": ["start", "process", "end"],
                    "edges": [
                        {"from": "start", "to": "process"},
                        {"from": "process", "to": "end"},
                    ],
                },
                "is_active": True,
            },
        )
        assert response.status_code in [200, 201]


class TestPlatformSettings:
    """Test platform settings endpoints."""

    def test_get_settings(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test getting platform settings."""
        response = http_client.get(
            "/api/v1/settings",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict) or isinstance(data, list)

    def test_update_setting(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test updating a platform setting."""
        response = http_client.put(
            "/api/v1/settings/default_model",
            headers=auth_headers,
            json={"value": "gpt-4o-mini"},
        )
        assert response.status_code in [200, 204]

    def test_get_specific_setting(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test getting a specific setting."""
        response = http_client.get(
            "/api/v1/settings/default_model",
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestRealtimeMetrics:
    """Test real-time metrics endpoint."""

    def test_get_realtime_metrics(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test getting real-time metrics."""
        response = http_client.get(
            "/api/v1/metrics/realtime",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_metrics_include_expected_fields(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test metrics include expected fields."""
        response = http_client.get(
            "/api/v1/metrics/realtime",
            headers=auth_headers,
        )
        if response.status_code == 200:
            data = response.json()
            # Should have some metric categories
            assert any(key in data for key in [
                "requests", "costs", "latency", "models", "errors"
            ])


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_not_found_resource(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test 404 for non-existent resource."""
        fake_id = str(uuid.uuid4())
        response = http_client.get(
            f"/api/v1/budgets/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_invalid_json_body(
        self, http_client: httpx.Client, auth_headers: dict
    ):
        """Test handling of invalid JSON."""
        response = http_client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            content="not valid json",
        )
        assert response.status_code == 422

    def test_expired_token(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test handling of expired/invalid token."""
        headers = {
            **api_headers,
            "Authorization": "Bearer invalid-token",
        }
        response = http_client.get("/api/v1/models", headers=headers)
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
