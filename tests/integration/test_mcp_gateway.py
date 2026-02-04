"""
Integration tests for MCP Gateway functionality.

Tests:
- MCP tool discovery
- Tool invocation
- Tool aggregation from multiple servers
"""

import os
import pytest
import httpx

# Configuration from environment
MCP_GATEWAY_URL = os.getenv("MCP_GATEWAY_URL", "http://localhost:3001")
API_KEY = os.getenv("TEST_API_KEY", "sk-test-key")


@pytest.fixture
def http_client():
    """Create HTTP client for tests."""
    return httpx.Client(timeout=60.0)


@pytest.fixture
def api_headers():
    """Common API headers."""
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }


class TestMCPToolDiscovery:
    """Test MCP tool discovery functionality."""

    def test_list_tools(self, http_client, api_headers):
        """Test listing all available MCP tools."""
        response = http_client.get(
            f"{MCP_GATEWAY_URL}/tools",
            headers=api_headers
        )

        # May return 200 or 503 depending on MCP server availability
        if response.status_code == 200:
            data = response.json()
            assert "tools" in data or isinstance(data, list)
        else:
            assert response.status_code in [200, 503, 502]

    def test_tool_metadata(self, http_client, api_headers):
        """Test that tool metadata is properly formatted."""
        response = http_client.get(
            f"{MCP_GATEWAY_URL}/tools",
            headers=api_headers
        )

        if response.status_code == 200:
            data = response.json()
            tools = data.get("tools", data) if isinstance(data, dict) else data

            for tool in tools:
                # Each tool should have required fields
                assert "name" in tool
                # Optional but expected fields
                if "description" in tool:
                    assert isinstance(tool["description"], str)
                if "inputSchema" in tool:
                    assert isinstance(tool["inputSchema"], dict)


class TestMCPToolInvocation:
    """Test MCP tool invocation."""

    def test_invoke_tool_success(self, http_client, api_headers):
        """Test successful tool invocation."""
        # First get available tools
        tools_response = http_client.get(
            f"{MCP_GATEWAY_URL}/tools",
            headers=api_headers
        )

        if tools_response.status_code != 200:
            pytest.skip("MCP servers not available")

        tools = tools_response.json()
        if not tools:
            pytest.skip("No tools available")

        # Try to invoke the first available tool
        # This is a generic test - specific tool tests would be more targeted
        tool_name = tools[0]["name"] if isinstance(tools, list) else tools.get("tools", [{}])[0].get("name")

        if not tool_name:
            pytest.skip("No tool name found")

        response = http_client.post(
            f"{MCP_GATEWAY_URL}/tools/{tool_name}",
            headers=api_headers,
            json={}  # Empty input for basic test
        )

        # Tool invocation might fail with bad input, but should return a valid response
        assert response.status_code in [200, 400, 422]

    def test_invoke_nonexistent_tool(self, http_client, api_headers):
        """Test invoking a non-existent tool returns 404."""
        response = http_client.post(
            f"{MCP_GATEWAY_URL}/tools/nonexistent_tool_12345",
            headers=api_headers,
            json={}
        )

        # Should return 404 or 502 if gateway is unavailable
        assert response.status_code in [404, 502, 503]


class TestMCPToolAggregation:
    """Test tool aggregation from multiple MCP servers."""

    def test_tools_from_multiple_servers(self, http_client, api_headers):
        """Test that tools from multiple servers are aggregated."""
        response = http_client.get(
            f"{MCP_GATEWAY_URL}/tools",
            headers=api_headers
        )

        if response.status_code != 200:
            pytest.skip("MCP servers not available")

        data = response.json()
        tools = data.get("tools", data) if isinstance(data, dict) else data

        # If tool prefixing is enabled, tools should have server prefix
        # e.g., "filesystem-tools:read_file", "database-tools:query"
        prefixed_tools = [t for t in tools if ":" in t.get("name", "")]

        # This test is informational - may or may not have prefixed tools
        # depending on configuration
        print(f"Found {len(tools)} tools, {len(prefixed_tools)} with server prefix")


class TestMCPSSE:
    """Test MCP Server-Sent Events endpoint."""

    def test_sse_endpoint_exists(self, http_client, api_headers):
        """Test that SSE endpoint is accessible."""
        # SSE endpoint should return streaming response
        response = http_client.get(
            f"{MCP_GATEWAY_URL}/sse",
            headers=api_headers,
            timeout=5.0  # Short timeout for connection test
        )

        # Should either work or return appropriate error
        assert response.status_code in [200, 400, 502, 503]


class TestMCPHealthCheck:
    """Test MCP Gateway health."""

    def test_mcp_gateway_health(self, http_client):
        """Test MCP Gateway health endpoint."""
        response = http_client.get(f"{MCP_GATEWAY_URL}/health")
        # Health check should work even if MCP servers are down
        assert response.status_code in [200, 502, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
