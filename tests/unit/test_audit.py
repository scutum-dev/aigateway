"""Unit tests for the audit trail utility (audit.py).

Tests the fire-and-forget log_audit_event function, verifying:
- Correct SQL INSERT with all arguments
- Request metadata extraction (method, path, user_agent, client IP)
- Graceful handling of missing DB pool, missing request, SQL errors
- JSON serialisation of changes and request_metadata
"""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup — make admin-api importable
# ---------------------------------------------------------------------------

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

import deps  # noqa: E402
from audit import log_audit_event  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_async_conn(fetch_return=None, fetchrow_return=None, execute_return=None):
    """Build a mock asyncpg connection with configurable return values."""
    conn = AsyncMock()
    conn.fetch.return_value = fetch_return if fetch_return is not None else []
    conn.fetchrow.return_value = fetchrow_return
    conn.execute.return_value = execute_return or "INSERT 1"
    return conn


def _make_pool(conn):
    """Wrap a mock connection in a pool that supports `async with pool.acquire()`."""
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = None
    pool.acquire.return_value = ctx
    return pool


def _make_request(method="POST", path="/api/v1/models", user_agent="TestAgent/1.0", client_host="10.0.0.1"):
    """Build a minimal mock FastAPI Request."""
    req = MagicMock()
    req.method = method
    req.url.path = path
    req.headers.get.side_effect = lambda key, default="": user_agent if key == "user-agent" else default
    if client_host is not None:
        req.client.host = client_host
    else:
        req.client = None
    return req


@pytest.fixture(autouse=True)
def _reset_deps():
    """Ensure deps.db_pool is clean before and after each test."""
    original_pool = deps.db_pool
    yield
    deps.db_pool = original_pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAudit:
    """Tests for audit.log_audit_event."""

    @pytest.mark.asyncio
    async def test_successful_audit_insert(self):
        """All fields populated — verify conn.execute called with correct SQL and args."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)
        req = _make_request()

        await log_audit_event(
            actor_id="user-1",
            action="create",
            resource_type="model",
            resource_id="model-42",
            resource_name="gpt-4o",
            changes={"field": "name", "old": "gpt-4", "new": "gpt-4o"},
            request=req,
            org_id="org-abc",
            actor_email="admin@example.com",
        )

        conn.execute.assert_awaited_once()
        args = conn.execute.call_args[0]
        # Positional args after the SQL string
        assert args[1] == "user-1"  # actor_id
        assert args[2] == "admin@example.com"  # actor_email
        assert args[3] == "10.0.0.1"  # actor_ip
        assert args[4] == "org-abc"  # org_id
        assert args[5] == "create"  # action
        assert args[6] == "model"  # resource_type
        assert args[7] == "model-42"  # resource_id
        assert args[8] == "gpt-4o"  # resource_name
        assert json.loads(args[9]) == {"field": "name", "old": "gpt-4", "new": "gpt-4o"}
        metadata = json.loads(args[10])
        assert metadata["method"] == "POST"
        assert metadata["path"] == "/api/v1/models"
        assert metadata["user_agent"] == "TestAgent/1.0"

    @pytest.mark.asyncio
    async def test_request_metadata_extraction(self):
        """Verify method, path, user_agent and client IP are extracted from the request."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)
        req = _make_request(
            method="DELETE", path="/api/v1/keys/k1", user_agent="Mozilla/5.0", client_host="192.168.1.1"
        )

        await log_audit_event(
            actor_id="user-2",
            action="delete",
            resource_type="api_key",
            request=req,
        )

        args = conn.execute.call_args[0]
        assert args[3] == "192.168.1.1"  # actor_ip
        assert args[4] is None  # org_id not passed
        metadata = json.loads(args[10])
        assert metadata["method"] == "DELETE"
        assert metadata["path"] == "/api/v1/keys/k1"
        assert metadata["user_agent"] == "Mozilla/5.0"

    @pytest.mark.asyncio
    async def test_none_request(self):
        """No request passed — actor_ip should be None, request_metadata should be empty."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        await log_audit_event(
            actor_id="user-3",
            action="update",
            resource_type="setting",
        )

        args = conn.execute.call_args[0]
        # arg order: SQL, actor_id, actor_email, actor_ip, org_id, action, ...
        assert args[2] is None  # actor_email (not passed)
        assert args[3] is None  # actor_ip (no request)
        assert json.loads(args[10]) == {}  # empty request_metadata

    @pytest.mark.asyncio
    async def test_missing_db_pool(self):
        """deps.db_pool is None — returns without error."""
        deps.db_pool = None

        # Should not raise
        await log_audit_event(
            actor_id="user-4",
            action="create",
            resource_type="org",
        )

    @pytest.mark.asyncio
    async def test_sql_error_no_raise(self):
        """conn.execute raises — exception is caught, does not propagate."""
        conn = _make_async_conn()
        conn.execute.side_effect = Exception("DB connection lost")
        deps.db_pool = _make_pool(conn)

        # Should not raise
        await log_audit_event(
            actor_id="user-5",
            action="delete",
            resource_type="model",
        )

    @pytest.mark.asyncio
    async def test_none_optional_fields(self):
        """resource_id=None, org_id=None — verify they arrive as None in the INSERT."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        await log_audit_event(
            actor_id="user-6",
            action="list",
            resource_type="models",
            resource_id=None,
            org_id=None,
        )

        args = conn.execute.call_args[0]
        assert args[4] is None  # org_id
        assert args[7] is None  # resource_id
        assert args[8] is None  # resource_name

    @pytest.mark.asyncio
    async def test_changes_serialized_as_json(self):
        """Verify changes dict is serialised via json.dumps."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)
        changes = {"before": {"rate_limit": 100}, "after": {"rate_limit": 200}}

        await log_audit_event(
            actor_id="user-7",
            action="update",
            resource_type="rate_limit",
            changes=changes,
        )

        args = conn.execute.call_args[0]
        assert args[9] == json.dumps(changes)
        assert json.loads(args[9]) == changes

    @pytest.mark.asyncio
    async def test_empty_changes(self):
        """changes=None becomes '{}' after json.dumps."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        await log_audit_event(
            actor_id="user-8",
            action="read",
            resource_type="audit_logs",
            changes=None,
        )

        args = conn.execute.call_args[0]
        assert args[9] == "{}"

    @pytest.mark.asyncio
    async def test_request_without_client(self):
        """request.client is None — actor_ip should be None."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)
        req = _make_request(client_host=None)  # sets req.client = None

        await log_audit_event(
            actor_id="user-9",
            action="update",
            resource_type="sso_provider",
            request=req,
        )

        args = conn.execute.call_args[0]
        assert args[3] is None  # actor_ip (request.client is None)

    @pytest.mark.asyncio
    async def test_actor_email_passed(self):
        """Verify actor_email is correctly passed to the INSERT."""
        conn = _make_async_conn()
        deps.db_pool = _make_pool(conn)

        await log_audit_event(
            actor_id="user-10",
            action="create",
            resource_type="user",
            actor_email="alice@corp.com",
        )

        args = conn.execute.call_args[0]
        assert args[1] == "user-10"  # actor_id
        assert args[2] == "alice@corp.com"  # actor_email


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
