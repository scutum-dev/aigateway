"""Integration tests for the FinOps Reporter API.

Tests HTTP endpoints and ServiceAuthMiddleware via ASGI test client.
"""

import os
import importlib.util
from unittest.mock import AsyncMock, MagicMock
from datetime import date
from decimal import Decimal

import pytest
import httpx

# Load the finops-reporter module
_service_path = os.path.join(os.path.dirname(__file__), "../../src/finops-reporter/main.py")
_spec = importlib.util.spec_from_file_location("finops_reporter_integ", _service_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

app = _mod.app

SERVICE_KEY = "test-integration-key"


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module state between tests."""
    original_key = _mod.INTERNAL_SERVICE_KEY
    original_db = _mod.db_pool
    yield
    _mod.INTERNAL_SERVICE_KEY = original_key
    _mod.db_pool = original_db


def _mock_db_pool(conn):
    """Create a mock asyncpg pool wrapping a mock connection."""
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx
    return pool


@pytest.fixture
def client():
    """ASGI test client (dev mode)."""
    _mod.INTERNAL_SERVICE_KEY = ""
    _mod.db_pool = None
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def authed_client():
    """ASGI test client with auth required."""
    _mod.INTERNAL_SERVICE_KEY = SERVICE_KEY
    _mod.db_pool = None
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
    async def test_reject_without_key(self, authed_client):
        """Protected endpoint should return 401."""
        resp = await authed_client.get("/reports/budget-utilization")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_accept_correct_key(self, authed_client):
        """Protected endpoint should work with correct key."""
        resp = await authed_client.get(
            "/reports/budget-utilization",
            headers={"X-Service-Key": SERVICE_KEY}
        )
        assert resp.status_code == 200


# ============================================================================
# /health
# ============================================================================


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_with_db(self, client):
        _mod.db_pool = MagicMock()
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] is True

    @pytest.mark.asyncio
    async def test_health_without_db(self, client):
        _mod.db_pool = None
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database"] is False


# ============================================================================
# /reports/cost
# ============================================================================


class TestCostReportEndpoint:
    @pytest.mark.asyncio
    async def test_no_database(self, client):
        """Should return 503 when no database."""
        resp = await client.get("/reports/cost")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_daily_report(self, client):
        """Should return daily cost report."""
        conn = AsyncMock()
        today = date.today()

        # Mock totals
        conn.fetchrow.return_value = {
            "total_requests": 100,
            "total_input_tokens": 50000,
            "total_output_tokens": 20000,
            "total_cost": Decimal("5.50"),
        }
        # Mock breakdowns (model, user, team)
        conn.fetch.return_value = []

        _mod.db_pool = _mock_db_pool(conn)

        resp = await client.get("/reports/cost", params={"period": "daily"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "daily"
        assert data["total_cost"] == 5.50
        assert data["total_requests"] == 100


# ============================================================================
# /reports/trend
# ============================================================================


class TestTrendEndpoint:
    @pytest.mark.asyncio
    async def test_no_database(self, client):
        """Should return 503 when no database."""
        resp = await client.get("/reports/trend")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_trend_data(self, client):
        """Should return trend analysis."""
        conn = AsyncMock()

        # Return 10 days of mock data
        rows = []
        for i in range(10):
            d = date(2025, 1, i + 1)
            row = MagicMock()
            row.__getitem__ = lambda self, key, i=i, d=d: {
                "date": d,
                "cost": Decimal(str(float(i + 1))),
                "requests": 10,
                "tokens": 1000,
            }[key]
            rows.append(row)

        conn.fetch.return_value = rows
        _mod.db_pool = _mock_db_pool(conn)

        resp = await client.get("/reports/trend", params={"days": 30})
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "last_30_days"
        assert len(data["data_points"]) == 10
        assert data["trend_direction"] in ("increasing", "decreasing", "stable")


# ============================================================================
# /reports/budget-utilization
# ============================================================================


class TestBudgetUtilizationEndpoint:
    @pytest.mark.asyncio
    async def test_returns_placeholder(self, client):
        """Should return placeholder data."""
        resp = await client.get("/reports/budget-utilization")
        assert resp.status_code == 200
        data = resp.json()
        assert "utilization" in data


# ============================================================================
# /reports/export
# ============================================================================


class TestExportEndpoint:
    @pytest.mark.asyncio
    async def test_no_database(self, client):
        """Should return 503 when no database."""
        resp = await client.get("/reports/export")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_csv_export(self, client):
        """Should return CSV with correct headers."""
        conn = AsyncMock()
        row = MagicMock()
        row.__getitem__ = lambda self, key: {
            "date": date(2025, 1, 1),
            "user_id": "user-1",
            "team_id": "team-1",
            "model": "gpt-4o",
            "request_count": 10,
            "input_tokens": 5000,
            "output_tokens": 2000,
            "total_cost": Decimal("0.05"),
        }[key]
        conn.fetch.return_value = [row]
        _mod.db_pool = _mock_db_pool(conn)

        resp = await client.get("/reports/export", params={"format": "csv"})
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "date" in content
        assert "gpt-4o" in content

    @pytest.mark.asyncio
    async def test_json_export(self, client):
        """Should return JSON export."""
        conn = AsyncMock()
        row = MagicMock()
        row_data = {
            "date": date(2025, 1, 1),
            "user_id": "user-1",
            "team_id": "team-1",
            "model": "gpt-4o",
            "request_count": 10,
            "input_tokens": 5000,
            "output_tokens": 2000,
            "total_cost": Decimal("0.05"),
        }
        row.__getitem__ = lambda self, key: row_data[key]
        row.keys = lambda: row_data.keys()
        row.values = lambda: row_data.values()
        row.items = lambda: row_data.items()

        def dict_from_row(r=row):
            return dict(row_data)
        # asyncpg records support dict()
        conn.fetch.return_value = [MagicMock(__iter__=lambda s: iter(row_data.items()), keys=lambda: row_data.keys())]

        # Simpler approach: mock at the dict(row) level
        class FakeRow:
            def __getitem__(self, key):
                return row_data[key]
            def keys(self):
                return row_data.keys()
            def values(self):
                return row_data.values()
            def items(self):
                return row_data.items()
            def __iter__(self):
                return iter(row_data)

        conn.fetch.return_value = [FakeRow()]
        _mod.db_pool = _mock_db_pool(conn)

        resp = await client.get("/reports/export", params={"format": "json"})
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]


# ============================================================================
# /reports/summary
# ============================================================================


class TestSummaryEndpoint:
    @pytest.mark.asyncio
    async def test_no_database(self, client):
        """Should return 503 when no database."""
        resp = await client.get("/reports/summary")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_summary_stats(self, client):
        """Should return summary statistics."""
        conn = AsyncMock()

        # Mock fetchrow for today/week/month stats
        stats_row = MagicMock()
        stats_row.__getitem__ = lambda self, key: {"cost": Decimal("10.00"), "requests": 50}[key]
        conn.fetchrow.return_value = stats_row

        # Mock fetch for top models
        model_row = MagicMock()
        model_row.__getitem__ = lambda self, key: {"model": "gpt-4o", "cost": Decimal("8.00")}[key]
        conn.fetch.return_value = [model_row]

        _mod.db_pool = _mock_db_pool(conn)

        resp = await client.get("/reports/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "today" in data
        assert "this_week" in data
        assert "this_month" in data
        assert "top_models" in data
