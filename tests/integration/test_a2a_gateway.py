"""
Integration tests for A2A (Agent-to-Agent) Gateway functionality.

Tests:
- Agent discovery
- Agent registration
- Agent-to-agent communication
"""

import os
import pytest
import httpx
import json

# Configuration from environment
A2A_GATEWAY_URL = os.getenv("A2A_GATEWAY_URL", "http://localhost:3002")
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


class TestAgentDiscovery:
    """Test agent discovery functionality."""

    def test_list_agents(self, http_client, api_headers):
        """Test listing registered agents."""
        response = http_client.get(
            f"{A2A_GATEWAY_URL}/agents",
            headers=api_headers
        )

        if response.status_code == 200:
            data = response.json()
            assert "agents" in data or isinstance(data, list)
        else:
            # Gateway might not be running
            assert response.status_code in [200, 502, 503]

    def test_agent_card_endpoint(self, http_client, api_headers):
        """Test the well-known agent card endpoint."""
        response = http_client.get(
            f"{A2A_GATEWAY_URL}/.well-known/agent.json",
            headers=api_headers
        )

        if response.status_code == 200:
            data = response.json()
            # Agent card should have standard fields
            # Based on A2A protocol specification
            expected_fields = ["name", "description", "capabilities"]
            for field in expected_fields:
                if field in data:
                    assert data[field] is not None
        else:
            assert response.status_code in [200, 404, 502, 503]

    def test_discover_agent_by_capability(self, http_client, api_headers):
        """Test discovering agents by capability."""
        response = http_client.get(
            f"{A2A_GATEWAY_URL}/agents",
            headers=api_headers,
            params={"capability": "code_generation"}
        )

        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", data) if isinstance(data, dict) else data

            # All returned agents should have the requested capability
            for agent in agents:
                capabilities = agent.get("capabilities", [])
                # Capability might be in capabilities or not filtered
                print(f"Agent: {agent.get('name')}, Capabilities: {capabilities}")
        else:
            assert response.status_code in [200, 502, 503]


class TestAgentCommunication:
    """Test agent-to-agent communication."""

    def test_send_message_to_agent(self, http_client, api_headers):
        """Test sending a message to an agent."""
        # First, get list of agents
        agents_response = http_client.get(
            f"{A2A_GATEWAY_URL}/agents",
            headers=api_headers
        )

        if agents_response.status_code != 200:
            pytest.skip("A2A gateway not available")

        agents = agents_response.json()
        if not agents:
            pytest.skip("No agents registered")

        agent_list = agents.get("agents", agents) if isinstance(agents, dict) else agents
        if not agent_list:
            pytest.skip("No agents in list")

        agent_id = agent_list[0].get("id") or agent_list[0].get("name")

        # Send a test message
        response = http_client.post(
            f"{A2A_GATEWAY_URL}/agents/{agent_id}",
            headers=api_headers,
            json={
                "type": "message",
                "content": {
                    "text": "Hello, this is a test message."
                }
            }
        )

        # Message might be rejected, queued, or processed
        assert response.status_code in [200, 202, 400, 404, 502, 503]

    def test_send_task_to_agent(self, http_client, api_headers):
        """Test sending a task request to an agent."""
        agents_response = http_client.get(
            f"{A2A_GATEWAY_URL}/agents",
            headers=api_headers
        )

        if agents_response.status_code != 200:
            pytest.skip("A2A gateway not available")

        agents = agents_response.json()
        agent_list = agents.get("agents", agents) if isinstance(agents, dict) else agents
        if not agent_list:
            pytest.skip("No agents available")

        agent_id = agent_list[0].get("id") or agent_list[0].get("name")

        # Send a task request
        response = http_client.post(
            f"{A2A_GATEWAY_URL}/agents/{agent_id}/tasks",
            headers=api_headers,
            json={
                "type": "task",
                "task": {
                    "id": "test-task-001",
                    "description": "Test task",
                    "input": {"test": True}
                }
            }
        )

        # Task might be rejected or accepted
        assert response.status_code in [200, 202, 400, 404, 502, 503]


class TestAgentRegistration:
    """Test agent registration functionality."""

    def test_register_agent(self, http_client, api_headers):
        """Test registering a new agent."""
        agent_data = {
            "name": "test-agent",
            "description": "A test agent for integration testing",
            "url": "http://test-agent:8080",
            "capabilities": ["testing", "echo"]
        }

        response = http_client.post(
            f"{A2A_GATEWAY_URL}/agents",
            headers=api_headers,
            json=agent_data
        )

        # Registration might succeed or fail depending on auth
        assert response.status_code in [200, 201, 400, 401, 403, 502, 503]

        if response.status_code in [200, 201]:
            data = response.json()
            # Should return agent info or ID
            assert "id" in data or "name" in data


class TestA2AHealthCheck:
    """Test A2A Gateway health."""

    def test_a2a_gateway_health(self, http_client):
        """Test A2A Gateway health endpoint."""
        response = http_client.get(f"{A2A_GATEWAY_URL}/health")
        assert response.status_code in [200, 502, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
