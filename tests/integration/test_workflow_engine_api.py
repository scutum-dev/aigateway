"""Integration tests for the Workflow Engine API.

Tests HTTP endpoints, ServiceAuthMiddleware, template listing,
execution management, and dependency injection.
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# Workflow engine has its own requirements.txt with langgraph + temporalio. Those
# aren't in `tests/requirements.txt`, so on a CI host without them, skip cleanly.
pytest.importorskip("langgraph", reason="langgraph not installed; install via src/workflow-engine/requirements.txt")

# Load the workflow-engine module
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/workflow-engine")
_service_path = os.path.join(_service_dir, "main.py")
sys.path.insert(0, _service_dir)

# Remove any previously-cached ``models``, ``config``, or ``routes`` packages
# (e.g. from other service tests collected earlier) so that the workflow-engine
# versions are found from ``_service_dir`` instead.
for _stale in list(sys.modules):
    if (
        _stale == "models"
        or _stale.startswith("models.")
        or _stale == "config"
        or _stale.startswith("config.")
        or _stale == "routes"
        or _stale.startswith("routes.")
    ):
        sys.modules.pop(_stale)

_spec = importlib.util.spec_from_file_location("workflow_engine_integ", _service_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["workflow_engine_integ"] = _mod
_spec.loader.exec_module(_mod)

app = _mod.app

# Import routes module (already loaded by main.py) to access set_dependencies
import api.routes as _routes_mod  # noqa: E402
from api.routes import set_dependencies as _set_dependencies  # noqa: E402

SERVICE_KEY = "test-integration-key"


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Reset module state between tests. INTERNAL_SERVICE_KEY moved to env-var
    via shared.middleware.ServiceAuthMiddleware (cost-predictor pattern); the
    routes-module dependency injection still uses module-level state."""
    monkeypatch.delenv("INTERNAL_SERVICE_KEY", raising=False)
    original_repo = _routes_mod._repository
    original_manager = _routes_mod._workflow_manager
    yield
    _routes_mod._repository = original_repo
    _routes_mod._workflow_manager = original_manager


@pytest.fixture
def client(monkeypatch):
    """ASGI test client (dev mode, no auth) with mock dependencies."""
    monkeypatch.delenv("INTERNAL_SERVICE_KEY", raising=False)
    mock_repo = AsyncMock()
    mock_manager = AsyncMock()
    _set_dependencies(mock_repo, mock_manager)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def authed_client(monkeypatch):
    """ASGI test client with auth required and mock dependencies."""
    monkeypatch.setenv("INTERNAL_SERVICE_KEY", SERVICE_KEY)
    mock_repo = AsyncMock()
    mock_manager = AsyncMock()
    _set_dependencies(mock_repo, mock_manager)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def no_deps_client(monkeypatch):
    """ASGI test client with no repository or manager set."""
    monkeypatch.delenv("INTERNAL_SERVICE_KEY", raising=False)
    _routes_mod._repository = None
    _routes_mod._workflow_manager = None
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# ServiceAuthMiddleware
# ============================================================================


class TestServiceAuthMiddleware:
    @pytest.mark.asyncio
    async def test_health_exempt(self, authed_client):
        """Health endpoint should bypass auth."""
        resp = await authed_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_templates_requires_auth(self, authed_client):
        """Templates endpoint should require service key."""
        resp = await authed_client.get("/api/v1/templates")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_templates_with_correct_key(self, authed_client):
        """Templates endpoint should work with correct key."""
        resp = await authed_client.get("/api/v1/templates", headers={"X-Service-Key": SERVICE_KEY})
        assert resp.status_code != 401


# ============================================================================
# /health
# ============================================================================


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        """Health endpoint should return healthy status."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


# ============================================================================
# GET /api/v1/templates
# ============================================================================


class TestTemplatesEndpoint:
    @pytest.mark.asyncio
    async def test_list_templates(self, client):
        """Templates endpoint should return all three templates."""
        resp = await client.get("/api/v1/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert len(data["templates"]) == 3
        types = [t["type"] for t in data["templates"]]
        assert "research" in types
        assert "coding" in types
        assert "data_analysis" in types

    @pytest.mark.asyncio
    async def test_templates_have_required_fields(self, client):
        """Each template should have type, name, description, and nodes."""
        resp = await client.get("/api/v1/templates")
        assert resp.status_code == 200
        for template in resp.json()["templates"]:
            assert "type" in template
            assert "name" in template
            assert "description" in template
            assert "nodes" in template
            assert isinstance(template["nodes"], list)
            assert len(template["nodes"]) > 0


# ============================================================================
# POST /api/v1/executions
# ============================================================================


class TestExecutionsEndpoint:
    @pytest.mark.asyncio
    async def test_start_execution(self, client):
        """Start execution should call workflow manager."""
        mock_output = MagicMock()
        mock_output.execution_id = "exec-123"
        mock_output.status = "completed"
        mock_output.output = {"result": "done"}
        mock_output.error = None
        mock_output.total_cost = 0.01
        mock_output.total_tokens = 500
        mock_output.duration_ms = 1234
        # Make model_dump return all fields for Pydantic serialization
        mock_output.model_dump = MagicMock(
            return_value={
                "execution_id": "exec-123",
                "status": "completed",
                "output": {"result": "done"},
                "error": None,
                "total_cost": 0.01,
                "total_tokens": 500,
                "duration_ms": 1234,
            }
        )
        _routes_mod._workflow_manager.start_execution.return_value = mock_output

        resp = await client.post(
            "/api/v1/executions",
            json={
                "template": "research",
                "input": {"query": "test query"},
            },
        )
        assert resp.status_code == 200
        _routes_mod._workflow_manager.start_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_executions(self, client):
        """List executions should call repository."""
        _routes_mod._repository.list_executions.return_value = []
        resp = await client.get("/api/v1/executions")
        assert resp.status_code == 200
        _routes_mod._repository.list_executions.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_execution(self, client):
        """Get execution by ID should call repository."""
        mock_exec = MagicMock()
        mock_exec.model_dump = MagicMock(
            return_value={
                "id": "exec-123",
                "status": "completed",
            }
        )
        _routes_mod._repository.get_execution.return_value = mock_exec
        resp = await client.get("/api/v1/executions/exec-123")
        assert resp.status_code == 200
        _routes_mod._repository.get_execution.assert_called_once_with("exec-123")

    @pytest.mark.asyncio
    async def test_get_execution_steps(self, client):
        """Get execution steps should call repository."""
        _routes_mod._repository.get_steps.return_value = []
        resp = await client.get("/api/v1/executions/exec-123/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        _routes_mod._repository.get_steps.assert_called_once_with("exec-123")

    @pytest.mark.asyncio
    async def test_cancel_execution(self, client):
        """Cancel execution should update status via repository."""
        resp = await client.post("/api/v1/executions/exec-123/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        _routes_mod._repository.update_execution.assert_called_once_with("exec-123", status="cancelled")


# ============================================================================
# Not Ready (no dependencies)
# ============================================================================


class TestServiceNotReady:
    @pytest.mark.asyncio
    async def test_start_execution_no_manager(self, no_deps_client):
        """Start execution should return 503 when manager is not available."""
        resp = await no_deps_client.post(
            "/api/v1/executions",
            json={
                "template": "research",
                "input": {"query": "test"},
            },
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_list_executions_no_repo(self, no_deps_client):
        """List executions should return 503 when repository is not available."""
        resp = await no_deps_client.get("/api/v1/executions")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_list_workflows_no_repo(self, no_deps_client):
        """List workflows should return 503 when repository is not available."""
        resp = await no_deps_client.get("/api/v1/workflows")
        assert resp.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
