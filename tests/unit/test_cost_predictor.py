"""Unit tests for the Cost Predictor service.

Tests pure functions (no mocks needed): token counting, pricing lookup,
output estimation.
"""

import importlib.util
import os
from decimal import Decimal

# Load the cost-predictor main module under a unique name to avoid sys.modules collision
_service_path = os.path.join(os.path.dirname(__file__), "../../src/cost-predictor/main.py")
_spec = importlib.util.spec_from_file_location("cost_predictor_main", _service_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

count_tokens = _mod.count_tokens
count_message_tokens = _mod.count_message_tokens
get_encoding = _mod.get_encoding
get_model_pricing = _mod.get_model_pricing
estimate_output_tokens = _mod.estimate_output_tokens
MODEL_PRICING = _mod.MODEL_PRICING


# ============================================================================
# Token Counting
# ============================================================================


class TestCountTokens:
    def test_known_text(self):
        """Token count for a known string should be > 0."""
        tokens = count_tokens("Hello, world!", "gpt-4o")
        assert tokens > 0

    def test_empty_string(self):
        """Empty string should produce 0 tokens."""
        tokens = count_tokens("", "gpt-4o")
        assert tokens == 0

    def test_longer_text_more_tokens(self):
        """Longer text should produce more tokens."""
        short = count_tokens("Hi", "gpt-4o")
        long = count_tokens("Hello, this is a much longer piece of text for testing.", "gpt-4o")
        assert long > short


class TestCountMessageTokens:
    def test_single_message(self):
        """Single message should include overhead tokens."""
        messages = [{"role": "user", "content": "Hello"}]
        tokens = count_message_tokens(messages, "gpt-4o")
        # At minimum: 4 (per message) + content tokens + 3 (reply priming)
        assert tokens >= 7

    def test_message_overhead(self):
        """Multiple messages should include per-message overhead."""
        one_msg = count_message_tokens([{"role": "user", "content": "Hello"}], "gpt-4o")
        two_msg = count_message_tokens(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
            "gpt-4o",
        )
        # Two messages should have more overhead than one
        assert two_msg > one_msg

    def test_empty_messages(self):
        """Empty message list should return just the reply priming tokens."""
        tokens = count_message_tokens([], "gpt-4o")
        assert tokens == 3  # reply priming only


# ============================================================================
# Encoding
# ============================================================================


class TestGetEncoding:
    def test_known_model(self):
        """Known model should return an encoding."""
        enc = get_encoding("gpt-4o")
        assert enc is not None

    def test_unknown_model_fallback(self):
        """Unknown model should fall back to cl100k_base."""
        enc = get_encoding("totally-unknown-model-xyz")
        assert enc is not None


# ============================================================================
# Pricing
# ============================================================================


class TestGetModelPricing:
    def test_direct_match(self):
        """Direct model name match should return exact pricing."""
        pricing = get_model_pricing("gpt-4o")
        assert pricing["input"] == Decimal("2.50")
        assert pricing["output"] == Decimal("10.00")

    def test_partial_match(self):
        """Partial match should find a model."""
        pricing = get_model_pricing("claude-sonnet-4.5-latest")
        # Should match claude-sonnet-4.5
        assert pricing["input"] > 0

    def test_default_pricing(self):
        """Unknown model should return default pricing."""
        pricing = get_model_pricing("completely-unknown-model-12345")
        assert pricing["input"] == Decimal("1.00")
        assert pricing["output"] == Decimal("3.00")

    def test_case_insensitive(self):
        """Pricing lookup should be case-insensitive."""
        pricing = get_model_pricing("GPT-4O")
        assert pricing["input"] == Decimal("2.50")


# ============================================================================
# Output Token Estimation
# ============================================================================


class TestEstimateOutputTokens:
    def test_with_max_tokens_reasoning(self):
        """Reasoning models should use high utilization of max_tokens."""
        output = estimate_output_tokens(100, 1000, model="o3")
        assert output == 850  # 0.85 * 1000

    def test_with_max_tokens_standard(self):
        """Standard models should use moderate utilization."""
        output = estimate_output_tokens(100, 1000, model="gpt-4o")
        assert output == 550  # 0.55 * 1000

    def test_with_max_tokens_fast(self):
        """Fast/haiku models should use lower utilization."""
        # Use claude-3-haiku which matches "haiku" profile (0.35 utilization)
        output = estimate_output_tokens(100, 1000, model="claude-3-haiku")
        assert output == 350  # 0.35 * 1000

    def test_without_max_tokens(self):
        """Without max_tokens, should estimate from input length."""
        output = estimate_output_tokens(500, None, model="gpt-4o")
        assert output == 1000  # 500 * 2.0

    def test_cap_at_4096(self):
        """Output should be capped at 4096 when no max_tokens."""
        output = estimate_output_tokens(10000, None, model="gpt-4o")
        assert output == 4096
