"""Unit tests for the event publisher utility (event_publisher.py).

Tests the fire-and-forget publish_event function, verifying:
- Event inserted into event_log table
- Webhook and Slack subscription dispatch
- Graceful handling of missing DB pool and dispatch errors
- Inactive / unmatched subscriptions are not dispatched
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

from event_publisher import publish_event  # noqa: E402

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


def _make_subscription(name, channel, config, is_active=True, event_types=None):
    """Build a dict-like mock subscription row."""
    sub = {
        "name": name,
        "channel": channel,
        "config": json.dumps(config) if isinstance(config, dict) else config,
        "is_active": is_active,
        "event_types": event_types or ["model.created"],
    }
    return sub


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEventPublisher:
    """Tests for event_publisher.publish_event."""

    @pytest.mark.asyncio
    async def test_event_inserted_into_log(self):
        """Verify INSERT called with event_type, payload (json), source_service."""
        conn = _make_async_conn()
        pool = _make_pool(conn)

        await publish_event(
            db_pool=pool,
            event_type="model.created",
            payload={"model_id": "m-1", "name": "gpt-4o"},
            source_service="admin-api",
        )

        conn.execute.assert_awaited_once()
        args = conn.execute.call_args[0]
        assert args[1] == "model.created"
        assert json.loads(args[2]) == {"model_id": "m-1", "name": "gpt-4o"}
        assert args[3] == "admin-api"

    @pytest.mark.asyncio
    async def test_webhook_subscription_dispatched(self):
        """Active webhook sub with matching event_type — verify http_client.post called."""
        sub = _make_subscription(
            name="notify-ops",
            channel="webhook",
            config={"url": "https://hooks.example.com/events"},
        )
        conn = _make_async_conn(fetch_return=[sub])
        pool = _make_pool(conn)
        http_client = AsyncMock()

        await publish_event(
            db_pool=pool,
            event_type="model.created",
            payload={"model_id": "m-2"},
            http_client=http_client,
        )

        http_client.post.assert_awaited_once()
        call_args = http_client.post.call_args
        assert call_args[0][0] == "https://hooks.example.com/events"
        body = call_args[1]["json"]
        assert body["event_type"] == "model.created"
        assert body["payload"] == {"model_id": "m-2"}
        assert body["subscription"] == "notify-ops"
        assert call_args[1]["timeout"] == 10.0

    @pytest.mark.asyncio
    async def test_slack_subscription_dispatched(self):
        """Active slack sub — verify http_client.post called with slack payload."""
        sub = _make_subscription(
            name="slack-alerts",
            channel="slack",
            config={"webhook_url": "https://hooks.slack.com/services/T/B/X"},
        )
        conn = _make_async_conn(fetch_return=[sub])
        pool = _make_pool(conn)
        http_client = AsyncMock()

        await publish_event(
            db_pool=pool,
            event_type="budget.exceeded",
            payload={"org_id": "org-1", "spent": 150.0},
            http_client=http_client,
        )

        http_client.post.assert_awaited_once()
        call_args = http_client.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/services/T/B/X"
        body = call_args[1]["json"]
        assert "text" in body
        assert "budget.exceeded" in body["text"]

    @pytest.mark.asyncio
    async def test_no_matching_subscriptions(self):
        """conn.fetch returns empty list — verify no dispatch (http_client.post not called)."""
        conn = _make_async_conn(fetch_return=[])
        pool = _make_pool(conn)
        http_client = AsyncMock()

        await publish_event(
            db_pool=pool,
            event_type="model.deleted",
            payload={"model_id": "m-3"},
            http_client=http_client,
        )

        http_client.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_http_client_skips_dispatch(self):
        """Webhook subscription exists but http_client is None — no dispatch attempt."""
        sub = _make_subscription(
            name="webhook-no-client",
            channel="webhook",
            config={"url": "https://hooks.example.com/events"},
        )
        conn = _make_async_conn(fetch_return=[sub])
        pool = _make_pool(conn)

        # Should not raise even though there are matching subs
        await publish_event(
            db_pool=pool,
            event_type="model.created",
            payload={"model_id": "m-4"},
            http_client=None,
        )

    @pytest.mark.asyncio
    async def test_missing_db_pool(self):
        """db_pool is None — returns immediately without error."""
        # Should not raise
        await publish_event(
            db_pool=None,
            event_type="model.created",
            payload={"model_id": "m-5"},
        )

    @pytest.mark.asyncio
    async def test_dispatch_error_no_raise(self):
        """http_client.post raises — exception caught, does not propagate."""
        sub = _make_subscription(
            name="flaky-webhook",
            channel="webhook",
            config={"url": "https://hooks.example.com/flaky"},
        )
        conn = _make_async_conn(fetch_return=[sub])
        pool = _make_pool(conn)
        http_client = AsyncMock()
        http_client.post.side_effect = Exception("Connection refused")

        # Should not raise
        await publish_event(
            db_pool=pool,
            event_type="model.created",
            payload={"model_id": "m-6"},
            http_client=http_client,
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
