"""Integration tests for the Teams Admin API endpoints.

Tests CRUD operations for teams including update and delete.
"""

import sys
import os
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import httpx

# Load the admin-api module
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

# Mock heavy dependencies before importing
for mod_name in [
    "redis.asyncio", "jwt",
    "opentelemetry", "opentelemetry.trace",
    "opentelemetry.instrumentation.fastapi",
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    "opentelemetry.sdk.trace", "opentelemetry.sdk.trace.export",
    "opentelemetry.sdk.resources",
    "alembic", "alembic.config", "alembic.command",
    "passlib", "passlib.context",
]:
    sys.modules.setdefault(mod_name, MagicMock())

import deps
from auth import get_current_user, require_admin
from routers.teams import router

from fastapi import FastAPI
from fastapi.testclient import TestClient

_fake_user = MagicMock(user_id="admin", role="admin")

test_app = FastAPI()
test_app.dependency_overrides[get_current_user] = lambda: _fake_user
test_app.dependency_overrides[require_admin] = lambda: _fake_user
test_app.include_router(router, prefix="/api/v1")


SAMPLE_TEAM_ROW = {
    "id": uuid4(),
    "name": "engineering",
    "description": "Engineering team",
    "monthly_budget": 500.00,
    "default_model": "gpt-4o",
    "is_active": True,
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
}


@pytest.fixture
def mock_pool():
    conn = AsyncMock()
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx
    original = deps.db_pool
    deps.db_pool = pool
    yield pool, conn
    deps.db_pool = original


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=test_app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


class TestUpdateTeam:
    @pytest.mark.asyncio
    async def test_update_success(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = SAMPLE_TEAM_ROW
        conn.fetch.return_value = []  # no members
        resp = await client.put(f"/api/v1/teams/{SAMPLE_TEAM_ROW['id']}", json={
            "name": "eng-updated",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "engineering"  # from mock row

    @pytest.mark.asyncio
    async def test_update_empty_body(self, client, mock_pool):
        resp = await client.put(f"/api/v1/teams/{uuid4()}", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_not_found(self, client, mock_pool):
        _, conn = mock_pool
        conn.fetchrow.return_value = None
        resp = await client.put(f"/api/v1/teams/{uuid4()}", json={"name": "x"})
        assert resp.status_code == 404


class TestDeleteTeam:
    @pytest.mark.asyncio
    async def test_delete_success(self, client, mock_pool):
        _, conn = mock_pool
        conn.execute.return_value = "DELETE 1"
        resp = await client.delete(f"/api/v1/teams/{SAMPLE_TEAM_ROW['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client, mock_pool):
        _, conn = mock_pool
        conn.execute.return_value = "DELETE 0"
        resp = await client.delete(f"/api/v1/teams/{uuid4()}")
        assert resp.status_code == 404
