"""
Model routing strategies and ranking algorithms.

Implements intelligent model selection based on:
- Cost optimization
- Latency requirements
- Capability matching
- Budget constraints
- Provider diversity
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass

from models import ModelInfo, ModelTier, RoutingRequest

logger = logging.getLogger(__name__)


@dataclass
class ScoredModel:
    """Model with routing score."""
    model: ModelInfo
    score: float
    reasons: List[str]


class RoutingStrategy:
    """
    Intelligent model routing strategy.

    Ranks models based on multiple factors and returns optimal
    selection with fallbacks.
    """

    # Scoring weights
    WEIGHT_COST = 0.3
    WEIGHT_LATENCY = 0.25
    WEIGHT_ERROR_RATE = 0.25
    WEIGHT_CAPABILITY = 0.2

    # Thresholds
    MAX_ERROR_RATE = 0.05  # 5% error rate threshold
    COST_BUDGET_CRITICAL = 10.0  # Below $10 is critical

    def __init__(self):
        """Initialize routing strategy."""
        self._model_groups = self._init_model_groups()

    def _init_model_groups(self) -> Dict[str, List[str]]:
        """Initialize model group aliases."""
        return {
            "fast": ["gpt-4o-mini", "claude-3-haiku", "grok-3-mini"],
            "smart": ["gpt-4o", "claude-3-5-sonnet", "grok-3"],
            "powerful": ["gpt-4o", "claude-3-opus", "grok-3"],
            "cost-effective": ["gpt-4o-mini", "claude-3-haiku", "llama-3.1-70b"],
            "self-hosted": ["llama-3.1-70b", "llama-3.1-8b"],
        }

    def resolve_model_alias(self, alias: str, available_models: List[ModelInfo]) -> Optional[str]:
        """
        Resolve a model alias to a specific model.

        Args:
            alias: Model alias (e.g., "fast", "smart") or specific model name
            available_models: List of available models

        Returns:
            Specific model ID or None
        """
        available_ids = {m.model_id for m in available_models}

        # Check if it's a direct model name
        if alias in available_ids:
            return alias

        # Check if it's a group alias
        if alias in self._model_groups:
            for model_id in self._model_groups[alias]:
                if model_id in available_ids:
                    return model_id

        return None

    def rank_models(
        self,
        models: List[ModelInfo],
        request: RoutingRequest,
        policy_results: Optional[Dict[str, Tuple[bool, List[str]]]] = None
    ) -> List[ScoredModel]:
        """
        Rank models for a given request.

        Args:
            models: Available models with metrics
            request: Routing request with constraints
            policy_results: Cedar policy evaluation results per model

        Returns:
            List of models sorted by score (best first)
        """
        scored_models = []

        for model in models:
            # Check policy results
            if policy_results and model.model_id in policy_results:
                allowed, reasons = policy_results[model.model_id]
                if not allowed:
                    logger.debug(f"Model {model.model_id} denied by policy: {reasons}")
                    continue

            # Check availability
            if not model.is_available:
                continue

            # Calculate score
            score, reasons = self._calculate_score(model, request)

            if score > 0:
                scored_models.append(ScoredModel(
                    model=model,
                    score=score,
                    reasons=reasons
                ))

        # Sort by score descending
        scored_models.sort(key=lambda x: x.score, reverse=True)

        return scored_models

    def _calculate_score(
        self,
        model: ModelInfo,
        request: RoutingRequest
    ) -> Tuple[float, List[str]]:
        """
        Calculate routing score for a model.

        Args:
            model: Model to score
            request: Request constraints

        Returns:
            Tuple of (score, reasons)
        """
        score = 100.0
        reasons = []

        # Cost scoring
        cost_score = self._score_cost(model, request)
        score += cost_score * self.WEIGHT_COST
        if cost_score > 0:
            reasons.append(f"cost_score: +{cost_score:.1f}")
        elif cost_score < 0:
            reasons.append(f"cost_score: {cost_score:.1f}")

        # Latency scoring
        latency_score = self._score_latency(model, request)
        score += latency_score * self.WEIGHT_LATENCY
        if latency_score != 0:
            reasons.append(f"latency_score: {latency_score:+.1f}")

        # Error rate scoring
        error_score = self._score_error_rate(model)
        score += error_score * self.WEIGHT_ERROR_RATE
        if error_score < 0:
            reasons.append(f"error_rate_penalty: {error_score:.1f}")

        # Capability scoring
        cap_score = self._score_capabilities(model, request)
        score += cap_score * self.WEIGHT_CAPABILITY
        if cap_score != 0:
            reasons.append(f"capability_score: {cap_score:+.1f}")

        # Budget constraints
        budget_adjustment = self._budget_adjustment(model, request)
        score += budget_adjustment
        if budget_adjustment != 0:
            reasons.append(f"budget_adjustment: {budget_adjustment:+.1f}")

        return max(0, score), reasons

    def _score_cost(self, model: ModelInfo, request: RoutingRequest) -> float:
        """Score based on cost efficiency."""
        # Lower cost = higher score
        # Normalize to 0-100 range based on typical costs
        avg_cost = (float(model.cost_per_1k_input) + float(model.cost_per_1k_output)) / 2

        # Invert and scale: $0.001/1k = 100 points, $0.05/1k = 0 points
        if avg_cost <= 0.001:
            return 50
        elif avg_cost >= 0.05:
            return -30
        else:
            # Linear interpolation
            return 50 - (avg_cost / 0.05) * 80

    def _score_latency(self, model: ModelInfo, request: RoutingRequest) -> float:
        """Score based on latency requirements."""
        current_latency = model.current_latency_ms
        sla = request.latency_sla_ms or model.default_latency_sla_ms

        if current_latency is None:
            return 0  # Neutral if unknown

        # Within SLA = positive score
        if current_latency <= sla:
            margin = (sla - current_latency) / sla
            return margin * 50
        else:
            # Over SLA = negative score
            overrun = (current_latency - sla) / sla
            return -min(overrun * 100, 100)

    def _score_error_rate(self, model: ModelInfo) -> float:
        """Score based on error rate."""
        error_rate = model.current_error_rate

        if error_rate is None:
            return 0  # Neutral if unknown

        if error_rate <= 0.01:  # < 1%
            return 20
        elif error_rate <= 0.03:  # 1-3%
            return 0
        elif error_rate <= 0.05:  # 3-5%
            return -30
        else:  # > 5%
            return -100  # Severely penalize

    def _score_capabilities(self, model: ModelInfo, request: RoutingRequest) -> float:
        """Score based on capability matching."""
        if not request.required_capabilities:
            return 0

        score = 0
        for cap in request.required_capabilities:
            if cap == "streaming" and model.supports_streaming:
                score += 10
            elif cap == "function_calling" and model.supports_function_calling:
                score += 20
            elif cap == "vision" and model.supports_vision:
                score += 15
            elif cap in ["streaming", "function_calling", "vision"]:
                # Required capability not present
                score -= 100

        return score

    def _budget_adjustment(self, model: ModelInfo, request: RoutingRequest) -> float:
        """Adjust score based on budget constraints."""
        if request.budget_remaining is None:
            return 0

        # Critical budget: strongly prefer cheap models
        if request.budget_remaining < self.COST_BUDGET_CRITICAL:
            if model.tier == ModelTier.FREE:
                return 100
            elif model.tier == ModelTier.BUDGET:
                return 50
            elif model.provider == "vllm":  # Self-hosted
                return 75
            else:
                return -50

        return 0

    def select_with_fallbacks(
        self,
        models: List[ModelInfo],
        request: RoutingRequest,
        policy_results: Optional[Dict[str, Tuple[bool, List[str]]]] = None,
        num_fallbacks: int = 2
    ) -> Tuple[Optional[ModelInfo], List[ModelInfo], str]:
        """
        Select best model with fallback options.

        Args:
            models: Available models
            request: Routing request
            policy_results: Policy evaluation results
            num_fallbacks: Number of fallback models to include

        Returns:
            Tuple of (selected_model, fallback_models, reason)
        """
        scored = self.rank_models(models, request, policy_results)

        if not scored:
            return None, [], "No models available matching criteria"

        selected = scored[0]
        fallbacks = [s.model for s in scored[1:num_fallbacks + 1]]

        reason = f"Selected {selected.model.model_id} (score: {selected.score:.1f}) - {', '.join(selected.reasons)}"

        return selected.model, fallbacks, reason

    def estimate_cost(
        self,
        model: ModelInfo,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Estimate cost for a request.

        Args:
            model: Model to use
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens

        Returns:
            Estimated cost in USD
        """
        input_cost = (input_tokens / 1000) * float(model.cost_per_1k_input)
        output_cost = (output_tokens / 1000) * float(model.cost_per_1k_output)

        return input_cost + output_cost
