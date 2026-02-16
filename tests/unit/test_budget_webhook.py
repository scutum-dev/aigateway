"""Unit tests for the Budget Webhook service.

Tests webhook logic, budget checking, alert recording, and notification dispatch.
"""

import sys
import os
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

import pytest

# Load the budget-webhook main module under a unique name to avoid sys.modules collision
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/budget-webhook")
_service_path = os.path.join(_service_dir, "main.py")
sys.path.insert(0, _service_dir)  # needed so notifier import inside main.py works
_spec = importlib.util.spec_from_file_location("budget_webhook_main", _service_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["budget_webhook_main"] = _mod
_spec.loader.exec_module(_mod)

BudgetAlert = _mod.BudgetAlert
WebhookRequest = _mod.WebhookRequest
WebhookResponse = _mod.WebhookResponse


# ============================================================================
# BudgetAlert Model
# ============================================================================


class TestBudgetAlertModel:
    def test_create_alert(self):
        """Should create a valid BudgetAlert."""
        alert = BudgetAlert(
            user_id="user-1",
            team_id="team-1",
            alert_type="approaching_limit",
            threshold_percent=85.0,
            current_spend=85.0,
            budget_limit=100.0,
            message="Approaching limit",
        )
        assert alert.user_id == "user-1"
        assert alert.alert_type == "approaching_limit"
        assert alert.threshold_percent == 85.0

    def test_alert_optional_fields(self):
        """User and team IDs should be optional."""
        alert = BudgetAlert(
            alert_type="budget_exceeded",
            threshold_percent=100.0,
            current_spend=100.0,
            budget_limit=100.0,
            message="Exceeded",
        )
        assert alert.user_id is None
        assert alert.team_id is None


# ============================================================================
# send_notification
# ============================================================================


class TestSendNotification:
    @pytest.mark.asyncio
    async def test_calls_notifier(self):
        """send_notification should delegate to send_all_notifications."""
        alert = BudgetAlert(
            alert_type="approaching_limit",
            threshold_percent=80.0,
            current_spend=80.0,
            budget_limit=100.0,
            message="Warning",
        )

        mock_client = AsyncMock()
        _mod.http_client = mock_client

        with patch("notifier.send_all_notifications", new_callable=AsyncMock) as mock_notify:
            await _mod.send_notification(alert)
            mock_notify.assert_called_once_with(alert, mock_client)


# ============================================================================
# record_alert
# ============================================================================


class TestRecordAlert:
    @pytest.mark.asyncio
    async def test_record_with_db(self):
        """Should insert alert into database."""
        conn = AsyncMock()
        pool = MagicMock()
        # asyncpg pool.acquire() returns an async context manager
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = ctx
        _mod.db_pool = pool

        alert = BudgetAlert(
            user_id="u1",
            alert_type="budget_exceeded",
            threshold_percent=100.0,
            current_spend=100.0,
            budget_limit=100.0,
            message="Exceeded",
        )

        await _mod.record_alert(alert)
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_without_db(self):
        """Should not fail when no database is available."""
        _mod.db_pool = None

        alert = BudgetAlert(
            alert_type="approaching_limit",
            threshold_percent=80.0,
            current_spend=80.0,
            budget_limit=100.0,
            message="Warning",
        )

        # Should not raise
        await _mod.record_alert(alert)


# ============================================================================
# get_budget_info
# ============================================================================


class TestGetBudgetInfo:
    @pytest.mark.asyncio
    async def test_success(self):
        """Should return budget info from LiteLLM."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"max_budget": 100.0, "spend": 50.0}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        _mod.http_client = mock_client

        result = await _mod.get_budget_info("sk-test-key")
        assert result["max_budget"] == 100.0
        assert result["spend"] == 50.0

    @pytest.mark.asyncio
    async def test_failure_returns_empty(self):
        """Should return empty dict on failure."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        _mod.http_client = mock_client

        result = await _mod.get_budget_info("sk-bad-key")
        assert result == {}


# ============================================================================
# predict_cost
# ============================================================================


class TestPredictCost:
    @pytest.mark.asyncio
    async def test_success(self):
        """Should return predicted cost from cost-predictor."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total_estimated_cost_usd": 0.0025}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        _mod.http_client = mock_client

        cost = await _mod.predict_cost("gpt-4o", [{"role": "user", "content": "Hi"}], 100)
        assert cost == 0.0025

    @pytest.mark.asyncio
    async def test_failure_returns_zero(self):
        """Should return 0 when cost prediction fails."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        _mod.http_client = mock_client

        cost = await _mod.predict_cost("gpt-4o", [], None)
        assert cost == 0


# ============================================================================
# Pre-request webhook logic
# ============================================================================


class TestPreRequestLogic:
    def test_webhook_request_model(self):
        """WebhookRequest should parse data correctly."""
        req = WebhookRequest(data={"model": "gpt-4o", "api_key": "sk-test"})
        assert req.data["model"] == "gpt-4o"

    def test_webhook_response_allow(self):
        """WebhookResponse should support allow=True."""
        resp = WebhookResponse(allow=True)
        assert resp.allow is True
        assert resp.message is None

    def test_webhook_response_deny(self):
        """WebhookResponse should support allow=False with message."""
        resp = WebhookResponse(allow=False, message="Over budget")
        assert resp.allow is False
        assert "Over budget" in resp.message
