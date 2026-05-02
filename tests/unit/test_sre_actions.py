"""Unit tests for the SRE agent action allow-list registry.

Verifies:
- Every spec produces a valid OpenAI tool definition (no required-but-missing).
- validate() rejects unknown actions and reports missing required params.
- builder() functions produce coherent admin-api method+path tuples.
- preconditions() gate trigger_failover when the trigger lacks a provider/model.
"""

import importlib.util
import os
import sys

import pytest

_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "../../src/sre-agent")
sys.path.insert(0, _SERVICE_DIR)
_spec = importlib.util.spec_from_file_location("sre_actions", os.path.join(_SERVICE_DIR, "actions.py"))
_actions = importlib.util.module_from_spec(_spec)
sys.modules["sre_actions"] = _actions
_spec.loader.exec_module(_actions)

if _SERVICE_DIR in sys.path:
    sys.path.remove(_SERVICE_DIR)
sys.modules.pop("sre_actions", None)

ALLOWED_ACTIONS = _actions.ALLOWED_ACTIONS
list_tool_definitions = _actions.list_tool_definitions
validate = _actions.validate


class TestAllowList:
    def test_every_action_has_a_spec(self):
        expected = {
            "notify",
            "trigger_failover",
            "tighten_rate_limit",
            "tighten_guardrail",
            "clear_cache",
            "reassign_guardrail",
            "update_budget",
            "deprecate_model",
        }
        assert set(ALLOWED_ACTIONS.keys()) == expected

    def test_tool_definitions_are_well_formed(self):
        tools = list_tool_definitions()
        assert len(tools) == len(ALLOWED_ACTIONS)
        names = [t["function"]["name"] for t in tools]
        assert set(names) == set(ALLOWED_ACTIONS.keys())
        for tool in tools:
            assert tool["type"] == "function"
            params = tool["function"]["parameters"]
            assert params["type"] == "object"
            assert isinstance(params["properties"], dict)
            assert isinstance(params["required"], list)


class TestValidate:
    def test_unknown_action_rejected(self):
        err = validate("delete_database", {})
        assert err is not None
        assert "Unknown action" in err

    def test_missing_required_param_rejected(self):
        err = validate("trigger_failover", {})
        assert err is not None
        assert "failover_rule_id" in err

    def test_well_formed_call_accepted(self):
        assert validate("trigger_failover", {"failover_rule_id": "abc-123"}) is None
        assert validate("notify", {"summary": "hi", "severity": "info"}) is None

    def test_optional_params_not_required(self):
        # clear_cache has no required params — empty {} should be accepted.
        assert validate("clear_cache", {}) is None


class TestBuilders:
    def test_failover_builder_emits_admin_api_post(self):
        spec = ALLOWED_ACTIONS["trigger_failover"]
        out = spec.builder({"failover_rule_id": "rule-uuid"})
        assert out["kind"] == "admin_api"
        assert out["method"] == "POST"
        assert out["path"].endswith("/sla/failover-rules/rule-uuid/trigger")
        assert out["body"] is None

    def test_rate_limit_builder_strips_policy_id(self):
        spec = ALLOWED_ACTIONS["tighten_rate_limit"]
        out = spec.builder({"policy_id": "pid", "rpm_limit": 100, "tpm_limit": 5000})
        assert out["method"] == "PUT"
        assert out["path"].endswith("/rate-limits/pid")
        assert "policy_id" not in out["body"]
        assert out["body"]["rpm_limit"] == 100

    def test_guardrail_warn_builder_locks_mode(self):
        spec = ALLOWED_ACTIONS["tighten_guardrail"]
        out = spec.builder({"guardrail_id": "g-1"})
        assert out["body"] == {"mode": "warn"}

    def test_clear_cache_team_scope_passes_team_id(self):
        spec = ALLOWED_ACTIONS["clear_cache"]
        out_scoped = spec.builder({"team_id": "t-1"})
        out_global = spec.builder({})
        assert out_scoped["body"] == {"team_id": "t-1"}
        assert out_global["body"] == {}

    def test_notify_builder_is_internal(self):
        spec = ALLOWED_ACTIONS["notify"]
        out = spec.builder({"summary": "x", "severity": "warning"})
        assert out["kind"] == "notify"
        assert out["summary"] == "x"


class TestPreconditions:
    def test_trigger_failover_requires_provider_or_model(self):
        spec = ALLOWED_ACTIONS["trigger_failover"]
        assert spec.preconditions({"trigger_payload": {}}) is False
        assert spec.preconditions({"trigger_payload": {"provider": "openai"}}) is True
        assert spec.preconditions({"trigger_payload": {"model": "gpt-4o"}}) is True

    def test_other_actions_default_pass(self):
        for name in ("notify", "tighten_rate_limit", "clear_cache", "update_budget"):
            spec = ALLOWED_ACTIONS[name]
            assert spec.preconditions({}) is True


class TestRiskClasses:
    @pytest.mark.parametrize(
        "action,expected_class",
        [
            ("notify", "auto"),
            ("trigger_failover", "auto"),
            ("tighten_rate_limit", "auto-conditional"),
            ("tighten_guardrail", "auto-conditional"),
            ("clear_cache", "auto-conditional"),
            ("reassign_guardrail", "human"),
            ("update_budget", "human"),
            ("deprecate_model", "human"),
        ],
    )
    def test_risk_classes_pinned(self, action, expected_class):
        assert ALLOWED_ACTIONS[action].risk_class == expected_class
