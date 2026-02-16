"""Unit tests for the Policy Router routing strategy module.

Tests model scoring algorithms (cost, latency, error rate, capabilities,
budget adjustment), model ranking, fallback selection, cost estimation,
and alias resolution.
"""

import sys
import os
import importlib.util
from decimal import Decimal

import pytest

# Load the policy-router modules under unique names to avoid sys.modules collision
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/policy-router")
sys.path.insert(0, _service_dir)  # needed so routing_strategy.py can import models

_models_path = os.path.join(_service_dir, "models.py")
_models_spec = importlib.util.spec_from_file_location("policy_router_models", _models_path)
_models_mod = importlib.util.module_from_spec(_models_spec)
sys.modules["models"] = _models_mod
_models_spec.loader.exec_module(_models_mod)

_strategy_path = os.path.join(_service_dir, "routing_strategy.py")
_strategy_spec = importlib.util.spec_from_file_location("policy_router_strategy", _strategy_path)
_strategy_mod = importlib.util.module_from_spec(_strategy_spec)
_strategy_spec.loader.exec_module(_strategy_mod)

RoutingStrategy = _strategy_mod.RoutingStrategy
ScoredModel = _strategy_mod.ScoredModel
ModelInfo = _models_mod.ModelInfo
ModelTier = _models_mod.ModelTier
RoutingRequest = _models_mod.RoutingRequest


def _make_model(**overrides) -> ModelInfo:
    """Helper to create a ModelInfo with sensible defaults."""
    defaults = {
        "model_id": "test-model",
        "provider": "openai",
        "tier": ModelTier.STANDARD,
        "cost_per_1k_input": Decimal("0.01"),
        "cost_per_1k_output": Decimal("0.03"),
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "default_latency_sla_ms": 5000,
        "current_latency_ms": None,
        "current_error_rate": None,
        "requests_per_minute": None,
        "is_available": True,
    }
    defaults.update(overrides)
    return ModelInfo(**defaults)


def _make_request(**overrides) -> RoutingRequest:
    """Helper to create a RoutingRequest with sensible defaults."""
    defaults = {
        "user_id": "user-1",
        "team_id": "team-1",
        "budget_remaining": None,
        "latency_sla_ms": None,
        "required_capabilities": None,
    }
    defaults.update(overrides)
    return RoutingRequest(**defaults)


# ============================================================================
# _score_cost
# ============================================================================


class TestScoreCost:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()
        self.request = _make_request()

    def test_very_cheap_model(self):
        """Cost <= 0.001 per 1k should score 50."""
        model = _make_model(
            cost_per_1k_input=Decimal("0.0005"),
            cost_per_1k_output=Decimal("0.001"),
        )
        score = self.strategy._score_cost(model, self.request)
        assert score == 50

    def test_expensive_model(self):
        """Cost >= 0.05 per 1k should score -30."""
        model = _make_model(
            cost_per_1k_input=Decimal("0.06"),
            cost_per_1k_output=Decimal("0.12"),
        )
        score = self.strategy._score_cost(model, self.request)
        assert score == -30

    def test_mid_range_model(self):
        """Mid-range cost should produce a score between -30 and 50."""
        model = _make_model(
            cost_per_1k_input=Decimal("0.01"),
            cost_per_1k_output=Decimal("0.03"),
        )
        score = self.strategy._score_cost(model, self.request)
        # avg = 0.02, linear: 50 - (0.02/0.05)*80 = 50 - 32 = 18
        assert -30 < score < 50
        assert abs(score - 18.0) < 0.01


# ============================================================================
# _score_latency
# ============================================================================


class TestScoreLatency:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()

    def test_within_sla_positive(self):
        """Latency well within SLA should produce a positive score."""
        model = _make_model(current_latency_ms=1000, default_latency_sla_ms=5000)
        request = _make_request()
        score = self.strategy._score_latency(model, request)
        # margin = (5000-1000)/5000 = 0.8, score = 0.8*50 = 40
        assert score > 0
        assert abs(score - 40.0) < 0.01

    def test_over_sla_negative(self):
        """Latency over SLA should produce a negative score."""
        model = _make_model(current_latency_ms=8000, default_latency_sla_ms=5000)
        request = _make_request()
        score = self.strategy._score_latency(model, request)
        # overrun = (8000-5000)/5000 = 0.6, score = -min(0.6*100, 100) = -60
        assert score < 0
        assert abs(score - (-60.0)) < 0.01

    def test_none_latency_returns_zero(self):
        """Unknown latency (None) should return 0."""
        model = _make_model(current_latency_ms=None)
        request = _make_request()
        score = self.strategy._score_latency(model, request)
        assert score == 0

    def test_request_sla_overrides_default(self):
        """Request-level latency_sla_ms should override the model default."""
        model = _make_model(current_latency_ms=2000, default_latency_sla_ms=5000)
        request = _make_request(latency_sla_ms=3000)
        score = self.strategy._score_latency(model, request)
        # margin = (3000-2000)/3000 = 0.333, score = 0.333*50 ~ 16.67
        assert abs(score - 16.67) < 0.1


# ============================================================================
# _score_error_rate
# ============================================================================


class TestScoreErrorRate:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()

    def test_low_error_rate(self):
        """Error rate <= 1% should score 20."""
        model = _make_model(current_error_rate=0.005)
        assert self.strategy._score_error_rate(model) == 20

    def test_medium_error_rate(self):
        """Error rate 1-3% should score 0."""
        model = _make_model(current_error_rate=0.02)
        assert self.strategy._score_error_rate(model) == 0

    def test_high_error_rate(self):
        """Error rate 3-5% should score -30."""
        model = _make_model(current_error_rate=0.04)
        assert self.strategy._score_error_rate(model) == -30

    def test_very_high_error_rate(self):
        """Error rate > 5% should score -100."""
        model = _make_model(current_error_rate=0.10)
        assert self.strategy._score_error_rate(model) == -100

    def test_none_error_rate(self):
        """Unknown error rate (None) should return 0."""
        model = _make_model(current_error_rate=None)
        assert self.strategy._score_error_rate(model) == 0


# ============================================================================
# _score_capabilities
# ============================================================================


class TestScoreCapabilities:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()

    def test_matching_streaming(self):
        """Matching streaming capability should add 10 points."""
        model = _make_model(supports_streaming=True)
        request = _make_request(required_capabilities=["streaming"])
        score = self.strategy._score_capabilities(model, request)
        assert score == 10

    def test_matching_function_calling(self):
        """Matching function_calling capability should add 20 points."""
        model = _make_model(supports_function_calling=True)
        request = _make_request(required_capabilities=["function_calling"])
        score = self.strategy._score_capabilities(model, request)
        assert score == 20

    def test_matching_vision(self):
        """Matching vision capability should add 15 points."""
        model = _make_model(supports_vision=True)
        request = _make_request(required_capabilities=["vision"])
        score = self.strategy._score_capabilities(model, request)
        assert score == 15

    def test_missing_required_capability(self):
        """Missing a required capability should subtract 100 points."""
        model = _make_model(supports_function_calling=False)
        request = _make_request(required_capabilities=["function_calling"])
        score = self.strategy._score_capabilities(model, request)
        assert score == -100

    def test_no_capabilities_required(self):
        """No required capabilities should return 0."""
        model = _make_model()
        request = _make_request(required_capabilities=None)
        score = self.strategy._score_capabilities(model, request)
        assert score == 0


# ============================================================================
# _budget_adjustment
# ============================================================================


class TestBudgetAdjustment:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()

    def test_critical_budget_free_tier(self):
        """Critical budget (< $10) should give FREE tier +100."""
        model = _make_model(tier=ModelTier.FREE)
        request = _make_request(budget_remaining=5.0)
        assert self.strategy._budget_adjustment(model, request) == 100

    def test_critical_budget_budget_tier(self):
        """Critical budget should give BUDGET tier +50."""
        model = _make_model(tier=ModelTier.BUDGET)
        request = _make_request(budget_remaining=5.0)
        assert self.strategy._budget_adjustment(model, request) == 50

    def test_critical_budget_vllm_provider(self):
        """Critical budget should give vllm provider +75."""
        model = _make_model(tier=ModelTier.STANDARD, provider="vllm")
        request = _make_request(budget_remaining=5.0)
        assert self.strategy._budget_adjustment(model, request) == 75

    def test_critical_budget_premium_penalized(self):
        """Critical budget should penalize premium models by -50."""
        model = _make_model(tier=ModelTier.PREMIUM)
        request = _make_request(budget_remaining=5.0)
        assert self.strategy._budget_adjustment(model, request) == -50

    def test_no_budget_constraint(self):
        """No budget_remaining should return 0."""
        model = _make_model()
        request = _make_request(budget_remaining=None)
        assert self.strategy._budget_adjustment(model, request) == 0

    def test_ample_budget(self):
        """Budget above critical threshold should return 0."""
        model = _make_model(tier=ModelTier.PREMIUM)
        request = _make_request(budget_remaining=500.0)
        assert self.strategy._budget_adjustment(model, request) == 0


# ============================================================================
# rank_models
# ============================================================================


class TestRankModels:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()

    def test_sorted_by_score_descending(self):
        """Ranked models should be sorted by score in descending order."""
        cheap = _make_model(
            model_id="cheap",
            cost_per_1k_input=Decimal("0.0001"),
            cost_per_1k_output=Decimal("0.0002"),
        )
        expensive = _make_model(
            model_id="expensive",
            cost_per_1k_input=Decimal("0.06"),
            cost_per_1k_output=Decimal("0.12"),
        )
        request = _make_request()
        ranked = self.strategy.rank_models([expensive, cheap], request)
        assert len(ranked) >= 1
        # Cheap model should score higher
        scores = [s.score for s in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_unavailable_models_filtered(self):
        """Unavailable models should be excluded from results."""
        available = _make_model(model_id="up", is_available=True)
        down = _make_model(model_id="down", is_available=False)
        request = _make_request()
        ranked = self.strategy.rank_models([available, down], request)
        model_ids = [s.model.model_id for s in ranked]
        assert "down" not in model_ids

    def test_policy_denied_filtered(self):
        """Models denied by policy should be excluded."""
        m1 = _make_model(model_id="allowed-model")
        m2 = _make_model(model_id="denied-model")
        request = _make_request()
        policy_results = {
            "allowed-model": (True, []),
            "denied-model": (False, ["policy-1"]),
        }
        ranked = self.strategy.rank_models([m1, m2], request, policy_results)
        model_ids = [s.model.model_id for s in ranked]
        assert "denied-model" not in model_ids
        assert "allowed-model" in model_ids

    def test_empty_model_list(self):
        """Empty model list should return empty ranked list."""
        request = _make_request()
        ranked = self.strategy.rank_models([], request)
        assert ranked == []


# ============================================================================
# select_with_fallbacks
# ============================================================================


class TestSelectWithFallbacks:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()

    def test_returns_best_and_fallbacks(self):
        """Should return the best model plus up to num_fallbacks fallbacks."""
        models = [
            _make_model(
                model_id=f"model-{i}",
                cost_per_1k_input=Decimal(str(0.001 * (i + 1))),
                cost_per_1k_output=Decimal(str(0.003 * (i + 1))),
            )
            for i in range(4)
        ]
        request = _make_request()
        selected, fallbacks, reason = self.strategy.select_with_fallbacks(models, request)
        assert selected is not None
        assert isinstance(fallbacks, list)
        assert len(fallbacks) <= 2
        assert "Selected" in reason

    def test_empty_list_returns_none(self):
        """Empty model list should return None with no fallbacks."""
        request = _make_request()
        selected, fallbacks, reason = self.strategy.select_with_fallbacks([], request)
        assert selected is None
        assert fallbacks == []
        assert "No models" in reason

    def test_single_model_no_fallbacks(self):
        """A single model should be selected with no fallbacks."""
        model = _make_model(model_id="solo")
        request = _make_request()
        selected, fallbacks, reason = self.strategy.select_with_fallbacks([model], request)
        assert selected is not None
        assert selected.model_id == "solo"
        assert fallbacks == []


# ============================================================================
# estimate_cost
# ============================================================================


class TestEstimateCost:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()

    def test_known_calculation(self):
        """Cost should be (input/1000)*input_price + (output/1000)*output_price."""
        model = _make_model(
            cost_per_1k_input=Decimal("0.01"),
            cost_per_1k_output=Decimal("0.03"),
        )
        cost = self.strategy.estimate_cost(model, input_tokens=2000, output_tokens=1000)
        # (2000/1000)*0.01 + (1000/1000)*0.03 = 0.02 + 0.03 = 0.05
        assert abs(cost - 0.05) < 1e-9

    def test_zero_tokens(self):
        """Zero tokens should produce zero cost."""
        model = _make_model()
        cost = self.strategy.estimate_cost(model, input_tokens=0, output_tokens=0)
        assert cost == 0.0


# ============================================================================
# resolve_model_alias
# ============================================================================


class TestResolveModelAlias:
    def setup_method(self):
        """Create a fresh RoutingStrategy for each test."""
        self.strategy = RoutingStrategy()

    def test_direct_match(self):
        """A direct model name should resolve to itself."""
        models = [_make_model(model_id="gpt-4o")]
        result = self.strategy.resolve_model_alias("gpt-4o", models)
        assert result == "gpt-4o"

    def test_group_alias(self):
        """A group alias should resolve to the first available model in the group."""
        models = [
            _make_model(model_id="claude-3-haiku"),
            _make_model(model_id="gpt-4o-mini"),
        ]
        result = self.strategy.resolve_model_alias("fast", models)
        # "fast" group: ["gpt-4o-mini", "claude-3-haiku", "grok-3-mini"]
        assert result == "gpt-4o-mini"

    def test_unknown_alias_returns_none(self):
        """An unknown alias with no matching models should return None."""
        models = [_make_model(model_id="some-model")]
        result = self.strategy.resolve_model_alias("nonexistent-alias", models)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
