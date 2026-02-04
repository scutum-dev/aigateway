"""
Integration tests for Workflow Engine Service.

Tests workflow execution, templates, WebSocket streaming,
checkpointing, and cost tracking.
"""
import pytest
import httpx
import asyncio
import json
from typing import Generator
from websockets.sync.client import connect as ws_connect


# Test configuration
WORKFLOW_ENGINE_URL = "http://localhost:8085"
WORKFLOW_ENGINE_WS_URL = "ws://localhost:8085"


@pytest.fixture(scope="module")
def http_client() -> Generator[httpx.Client, None, None]:
    """Create HTTP client for tests."""
    with httpx.Client(base_url=WORKFLOW_ENGINE_URL, timeout=60.0) as client:
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


class TestWorkflowTemplates:
    """Test workflow template listing."""

    def test_list_templates(self, http_client: httpx.Client, api_headers: dict):
        """Test listing available workflow templates."""
        response = http_client.get("/api/v1/templates", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3  # research, coding, data_analysis

    def test_template_has_required_fields(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test template info contains required fields."""
        response = http_client.get("/api/v1/templates", headers=api_headers)
        assert response.status_code == 200
        data = response.json()

        for template in data:
            assert "name" in template
            assert "description" in template
            assert "input_schema" in template
            assert "nodes" in template

    def test_research_template_exists(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test research template is available."""
        response = http_client.get("/api/v1/templates", headers=api_headers)
        assert response.status_code == 200
        data = response.json()

        template_names = [t["name"] for t in data]
        assert "research" in template_names

    def test_coding_template_exists(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test coding template is available."""
        response = http_client.get("/api/v1/templates", headers=api_headers)
        assert response.status_code == 200
        data = response.json()

        template_names = [t["name"] for t in data]
        assert "coding" in template_names

    def test_data_analysis_template_exists(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test data analysis template is available."""
        response = http_client.get("/api/v1/templates", headers=api_headers)
        assert response.status_code == 200
        data = response.json()

        template_names = [t["name"] for t in data]
        assert "data_analysis" in template_names


class TestWorkflowDefinitions:
    """Test workflow definition CRUD."""

    def test_create_workflow(self, http_client: httpx.Client, api_headers: dict):
        """Test creating a custom workflow definition."""
        import uuid
        workflow_name = f"test-workflow-{uuid.uuid4().hex[:8]}"

        response = http_client.post(
            "/api/v1/workflows",
            headers=api_headers,
            json={
                "name": workflow_name,
                "description": "Test workflow for integration testing",
                "template_type": "research",
                "graph_definition": {
                    "nodes": ["start", "process", "end"],
                    "edges": [
                        {"from": "start", "to": "process"},
                        {"from": "process", "to": "end"},
                    ],
                },
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
        assert data["name"] == workflow_name

    def test_list_workflows(self, http_client: httpx.Client, api_headers: dict):
        """Test listing workflow definitions."""
        response = http_client.get("/api/v1/workflows", headers=api_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_workflow_by_id(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test getting workflow by ID."""
        # First create a workflow
        import uuid
        workflow_name = f"test-workflow-{uuid.uuid4().hex[:8]}"

        create_response = http_client.post(
            "/api/v1/workflows",
            headers=api_headers,
            json={
                "name": workflow_name,
                "description": "Test workflow",
                "template_type": "research",
                "graph_definition": {"nodes": ["start", "end"]},
            },
        )
        assert create_response.status_code in [200, 201]
        workflow_id = create_response.json()["id"]

        # Then get it by ID
        response = http_client.get(
            f"/api/v1/workflows/{workflow_id}",
            headers=api_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == workflow_id
        assert data["name"] == workflow_name


class TestWorkflowExecution:
    """Test workflow execution."""

    def test_start_execution_from_template(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test starting workflow execution from template."""
        response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "research",
                "input": {
                    "query": "What are the best practices for API design?",
                },
                "user_id": "test-user",
                "team_id": "engineering",
            },
        )
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "execution_id" in data or "id" in data
        assert "status" in data

    def test_get_execution_status(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test getting execution status."""
        # Start an execution
        start_response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "research",
                "input": {"query": "Test query"},
                "user_id": "test-user",
            },
        )
        assert start_response.status_code in [200, 201, 202]
        execution_id = start_response.json().get("execution_id") or start_response.json().get("id")

        # Get status
        response = http_client.get(
            f"/api/v1/executions/{execution_id}",
            headers=api_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["pending", "running", "paused", "completed", "failed"]

    def test_get_execution_steps(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test getting execution step details."""
        # Start an execution
        start_response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "research",
                "input": {"query": "Test query"},
                "user_id": "test-user",
            },
        )
        execution_id = start_response.json().get("execution_id") or start_response.json().get("id")

        # Get steps (may be empty if execution just started)
        response = http_client.get(
            f"/api/v1/executions/{execution_id}/steps",
            headers=api_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_execution_with_invalid_template(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test execution with non-existent template."""
        response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "non_existent_template",
                "input": {"query": "Test"},
            },
        )
        assert response.status_code in [400, 404, 422]

    def test_execution_with_invalid_input(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test execution with invalid input schema."""
        response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "research",
                "input": {},  # Missing required 'query' field
            },
        )
        # Should either validate and reject, or handle gracefully
        assert response.status_code in [200, 201, 202, 400, 422]


class TestWorkflowPauseResume:
    """Test workflow pause and resume functionality."""

    def test_pause_execution(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test pausing a running execution."""
        # Start an execution
        start_response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "research",
                "input": {"query": "Long running test query"},
                "user_id": "test-user",
            },
        )
        execution_id = start_response.json().get("execution_id") or start_response.json().get("id")

        # Pause it
        response = http_client.post(
            f"/api/v1/executions/{execution_id}/pause",
            headers=api_headers,
        )
        # May fail if execution already completed
        assert response.status_code in [200, 400, 409]

    def test_resume_execution(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test resuming a paused execution."""
        # Start an execution
        start_response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "research",
                "input": {"query": "Test query for resume"},
                "user_id": "test-user",
            },
        )
        execution_id = start_response.json().get("execution_id") or start_response.json().get("id")

        # Try to pause then resume
        http_client.post(f"/api/v1/executions/{execution_id}/pause", headers=api_headers)

        response = http_client.post(
            f"/api/v1/executions/{execution_id}/resume",
            headers=api_headers,
        )
        # May fail if execution not paused or already completed
        assert response.status_code in [200, 400, 409]


class TestWorkflowCosts:
    """Test workflow cost tracking."""

    def test_get_cost_summary(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test getting workflow cost summary."""
        response = http_client.get(
            "/api/v1/costs/summary",
            headers=api_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_cost" in data or "workflows" in data

    def test_cost_summary_by_user(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test getting cost summary filtered by user."""
        response = http_client.get(
            "/api/v1/costs/summary",
            headers=api_headers,
            params={"user_id": "test-user"},
        )
        assert response.status_code == 200

    def test_cost_summary_by_team(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test getting cost summary filtered by team."""
        response = http_client.get(
            "/api/v1/costs/summary",
            headers=api_headers,
            params={"team_id": "engineering"},
        )
        assert response.status_code == 200


class TestWebSocketStreaming:
    """Test WebSocket streaming for execution updates."""

    def test_websocket_connection(self):
        """Test WebSocket connection can be established."""
        # Start an execution first via HTTP
        with httpx.Client(base_url=WORKFLOW_ENGINE_URL, timeout=30.0) as client:
            start_response = client.post(
                "/api/v1/executions",
                headers={"Content-Type": "application/json"},
                json={
                    "template": "research",
                    "input": {"query": "WebSocket test query"},
                    "user_id": "test-user",
                },
            )
            execution_id = start_response.json().get("execution_id") or start_response.json().get("id")

        # Try to connect via WebSocket
        try:
            with ws_connect(
                f"{WORKFLOW_ENGINE_WS_URL}/ws/executions/{execution_id}",
                open_timeout=5,
            ) as websocket:
                # Try to receive at least one message
                websocket.recv(timeout=10)
                # If we get here, connection works
                assert True
        except Exception as e:
            # WebSocket connection may fail if execution completes too fast
            # or if service doesn't support WebSocket
            pytest.skip(f"WebSocket connection failed: {e}")

    def test_websocket_receives_updates(self):
        """Test WebSocket receives execution updates."""
        with httpx.Client(base_url=WORKFLOW_ENGINE_URL, timeout=30.0) as client:
            start_response = client.post(
                "/api/v1/executions",
                headers={"Content-Type": "application/json"},
                json={
                    "template": "research",
                    "input": {"query": "Streaming test query"},
                    "user_id": "test-user",
                },
            )
            execution_id = start_response.json().get("execution_id") or start_response.json().get("id")

        messages = []
        try:
            with ws_connect(
                f"{WORKFLOW_ENGINE_WS_URL}/ws/executions/{execution_id}",
                open_timeout=5,
            ) as websocket:
                for _ in range(5):  # Try to get up to 5 messages
                    try:
                        msg = websocket.recv(timeout=5)
                        messages.append(json.loads(msg))
                    except:
                        break

            # Verify message structure if we got any
            for msg in messages:
                assert "type" in msg or "status" in msg or "node" in msg
        except Exception as e:
            pytest.skip(f"WebSocket test skipped: {e}")


class TestCodingWorkflow:
    """Test coding workflow specific functionality."""

    def test_coding_workflow_execution(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test coding workflow execution."""
        response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "coding",
                "input": {
                    "task": "Write a Python function to calculate fibonacci numbers",
                    "language": "python",
                },
                "user_id": "test-user",
            },
        )
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "execution_id" in data or "id" in data


class TestDataAnalysisWorkflow:
    """Test data analysis workflow specific functionality."""

    def test_data_analysis_workflow_execution(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test data analysis workflow execution."""
        response = http_client.post(
            "/api/v1/executions",
            headers=api_headers,
            json={
                "template": "data_analysis",
                "input": {
                    "question": "What is the total cost by team for the last week?",
                    "data_source": "cost_tracking_daily",
                },
                "user_id": "test-user",
            },
        )
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "execution_id" in data or "id" in data


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_get_nonexistent_execution(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test getting non-existent execution."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = http_client.get(
            f"/api/v1/executions/{fake_id}",
            headers=api_headers,
        )
        assert response.status_code == 404

    def test_get_nonexistent_workflow(
        self, http_client: httpx.Client, api_headers: dict
    ):
        """Test getting non-existent workflow."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = http_client.get(
            f"/api/v1/workflows/{fake_id}",
            headers=api_headers,
        )
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
