"""Unit tests for landing-backend.

Loads the service modules under unique sys.modules names to avoid colliding
with budget-webhook (which also defines storage/email helpers under bare
names). Same teardown pattern as the SRE agent tests.
"""

import importlib.util
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "../../src/landing-backend")
sys.path.insert(0, _SERVICE_DIR)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_SERVICE_DIR, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_calcom = _load("calcom")
_email_sender = _load("email_sender")
_storage = _load("storage")

# Cleanup so other test modules' bare-name imports stay intact.
for _n in ("calcom", "email_sender", "storage"):
    sys.modules.pop(_n, None)
if _SERVICE_DIR in sys.path:
    sys.path.remove(_SERVICE_DIR)


# ============================================================================
# Cal.com client
# ============================================================================


class TestCalcomClient:
    def test_is_configured_false_without_env(self, monkeypatch):
        monkeypatch.setattr(_calcom, "CALCOM_API_KEY", "")
        monkeypatch.setattr(_calcom, "CALCOM_EVENT_TYPE_ID", "")
        assert _calcom.is_configured() is False

    def test_is_configured_true_with_env(self, monkeypatch):
        monkeypatch.setattr(_calcom, "CALCOM_API_KEY", "k")
        monkeypatch.setattr(_calcom, "CALCOM_EVENT_TYPE_ID", "1")
        assert _calcom.is_configured() is True

    @pytest.mark.asyncio
    async def test_get_availability_returns_empty_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(_calcom, "CALCOM_API_KEY", "")
        result = await _calcom.get_availability(AsyncMock(), "2026-05-02", "2026-05-09")
        assert result["configured"] is False
        assert result["slots"] == []

    @pytest.mark.asyncio
    async def test_create_booking_no_op_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(_calcom, "CALCOM_API_KEY", "")
        result = await _calcom.create_booking(
            AsyncMock(),
            name="Test",
            email="t@x.com",
            start_iso="2026-05-02T10:00:00Z",
            end_iso="2026-05-02T10:30:00Z",
        )
        assert result["ok"] is False
        assert result["configured"] is False

    @pytest.mark.asyncio
    async def test_create_booking_success(self, monkeypatch):
        monkeypatch.setattr(_calcom, "CALCOM_API_KEY", "k")
        monkeypatch.setattr(_calcom, "CALCOM_EVENT_TYPE_ID", "1")

        client = AsyncMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "booking": {
                "id": 12345,
                "uid": "abc",
                "meetingUrl": "https://meet.google.com/xyz",
            }
        }
        resp.raise_for_status = MagicMock()
        client.post.return_value = resp

        result = await _calcom.create_booking(
            client,
            name="Test",
            email="t@x.com",
            start_iso="2026-05-02T10:00:00Z",
            end_iso="2026-05-02T10:30:00Z",
        )
        assert result["ok"] is True
        assert result["booking_id"] == "12345"
        assert result["meeting_url"] == "https://meet.google.com/xyz"


# ============================================================================
# Email sender
# ============================================================================


class TestEmailSender:
    def test_unconfigured_when_smtp_host_missing(self, monkeypatch):
        monkeypatch.setattr(_email_sender, "SMTP_HOST", "")
        monkeypatch.setattr(_email_sender, "DEMO_INBOX", "x@y.com")
        assert _email_sender.is_configured() is False

    def test_unconfigured_when_inbox_missing(self, monkeypatch):
        monkeypatch.setattr(_email_sender, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(_email_sender, "DEMO_INBOX", "")
        assert _email_sender.is_configured() is False

    def test_configured_when_both_set(self, monkeypatch):
        monkeypatch.setattr(_email_sender, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(_email_sender, "DEMO_INBOX", "x@y.com")
        assert _email_sender.is_configured() is True

    @pytest.mark.asyncio
    async def test_send_internal_alert_skipped_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(_email_sender, "SMTP_HOST", "")
        result = await _email_sender.send_internal_alert({"id": "x", "name": "y"})
        assert result is False


# ============================================================================
# Storage
# ============================================================================


class FakeConn:
    def __init__(self):
        self.executes: list = []

    async def execute(self, sql, *args):
        self.executes.append((sql, args))
        return "INSERT 0 1"


class FakePool:
    def __init__(self, conn: FakeConn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self_inner):
                return conn

            async def __aexit__(self_inner, *args):
                return None

        return _Ctx()


class TestStorage:
    @pytest.mark.asyncio
    async def test_insert_demo_request_runs_insert_with_jsonb_window(self):
        conn = FakeConn()
        pool = FakePool(conn)
        rid = await _storage.insert_demo_request(
            pool,
            name="Alice",
            work_email="alice@example.com",
            company="Acme",
            role="CTO",
            team_size="2–10",
            use_case="Want to evaluate",
            preferred_window={"time_of_day": "morning", "timezone": "America/Los_Angeles"},
            source_ip="1.2.3.4",
            user_agent="ua",
        )
        assert rid  # uuid string
        assert len(conn.executes) == 1
        sql, args = conn.executes[0]
        assert "INSERT INTO demo_requests" in sql
        # args[7] is the jsonb-serialized preferred_window
        assert json.loads(args[7])["time_of_day"] == "morning"

    @pytest.mark.asyncio
    async def test_insert_demo_request_handles_null_window(self):
        conn = FakeConn()
        pool = FakePool(conn)
        await _storage.insert_demo_request(
            pool,
            name="Alice",
            work_email="alice@example.com",
            company=None,
            role=None,
            team_size=None,
            use_case=None,
            preferred_window=None,
            source_ip="1.2.3.4",
            user_agent=None,
        )
        sql, args = conn.executes[0]
        # preferred_window arg should be None when no window provided
        assert args[7] is None

    @pytest.mark.asyncio
    async def test_attach_calcom_booking_updates_status(self):
        conn = FakeConn()
        pool = FakePool(conn)
        await _storage.attach_calcom_booking(pool, "rid", "booking-123", "https://meet/abc")
        sql, args = conn.executes[0]
        assert "UPDATE demo_requests" in sql
        assert "scheduled" in sql
        assert args == ("booking-123", "https://meet/abc", "rid")
