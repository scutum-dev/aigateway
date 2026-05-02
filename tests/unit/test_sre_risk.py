"""Unit tests for risk.score().

v1 always returns 'human' regardless of score because the autonomy decision
was always-human. The score is still meaningful — it determines what would
have happened in v2 — so we exercise both the score math and the decision.
"""

import importlib.util
import os
import sys

import pytest

_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "../../src/sre-agent")
sys.path.insert(0, _SERVICE_DIR)

# actions.py is imported by risk.py, so load it first under the same module name.
_a_spec = importlib.util.spec_from_file_location("actions", os.path.join(_SERVICE_DIR, "actions.py"))
_actions = importlib.util.module_from_spec(_a_spec)
sys.modules["actions"] = _actions
_a_spec.loader.exec_module(_actions)

_r_spec = importlib.util.spec_from_file_location("risk", os.path.join(_SERVICE_DIR, "risk.py"))
_risk = importlib.util.module_from_spec(_r_spec)
sys.modules["risk"] = _risk
_r_spec.loader.exec_module(_risk)


score = _risk.score

# Restore sys.modules / sys.path at module-load time so other test modules
# (notably test_budget_webhook) keep their own bare-name imports intact.
# `_risk` and `_actions` references are kept by this module, so the modules
# stay alive even after the sys.modules entries are removed.
for _n in ("actions", "risk"):
    sys.modules.pop(_n, None)
if _SERVICE_DIR in sys.path:
    sys.path.remove(_SERVICE_DIR)


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("SRE_AUTO_APPROVE", raising=False)
    monkeypatch.delenv("SRE_RISK_THRESHOLD", raising=False)


class TestBaseScore:
    @pytest.mark.parametrize(
        "action,expected_base",
        [
            ("notify", 0),
            ("trigger_failover", 10),
            ("clear_cache", 15),
            ("tighten_rate_limit", 30),
            ("tighten_guardrail", 30),
            ("reassign_guardrail", 70),
            ("update_budget", 90),
            ("deprecate_model", 95),
        ],
    )
    def test_base_score_clean_diagnosis(self, action, expected_base):
        s, _decision = score(action, {}, {})
        assert s == expected_base


class TestModifiers:
    def test_org_scope_amplifies_when_action_is_qualifying(self):
        s_team, _ = score("tighten_rate_limit", {"team_id": "t-1"}, {})
        s_org, _ = score("tighten_rate_limit", {"team_id": "*"}, {})
        assert s_org == s_team + 10

    def test_org_scope_does_not_amplify_pure_human_actions(self):
        s, _ = score("update_budget", {"team_id": "*"}, {})
        # update_budget base is 90; org modifier only applies to the auto-conditional list.
        assert s == 90

    def test_affected_users_modifier(self):
        s_low, _ = score("trigger_failover", {}, {"affected_users": 5})
        s_high, _ = score("trigger_failover", {}, {"affected_users": 500})
        assert s_high == s_low + 15

    def test_oscillation_guard(self):
        diagnosis = {"recent_audit_for_resource": [{"action": "revert"}]}
        s_with, _ = score("trigger_failover", {}, diagnosis)
        s_without, _ = score("trigger_failover", {}, {})
        assert s_with == s_without + 20

    def test_score_caps_at_100(self):
        s, _ = score(
            "deprecate_model",
            {},
            {"affected_users": 999, "recent_audit_for_resource": [{"action": "revert"}]},
        )
        assert s == 100


class TestDecision:
    def test_human_class_always_human_even_with_auto_approve(self, monkeypatch):
        monkeypatch.setenv("SRE_AUTO_APPROVE", "true")
        _, decision = score("update_budget", {}, {})
        assert decision == "human"

    def test_v1_default_is_human_for_low_risk_actions(self, monkeypatch):
        monkeypatch.delenv("SRE_AUTO_APPROVE", raising=False)
        _, decision = score("notify", {}, {})
        assert decision == "human"

    def test_v2_low_risk_can_be_auto(self, monkeypatch):
        monkeypatch.setenv("SRE_AUTO_APPROVE", "true")
        monkeypatch.setenv("SRE_RISK_THRESHOLD", "40")
        _, decision = score("notify", {}, {})
        assert decision == "auto"

    def test_v2_above_threshold_still_human(self, monkeypatch):
        monkeypatch.setenv("SRE_AUTO_APPROVE", "true")
        monkeypatch.setenv("SRE_RISK_THRESHOLD", "5")
        _, decision = score("trigger_failover", {}, {})  # base 10 > threshold 5
        assert decision == "human"
