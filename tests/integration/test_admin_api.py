"""
Integration tests for Admin API Service.

Tests authentication, MCP server configuration, workflow templates,
and platform settings.
"""

import uuid
from typing import Generator

import httpx
import pytest

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

    def test_login_with_valid_key(self, http_client: httpx.Client, api_headers: dict):
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

    def test_login_with_invalid_key(self, http_client: httpx.Client, api_headers: dict):
        """Test login with invalid API key."""
        response = http_client.post(
            "/auth/login",
            headers=api_headers,
            json={"api_key": "invalid-key"},
        )
        assert response.status_code in [401, 403]

    def test_login_missing_key(self, http_client: httpx.Client, api_headers: dict):
        """Test login without API key."""
        response = http_client.post(
            "/auth/login",
            headers=api_headers,
            json={},
        )
        assert response.status_code == 422

    def test_protected_endpoint_without_auth(self, http_client: httpx.Client, api_headers: dict):
        """Test protected endpoint requires authentication."""
        response = http_client.get("/api/v1/settings", headers=api_headers)
        assert response.status_code == 401

    def test_protected_endpoint_with_auth(self, http_client: httpx.Client, auth_headers: dict):
        """Test protected endpoint with valid token."""
        response = http_client.get("/api/v1/settings", headers=auth_headers)
        assert response.status_code == 200


class TestMCPServerConfiguration:
    """Test MCP server configuration endpoints."""

    def test_list_mcp_servers(self, http_client: httpx.Client, auth_headers: dict):
        """Test listing MCP servers."""
        response = http_client.get(
            "/api/v1/mcp-servers",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_mcp_server(self, http_client: httpx.Client, auth_headers: dict):
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

    def test_update_mcp_server(self, http_client: httpx.Client, auth_headers: dict):
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

    def test_delete_mcp_server(self, http_client: httpx.Client, auth_headers: dict):
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

    def test_list_workflow_templates(self, http_client: httpx.Client, auth_headers: dict):
        """Test listing workflow templates."""
        response = http_client.get(
            "/api/v1/workflows",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_workflow_template(self, http_client: httpx.Client, auth_headers: dict):
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

    def test_get_settings(self, http_client: httpx.Client, auth_headers: dict):
        """Test getting platform settings."""
        response = http_client.get(
            "/api/v1/settings",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict) or isinstance(data, list)

    def test_update_setting(self, http_client: httpx.Client, auth_headers: dict):
        """Test updating a platform setting."""
        response = http_client.put(
            "/api/v1/settings/default_model",
            headers=auth_headers,
            json={"value": "gpt-4o-mini"},
        )
        assert response.status_code in [200, 204]

    def test_get_specific_setting(self, http_client: httpx.Client, auth_headers: dict):
        """Test getting a specific setting."""
        response = http_client.get(
            "/api/v1/settings/default_model",
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_expired_token(self, http_client: httpx.Client, api_headers: dict):
        """Test handling of expired/invalid token."""
        headers = {
            **api_headers,
            "Authorization": "Bearer invalid-token",
        }
        response = http_client.get("/api/v1/settings", headers=headers)
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
