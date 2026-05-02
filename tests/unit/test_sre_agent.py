"""Unit tests for sre-agent orchestration: open_incident, diagnose_and_propose,
execute_approved, reject_incident.

LLM and admin-api are mocked. asyncpg pool is faked with a context-manager
shim that records every SQL call so we can assert state transitions.
"""

import importlib.util
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "../../src/sre-agent")
sys.path.insert(0, _SERVICE_DIR)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_SERVICE_DIR, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_actions = _load("actions")
_risk = _load("risk")
_diagnose = _load("diagnose")
_notifier = _load("notifier")
_llm = _load("llm")
_agent = _load("agent")

# Restore sys.modules / sys.path at module-load time so other test modules
# (notably test_budget_webhook) keep their own bare-name imports intact.
# Captured module references above keep these alive.
for _n in ("actions", "risk", "diagnose", "notifier", "llm", "agent", "admin_client"):
    sys.modules.pop(_n, None)
if _SERVICE_DIR in sys.path:
    sys.path.remove(_SERVICE_DIR)


class FakeConn:
    """Minimal asyncpg.Connection stand-in with scripted return values."""

    def __init__(self):
        self.executes: list = []
        self.fetchrows: list = []
        self.fetches: list = []
        self.fetchvals: list = []
        self._fetchrow_returns: list = []
        self._fetch_returns: list = []
        self._fetchval_returns: list = []
        self._execute_returns: list = []

    def queue_fetchrow(self, value):
        self._fetchrow_returns.append(value)

    def queue_fetch(self, value):
        self._fetch_returns.append(value)

    def queue_fetchval(self, value):
        self._fetchval_returns.append(value)

    def queue_execute(self, value="UPDATE 1"):
        self._execute_returns.append(value)

    async def execute(self, sql, *args):
        self.executes.append((sql, args))
        if self._execute_returns:
            return self._execute_returns.pop(0)
        return "UPDATE 1"

    async def fetchrow(self, sql, *args):
        self.fetchrows.append((sql, args))
        if self._fetchrow_returns:
            return self._fetchrow_returns.pop(0)
        return None

    async def fetch(self, sql, *args):
        self.fetches.append((sql, args))
        if self._fetch_returns:
            return self._fetch_returns.pop(0)
        return []

    async def fetchval(self, sql, *args):
        self.fetchvals.append((sql, args))
        if self._fetchval_returns:
            return self._fetchval_returns.pop(0)
        return None


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


@pytest.mark.asyncio
async def test_open_incident_inserts_row():
    conn = FakeConn()
    conn.queue_fetchrow({"id": "11111111-1111-1111-1111-111111111111"})
    pool = FakePool(conn)

    incident_id = await _agent.open_incident(pool, "sla.violation", {"provider": "openai"})

    assert incident_id == "11111111-1111-1111-1111-111111111111"
    assert any("INSERT INTO sre_incidents" in sql for sql, _ in conn.fetchrows)


@pytest.mark.asyncio
async def test_diagnose_and_propose_persists_plan_and_decisions(monkeypatch):
    conn = FakeConn()
    pool = FakePool(conn)

    # diagnose status flip + read trigger row
    conn.queue_execute()  # UPDATE status='diagnosing'
    conn.queue_fetchrow({"trigger_event": "sla.violation", "trigger_payload": {"provider": "openai"}})

    # diagnose internal queries — we'll let them all return [] / 0.
    for _ in range(7):
        conn.queue_fetch([])
    conn.queue_fetchval(0)

    # final UPDATE writing diagnosis + plan + status='awaiting_approval'
    conn.queue_execute()
    # one INSERT INTO sre_action_decisions per plan step (we'll have 1 step → notify)
    conn.queue_execute()

    # No event_subscriptions for sre.incident → notify_all returns 0
    conn.queue_fetch([])

    proposer = MagicMock()
    proposer.propose = AsyncMock(return_value=[{"action": "notify", "params": {"summary": "x", "severity": "info"}}])

    http_client = AsyncMock()
    monkeypatch.setattr(_agent, "diagnose", _diagnose)
    monkeypatch.setattr(_agent, "notifier", _notifier)

    await _agent.diagnose_and_propose(pool, http_client, proposer, "incident-1")

    update_sqls = [sql for sql, _ in conn.executes]
    assert any("status = 'diagnosing'" in s for s in update_sqls)
    assert any("UPDATE sre_incidents" in s and "status = $3" in s for s in update_sqls)
    assert any("INSERT INTO sre_action_decisions" in s for s in update_sqls)


@pytest.mark.asyncio
async def test_diagnose_and_propose_when_plan_empty_marks_failed(monkeypatch):
    """If the LLM returns no actions and notify default is filtered out, status = closed_failed."""
    conn = FakeConn()
    pool = FakePool(conn)

    conn.queue_execute()  # status='diagnosing'
    conn.queue_fetchrow({"trigger_event": "sla.violation", "trigger_payload": {}})
    for _ in range(7):
        conn.queue_fetch([])
    conn.queue_fetchval(0)
    conn.queue_execute()  # final UPDATE
    conn.queue_fetch([])  # notify_all subscriptions

    proposer = MagicMock()
    # Simulate a proposal whose only step has preconditions=False (e.g. failover with no provider).
    proposer.propose = AsyncMock(return_value=[{"action": "trigger_failover", "params": {"failover_rule_id": "x"}}])

    monkeypatch.setattr(_agent, "diagnose", _diagnose)
    monkeypatch.setattr(_agent, "notifier", _notifier)

    await _agent.diagnose_and_propose(pool, AsyncMock(), proposer, "incident-2")
    # Final update SQL contains the new status; arg index 2 is status.
    final_update = [args for sql, args in conn.executes if "UPDATE sre_incidents" in sql and "status = $3" in sql]
    assert final_update, "expected a final UPDATE with status arg"
    assert final_update[-1][2] == "closed_failed"


@pytest.mark.asyncio
async def test_execute_approved_runs_each_step_and_marks_success():
    conn = FakeConn()
    pool = FakePool(conn)

    plan = [
        {"action": "notify", "params": {"summary": "x", "severity": "info"}},
        {"action": "trigger_failover", "params": {"failover_rule_id": "rule-1"}},
    ]
    conn.queue_fetchrow({"proposed_plan": json.dumps(plan), "status": "awaiting_approval"})
    conn.queue_execute()  # status='executing'
    # notify_all reads subscriptions (returns 0 dispatched)
    conn.queue_fetch([])
    # update sre_action_decisions for notify
    conn.queue_execute()
    # update sre_action_decisions for trigger_failover
    conn.queue_execute()
    # final UPDATE sre_incidents status closed_success
    conn.queue_execute()

    admin_client = MagicMock()
    admin_client.call = AsyncMock(return_value={"ok": True, "status": 200, "body": {"status": "triggered"}})

    http_client = AsyncMock()

    result = await _agent.execute_approved(pool, admin_client, http_client, "inc-1", "approver-1")

    assert result["ok"] is True
    assert result["status"] == "closed_success"
    assert len(result["executed"]) == 2
    admin_client.call.assert_awaited_once()  # only trigger_failover hits admin-api; notify is internal


@pytest.mark.asyncio
async def test_execute_approved_rejects_wrong_status():
    conn = FakeConn()
    pool = FakePool(conn)
    conn.queue_fetchrow({"proposed_plan": "[]", "status": "closed_success"})

    result = await _agent.execute_approved(pool, MagicMock(), AsyncMock(), "inc-1", "approver-1")
    assert result["ok"] is False
    assert "Cannot execute" in result["error"]


@pytest.mark.asyncio
async def test_reject_incident_only_when_awaiting_approval():
    conn = FakeConn()
    pool = FakePool(conn)
    conn.queue_execute("UPDATE 1")
    result = await _agent.reject_incident(pool, "inc-1", "user-1", "wrong action")
    assert result["ok"] is True

    # Second call: incident not awaiting_approval, UPDATE returns 0 rows
    conn.queue_execute("UPDATE 0")
    result_no = await _agent.reject_incident(pool, "inc-2", "user-1", None)
    assert result_no["ok"] is False
