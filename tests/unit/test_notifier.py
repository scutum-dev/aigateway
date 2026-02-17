"""Unit tests for the Budget Webhook notification dispatcher.

Tests multi-channel alert delivery, retry logic, and severity routing.
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Load the notifier module from src/budget-webhook/notifier.py
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/budget-webhook")
sys.path.insert(0, _service_dir)
_spec = importlib.util.spec_from_file_location(
    "budget_notifier",
    os.path.join(_service_dir, "notifier.py"),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["budget_notifier"] = _mod
_spec.loader.exec_module(_mod)

_send_slack = _mod._send_slack
_send_pagerduty = _mod._send_pagerduty
_send_generic_webhook = _mod._send_generic_webhook
_send_with_retry = _mod._send_with_retry
send_all_notifications = _mod.send_all_notifications
SEVERITY_MAP = _mod.SEVERITY_MAP
SLACK_COLORS = _mod.SLACK_COLORS


def _make_alert(**overrides):
    """Create a mock alert with sensible defaults."""
    defaults = {
        "alert_type": "budget_exceeded",
        "user_id": "user-42",
        "team_id": "team-eng",
        "current_spend": 95.0,
        "budget_limit": 100.0,
        "threshold_percent": 95.0,
        "message": "Budget exceeded for user-42",
    }
    defaults.update(overrides)
    alert = MagicMock()
    for k, v in defaults.items():
        setattr(alert, k, v)
    return alert


# ============================================================================
# SLACK_COLORS constant
# ============================================================================


class TestSlackColors:
    def test_approaching_limit_color(self):
        """Should use yellow/warning for approaching_limit."""
        assert SLACK_COLORS["approaching_limit"] == "#f0ad4e"

    def test_budget_exceeded_color(self):
        """Should use red/critical for budget_exceeded."""
        assert SLACK_COLORS["budget_exceeded"] == "#d9534f"

    def test_request_exceeds_budget_color(self):
        """Should use blue/info for request_exceeds_budget."""
        assert SLACK_COLORS["request_exceeds_budget"] == "#5bc0de"


# ============================================================================
# SEVERITY_MAP constant
# ============================================================================


class TestSeverityMap:
    def test_budget_exceeded_enables_pagerduty(self):
        """Should enable pagerduty for budget_exceeded alerts."""
        assert SEVERITY_MAP["budget_exceeded"]["pagerduty"] is True

    def test_approaching_limit_disables_pagerduty(self):
        """Should not enable pagerduty for approaching_limit alerts."""
        assert SEVERITY_MAP["approaching_limit"]["pagerduty"] is False

    def test_budget_exceeded_enables_all_channels(self):
        """Should enable all channels for budget_exceeded."""
        routing = SEVERITY_MAP["budget_exceeded"]
        assert routing["slack"] is True
        assert routing["email"] is True
        assert routing["pagerduty"] is True
        assert routing["webhook"] is True


# ============================================================================
# _send_slack
# ============================================================================


class TestSendSlack:
    @pytest.mark.asyncio
    async def test_posts_to_slack_webhook(self):
        """Should POST to the configured Slack webhook URL."""
        alert = _make_alert()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch.object(_mod, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/test"):
            await _send_slack(alert, mock_client)

        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert call_url == "https://hooks.slack.com/test"

    @pytest.mark.asyncio
    async def test_payload_has_attachments_with_blocks(self):
        """Should send Block Kit payload with attachments and blocks."""
        alert = _make_alert()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch.object(_mod, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/test"):
            await _send_slack(alert, mock_client)

        payload = mock_client.post.call_args[1]["json"]
        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        attachment = payload["attachments"][0]
        assert "blocks" in attachment
        assert len(attachment["blocks"]) >= 3

    @pytest.mark.asyncio
    async def test_uses_correct_color(self):
        """Should use the color mapped to the alert type."""
        alert = _make_alert(alert_type="approaching_limit")
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch.object(_mod, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/test"):
            await _send_slack(alert, mock_client)

        payload = mock_client.post.call_args[1]["json"]
        assert payload["attachments"][0]["color"] == "#f0ad4e"


# ============================================================================
# _send_pagerduty
# ============================================================================


class TestSendPagerDuty:
    @pytest.mark.asyncio
    async def test_posts_to_pagerduty_url(self):
        """Should POST to the PagerDuty events API endpoint."""
        alert = _make_alert()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch.object(_mod, "PAGERDUTY_ROUTING_KEY", "test-routing-key"):
            await _send_pagerduty(alert, mock_client)

        call_url = mock_client.post.call_args[0][0]
        assert call_url == "https://events.pagerduty.com/v2/enqueue"

    @pytest.mark.asyncio
    async def test_payload_has_routing_key_and_dedup(self):
        """Should include routing_key and dedup_key in payload."""
        alert = _make_alert()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch.object(_mod, "PAGERDUTY_ROUTING_KEY", "test-routing-key"):
            await _send_pagerduty(alert, mock_client)

        payload = mock_client.post.call_args[1]["json"]
        assert payload["routing_key"] == "test-routing-key"
        assert "dedup_key" in payload
        assert "budget-user-42-budget_exceeded" == payload["dedup_key"]

    @pytest.mark.asyncio
    async def test_severity_is_critical(self):
        """Should set PagerDuty severity to critical."""
        alert = _make_alert()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch.object(_mod, "PAGERDUTY_ROUTING_KEY", "key"):
            await _send_pagerduty(alert, mock_client)

        payload = mock_client.post.call_args[1]["json"]
        assert payload["payload"]["severity"] == "critical"


# ============================================================================
# _send_generic_webhook
# ============================================================================


class TestSendGenericWebhook:
    @pytest.mark.asyncio
    async def test_posts_correct_json(self):
        """Should POST alert data as JSON to the webhook URL."""
        alert = _make_alert()
        mock_client = AsyncMock()

        with patch.object(_mod, "ALERT_WEBHOOK_URL", "https://example.com/hook"):
            await _send_generic_webhook(alert, mock_client)

        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert call_url == "https://example.com/hook"
        payload = mock_client.post.call_args[1]["json"]
        assert payload["type"] == "budget_exceeded"
        assert payload["user_id"] == "user-42"
        assert payload["current_spend"] == 95.0
        assert payload["budget_limit"] == 100.0


# ============================================================================
# _send_with_retry
# ============================================================================


class TestSendWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        """Should call fn once and return when it succeeds."""
        fn = AsyncMock()
        await _send_with_retry(fn, "arg1", channel="test")
        fn.assert_called_once_with("arg1")

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        """Should retry when fn raises, then succeed."""
        fn = AsyncMock(side_effect=[RuntimeError("fail"), None])

        with patch.object(_mod.asyncio, "sleep", new_callable=AsyncMock):
            await _send_with_retry(fn, channel="test", max_retries=3)

        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self):
        """Should stop retrying after max_retries attempts."""
        fn = AsyncMock(side_effect=RuntimeError("always fails"))

        with patch.object(_mod.asyncio, "sleep", new_callable=AsyncMock):
            await _send_with_retry(fn, channel="test", max_retries=3)

        assert fn.call_count == 3


# ============================================================================
# send_all_notifications
# ============================================================================


class TestSendAllNotifications:
    @pytest.mark.asyncio
    async def test_dispatches_all_channels_for_budget_exceeded(self):
        """Should dispatch to all channels when budget_exceeded and all configured."""
        alert = _make_alert(alert_type="budget_exceeded")
        mock_client = AsyncMock()

        with (
            patch.object(_mod, "SLACK_WEBHOOK_URL", "https://slack"),
            patch.object(_mod, "PAGERDUTY_ROUTING_KEY", "pd-key"),
            patch.object(_mod, "SMTP_HOST", "smtp.test.com"),
            patch.object(_mod, "SMTP_ALERT_RECIPIENTS", "a@b.com"),
            patch.object(_mod, "ALERT_WEBHOOK_URL", "https://webhook"),
            patch.object(_mod, "_send_with_retry", new_callable=AsyncMock) as mock_retry,
        ):
            await send_all_notifications(alert, mock_client)

        # budget_exceeded enables all 4 channels
        assert mock_retry.call_count == 4

    @pytest.mark.asyncio
    async def test_skips_unconfigured_channels(self):
        """Should skip channels with empty URL/key."""
        alert = _make_alert(alert_type="budget_exceeded")
        mock_client = AsyncMock()

        with (
            patch.object(_mod, "SLACK_WEBHOOK_URL", "https://slack"),
            patch.object(_mod, "PAGERDUTY_ROUTING_KEY", ""),
            patch.object(_mod, "SMTP_HOST", ""),
            patch.object(_mod, "SMTP_ALERT_RECIPIENTS", ""),
            patch.object(_mod, "ALERT_WEBHOOK_URL", ""),
            patch.object(_mod, "_send_with_retry", new_callable=AsyncMock) as mock_retry,
        ):
            await send_all_notifications(alert, mock_client)

        # Only Slack is configured
        assert mock_retry.call_count == 1

    @pytest.mark.asyncio
    async def test_no_channels_logs_only(self):
        """Should log and return when no channels are configured."""
        alert = _make_alert(alert_type="budget_exceeded")
        mock_client = AsyncMock()

        with (
            patch.object(_mod, "SLACK_WEBHOOK_URL", ""),
            patch.object(_mod, "PAGERDUTY_ROUTING_KEY", ""),
            patch.object(_mod, "SMTP_HOST", ""),
            patch.object(_mod, "SMTP_ALERT_RECIPIENTS", ""),
            patch.object(_mod, "ALERT_WEBHOOK_URL", ""),
            patch.object(_mod, "_send_with_retry", new_callable=AsyncMock) as mock_retry,
        ):
            await send_all_notifications(alert, mock_client)

        mock_retry.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
