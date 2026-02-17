"""Unit tests for the Cedar policy evaluation engine.

Tests entity building, policy evaluation fallbacks, and model selection logic.
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Load the cedar_engine module from src/policy-router/cedar_engine.py
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/policy-router")
sys.path.insert(0, _service_dir)
_spec = importlib.util.spec_from_file_location(
    "cedar_engine_mod",
    os.path.join(_service_dir, "cedar_engine.py"),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["cedar_engine_mod"] = _mod
_spec.loader.exec_module(_mod)

CedarEngine = _mod.CedarEngine


# ============================================================================
# _build_entities
# ============================================================================


class TestBuildEntities:
    def test_user_principal_entity(self, tmp_path):
        """Should create entity with correct uid type and id for user principal."""
        engine = CedarEngine(str(tmp_path))
        context = {"provider": "openai", "tier": "premium"}
        entities = engine._build_entities("user::user-123", "model::gpt-4o", context)

        principal_entity = next(e for e in entities if e["uid"]["type"] == "user")
        assert principal_entity["uid"]["id"] == "user-123"
        assert principal_entity["parents"] == []

    def test_model_resource_entity_with_attrs(self, tmp_path):
        """Should create resource entity with provider and tier attributes."""
        engine = CedarEngine(str(tmp_path))
        context = {"provider": "anthropic", "tier": "premium", "current_latency_ms": 500}
        entities = engine._build_entities("user::u1", "model::claude-3-opus", context)

        resource_entity = next(e for e in entities if e["uid"]["type"] == "model")
        assert resource_entity["uid"]["id"] == "claude-3-opus"
        assert resource_entity["attrs"]["provider"] == "anthropic"
        assert resource_entity["attrs"]["tier"] == "premium"
        assert resource_entity["attrs"]["average_latency_ms"] == 500

    def test_principal_without_separator(self, tmp_path):
        """Should not create a principal entity when :: is absent."""
        engine = CedarEngine(str(tmp_path))
        entities = engine._build_entities("anonymous", "model::gpt-4o", {"provider": "openai"})

        types = [e["uid"]["type"] for e in entities]
        assert "anonymous" not in types
        # Resource entity should still be created
        assert "model" in types


# ============================================================================
# evaluate
# ============================================================================


class TestEvaluate:
    def test_cedar_unavailable_defaults_to_allow(self, tmp_path):
        """Should return allow when cedarpy is not available."""
        original = _mod.CEDAR_AVAILABLE
        try:
            _mod.CEDAR_AVAILABLE = False
            engine = CedarEngine(str(tmp_path))
            result = engine.evaluate("user::u1", "routing:select_model", "model::gpt-4o", {})
            assert result.decision == "allow"
            assert "cedarpy not available" in result.reasons[0]
        finally:
            _mod.CEDAR_AVAILABLE = original

    def test_no_policies_defaults_to_allow(self, tmp_path):
        """Should return allow when no policies are loaded."""
        original = _mod.CEDAR_AVAILABLE
        try:
            _mod.CEDAR_AVAILABLE = True
            engine = CedarEngine(str(tmp_path))
            engine.policies = []
            result = engine.evaluate("user::u1", "routing:select_model", "model::gpt-4o", {})
            assert result.decision == "allow"
            assert "no policies loaded" in result.reasons[0]
        finally:
            _mod.CEDAR_AVAILABLE = original

    def test_cedarpy_error_returns_allow_with_error(self, tmp_path):
        """Should return allow with error message when cedarpy raises."""
        original = _mod.CEDAR_AVAILABLE
        try:
            _mod.CEDAR_AVAILABLE = True
            engine = CedarEngine(str(tmp_path))
            engine.policies = ["permit(principal, action, resource);"]

            mock_cedarpy = MagicMock()
            mock_cedarpy.is_authorized.side_effect = RuntimeError("parse error")

            with patch.dict(sys.modules, {"cedarpy": mock_cedarpy}):
                _mod.cedarpy = mock_cedarpy
                result = engine.evaluate(
                    "user::u1",
                    "routing:select_model",
                    "model::gpt-4o",
                    {"provider": "openai"},
                )

            assert result.decision == "allow"
            assert len(result.errors) > 0
            assert "Evaluation error" in result.errors[0]
        finally:
            _mod.CEDAR_AVAILABLE = original


# ============================================================================
# evaluate_model_selection
# ============================================================================


class TestEvaluateModelSelection:
    def test_builds_user_principal(self, tmp_path):
        """Should build user:: principal when user_id is provided."""
        original = _mod.CEDAR_AVAILABLE
        try:
            _mod.CEDAR_AVAILABLE = False
            engine = CedarEngine(str(tmp_path))

            with patch.object(engine, "evaluate", wraps=engine.evaluate) as mock_eval:
                engine.evaluate_model_selection(
                    user_id="user-42",
                    team_id="team-eng",
                    model_id="gpt-4o",
                    model_attrs={"provider": "openai", "tier": "premium"},
                    request_context={},
                )
                call_args = mock_eval.call_args
                assert call_args[1]["principal"] == "user::user-42"
        finally:
            _mod.CEDAR_AVAILABLE = original

    def test_builds_team_principal_when_no_user(self, tmp_path):
        """Should build team:: principal when only team_id is provided."""
        original = _mod.CEDAR_AVAILABLE
        try:
            _mod.CEDAR_AVAILABLE = False
            engine = CedarEngine(str(tmp_path))

            with patch.object(engine, "evaluate", wraps=engine.evaluate) as mock_eval:
                engine.evaluate_model_selection(
                    user_id=None,
                    team_id="team-eng",
                    model_id="gpt-4o",
                    model_attrs={"provider": "openai"},
                    request_context={},
                )
                call_args = mock_eval.call_args
                assert call_args[1]["principal"] == "team::team-eng"
        finally:
            _mod.CEDAR_AVAILABLE = original

    def test_anonymous_when_both_none(self, tmp_path):
        """Should use user::anonymous when both user_id and team_id are None."""
        original = _mod.CEDAR_AVAILABLE
        try:
            _mod.CEDAR_AVAILABLE = False
            engine = CedarEngine(str(tmp_path))

            with patch.object(engine, "evaluate", wraps=engine.evaluate) as mock_eval:
                engine.evaluate_model_selection(
                    user_id=None,
                    team_id=None,
                    model_id="gpt-4o",
                    model_attrs={"provider": "openai"},
                    request_context={},
                )
                call_args = mock_eval.call_args
                assert call_args[1]["principal"] == "user::anonymous"
        finally:
            _mod.CEDAR_AVAILABLE = original


# ============================================================================
# reload_policies
# ============================================================================


class TestReloadPolicies:
    def test_nonexistent_path_returns_zero(self):
        """Should load zero policies when path does not exist."""
        engine = CedarEngine("/nonexistent/path/to/policies")
        count = engine.reload_policies()
        assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
