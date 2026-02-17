"""Integration tests for the A2A Runtime API.

Tests HTTP endpoints for agent registry, workflow management,
messaging, and human-in-the-loop approvals.
"""

import importlib.util
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# Pre-mock temporalio modules since they may not be installed in test env
for _mock_mod_name in [
    "temporalio",
    "temporalio.client",
    "temporalio.worker",
    "temporalio.common",
    "temporalio.worker.workflow_sandbox",
    "temporalio.workflow",
    "temporalio.activity",
]:
    if _mock_mod_name not in sys.modules:
        sys.modules[_mock_mod_name] = MagicMock()

# Pre-mock redis.asyncio if not available
try:
    import redis.asyncio  # noqa: F401
except ImportError:
    _redis_mock = MagicMock()
    sys.modules["redis"] = _redis_mock
    sys.modules["redis.asyncio"] = _redis_mock

# Load the a2a-runtime module
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/a2a-runtime")
_service_path = os.path.join(_service_dir, "main.py")
sys.path.insert(0, _service_dir)
_spec = importlib.util.spec_from_file_location("a2a_runtime_integ", _service_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["a2a_runtime_integ"] = _mod
_spec.loader.exec_module(_mod)

app = _mod.app

# The state module holds redis_client and temporal_client after refactor
import state as _state_mod  # noqa: E402


def _make_redis_mock():
    """Create an AsyncMock Redis client with standard methods."""
    mock = AsyncMock()
    mock.ping.return_value = True
    mock.hset.return_value = 1
    mock.hget.return_value = None
    mock.hdel.return_value = 1
    mock.hgetall.return_value = {}
    mock.sadd.return_value = 1
    mock.srem.return_value = 1
    mock.smembers.return_value = set()
    mock.rpush.return_value = 1
    mock.lrange.return_value = []
    mock.set.return_value = True
    mock.get.return_value = None

    async def _empty_scan(*args, **kwargs):
        return
        yield  # noqa: F841 - makes this an async generator

    mock.scan_iter = _empty_scan
    return mock


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module state between tests."""
    original_redis = _state_mod.redis_client
    original_temporal = _state_mod.temporal_client
    yield
    _state_mod.redis_client = original_redis
    _state_mod.temporal_client = original_temporal


@pytest.fixture
def client():
    """ASGI test client with mocked Redis and no Temporal."""
    _state_mod.redis_client = _make_redis_mock()
    _state_mod.temporal_client = None
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# /health
# ============================================================================


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_degraded(self, client):
        """Health should report degraded when Temporal is unavailable."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["temporal"] == "disconnected"


# ============================================================================
# Agent Registry
# ============================================================================


class TestAgentRegistry:
    @pytest.mark.asyncio
    async def test_register_agent(self, client):
        """Register agent should return agent ID."""
        resp = await client.post(
            "/agents/register",
            json={
                "id": "agent-1",
                "name": "Test Agent",
                "description": "A test agent",
                "endpoint": "http://localhost:9001",
                "capabilities": [{"name": "summarize", "description": "Summarize text"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "registered"
        assert data["agent_id"] == "agent-1"
        _state_mod.redis_client.hset.assert_called()

    @pytest.mark.asyncio
    async def test_list_agents(self, client):
        """List agents should return agent list from Redis."""
        _state_mod.redis_client.hgetall.return_value = {}
        resp = await client.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

    @pytest.mark.asyncio
    async def test_get_agent_found(self, client):
        """Get agent should return agent data when found."""
        agent_data = json.dumps(
            {
                "id": "agent-1",
                "name": "Test Agent",
                "description": "A test agent",
                "endpoint": "http://localhost:9001",
                "capabilities": [],
                "status": "available",
                "metadata": {},
            }
        )
        _state_mod.redis_client.hget.return_value = agent_data
        resp = await client.get("/agents/agent-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "agent-1"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, client):
        """Get agent should return 404 when not found."""
        _state_mod.redis_client.hget.return_value = None
        resp = await client.get("/agents/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_agent(self, client):
        """Delete agent should unregister from Redis."""
        _state_mod.redis_client.hget.return_value = None
        resp = await client.delete("/agents/agent-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unregistered"
        assert data["agent_id"] == "agent-1"
        _state_mod.redis_client.hdel.assert_called()


# ============================================================================
# Workflows
# ============================================================================


class TestWorkflowEndpoints:
    @pytest.mark.asyncio
    async def test_start_workflow_no_temporal(self, client):
        """Start workflow should return 503 when Temporal is unavailable."""
        resp = await client.post(
            "/workflows/start",
            json={
                "workflow_type": "single_agent",
                "agents": ["agent-1"],
                "input": {"task": "test"},
            },
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_get_workflow_status_no_temporal(self, client):
        """Get workflow status should return 503 when Temporal is unavailable."""
        resp = await client.get("/workflows/wf-123")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_cancel_workflow_no_temporal(self, client):
        """Cancel workflow should return 503 when Temporal is unavailable."""
        resp = await client.post("/workflows/wf-123/cancel")
        assert resp.status_code == 503


# ============================================================================
# Messaging
# ============================================================================


class TestMessagingEndpoints:
    @pytest.mark.asyncio
    async def test_send_message(self, client):
        """Send message should store in Redis and return message ID."""
        _state_mod.redis_client.hget.return_value = None  # no agent to notify
        resp = await client.post(
            "/messages",
            json={
                "source_agent": "agent-1",
                "target_agent": "agent-2",
                "content": {"text": "Hello"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"
        assert "message_id" in data
        _state_mod.redis_client.rpush.assert_called()

    @pytest.mark.asyncio
    async def test_get_messages(self, client):
        """Get messages should return agent message list."""
        _state_mod.redis_client.lrange.return_value = []
        resp = await client.get("/messages/agent-1")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)


# ============================================================================
# Human Approvals
# ============================================================================


class TestApprovalEndpoints:
    @pytest.mark.asyncio
    async def test_submit_approval(self, client):
        """Submit approval should store in Redis."""
        resp = await client.post(
            "/approvals",
            json={
                "workflow_id": "wf-123",
                "step_id": "step-1",
                "approved": True,
                "comment": "Looks good",
                "approver": "admin",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        _state_mod.redis_client.set.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
