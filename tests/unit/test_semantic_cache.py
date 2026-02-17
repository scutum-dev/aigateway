"""Unit tests for the Semantic Cache service.

Tests pure functions (messages_to_text, compute_cache_key, cosine_similarity)
and mock-based tests for find_similar_cached.
"""

import importlib.util
import json
import os
from unittest.mock import AsyncMock

import pytest

# Load the semantic-cache main module under a unique name to avoid sys.modules collision
_service_path = os.path.join(os.path.dirname(__file__), "../../src/semantic-cache/main.py")
_spec = importlib.util.spec_from_file_location("semantic_cache_main", _service_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

messages_to_text = _mod.messages_to_text
compute_cache_key = _mod.compute_cache_key
cosine_similarity = _mod.cosine_similarity
Message = _mod.Message
CacheEntry = _mod.CacheEntry


# ============================================================================
# messages_to_text
# ============================================================================


class TestMessagesToText:
    def test_single_message(self):
        """Should convert a single message to text."""
        messages = [Message(role="user", content="Hello")]
        text = messages_to_text(messages)
        assert text == "user: Hello"

    def test_multiple_messages(self):
        """Should join multiple messages with newlines."""
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hi"),
        ]
        text = messages_to_text(messages)
        assert "system: You are helpful" in text
        assert "user: Hi" in text
        assert "\n" in text

    def test_empty_messages(self):
        """Empty message list should produce empty string."""
        text = messages_to_text([])
        assert text == ""


# ============================================================================
# compute_cache_key
# ============================================================================


class TestComputeCacheKey:
    def test_deterministic(self):
        """Same input should produce same key."""
        msgs = [Message(role="user", content="Hello")]
        key1 = compute_cache_key(msgs, "gpt-4o")
        key2 = compute_cache_key(msgs, "gpt-4o")
        assert key1 == key2

    def test_model_isolation(self):
        """Different models should produce different keys."""
        msgs = [Message(role="user", content="Hello")]
        key1 = compute_cache_key(msgs, "gpt-4o")
        key2 = compute_cache_key(msgs, "claude-3-opus")
        assert key1 != key2

    def test_user_isolation(self):
        """Different users should produce different keys."""
        msgs = [Message(role="user", content="Hello")]
        key1 = compute_cache_key(msgs, "gpt-4o", user_id="user-a")
        key2 = compute_cache_key(msgs, "gpt-4o", user_id="user-b")
        assert key1 != key2

    def test_key_length(self):
        """Key should be 32 characters (truncated SHA-256)."""
        msgs = [Message(role="user", content="Hello")]
        key = compute_cache_key(msgs, "gpt-4o")
        assert len(key) == 32


# ============================================================================
# cosine_similarity
# ============================================================================


class TestCosineSimilarity:
    def test_identical_vectors(self):
        """Identical vectors should have similarity 1.0."""
        vec = [1.0, 2.0, 3.0]
        sim = cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.0."""
        sim = cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert abs(sim) < 1e-6

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity -1.0."""
        sim = cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert abs(sim - (-1.0)) < 1e-6

    def test_similar_vectors(self):
        """Similar but not identical vectors should have high similarity."""
        sim = cosine_similarity([1.0, 2.0, 3.0], [1.1, 2.1, 3.1])
        assert sim > 0.99


# ============================================================================
# find_similar_cached (mock-based)
# ============================================================================


find_similar_cached = _mod.find_similar_cached


class TestFindSimilarCached:
    @pytest.mark.asyncio
    async def test_no_entries(self):
        """Should return None when no cache entries exist."""
        mock_redis = AsyncMock()
        mock_redis.scan_iter = self._empty_async_iter
        _mod.redis_client = mock_redis

        result = await find_similar_cached([1.0, 0.0], "gpt-4o")
        assert result is None

    @pytest.mark.asyncio
    async def test_below_threshold(self):
        """Should return None when similarity is below threshold."""
        entry = CacheEntry(
            key="test",
            embedding=[0.0, 1.0],  # orthogonal to query
            response={"choices": []},
            model="gpt-4o",
            user_id=None,
            team_id=None,
            temperature=None,
            input_tokens=10,
            output_tokens=20,
            created_at="2025-01-01T00:00:00+00:00",
            expires_at="2099-01-01T00:00:00+00:00",
        )

        mock_redis = AsyncMock()
        mock_redis.scan_iter = self._make_async_iter([b"semantic_cache:gpt-4o:test"])
        mock_redis.get.return_value = json.dumps(entry.model_dump()).encode()
        _mod.redis_client = mock_redis

        result = await find_similar_cached([1.0, 0.0], "gpt-4o", threshold=0.92)
        assert result is None

    @pytest.mark.asyncio
    async def test_above_threshold(self):
        """Should return entry when similarity exceeds threshold."""
        entry = CacheEntry(
            key="test",
            embedding=[1.0, 0.01],  # very similar to [1.0, 0.0]
            response={"choices": [{"text": "Hello!"}]},
            model="gpt-4o",
            user_id=None,
            team_id=None,
            temperature=None,
            input_tokens=10,
            output_tokens=20,
            created_at="2025-01-01T00:00:00+00:00",
            expires_at="2099-01-01T00:00:00+00:00",
        )

        mock_redis = AsyncMock()
        mock_redis.scan_iter = self._make_async_iter([b"semantic_cache:gpt-4o:test"])
        mock_redis.hget.return_value = None  # force fallback to legacy string format
        mock_redis.get.return_value = json.dumps(entry.model_dump()).encode()
        mock_redis.delete = AsyncMock()
        _mod.redis_client = mock_redis

        result = await find_similar_cached([1.0, 0.0], "gpt-4o", threshold=0.90)
        assert result is not None
        found_entry, similarity = result
        assert similarity > 0.90

    @pytest.mark.asyncio
    async def test_user_isolation(self):
        """Should skip entries from different users."""
        entry = CacheEntry(
            key="test",
            embedding=[1.0, 0.0],
            response={"choices": []},
            model="gpt-4o",
            user_id="user-a",
            team_id=None,
            temperature=None,
            input_tokens=10,
            output_tokens=20,
            created_at="2025-01-01T00:00:00+00:00",
            expires_at="2099-01-01T00:00:00+00:00",
        )

        mock_redis = AsyncMock()
        mock_redis.scan_iter = self._make_async_iter([b"semantic_cache:gpt-4o:test"])
        mock_redis.get.return_value = json.dumps(entry.model_dump()).encode()
        _mod.redis_client = mock_redis

        result = await find_similar_cached([1.0, 0.0], "gpt-4o", user_id="user-b", threshold=0.5)
        assert result is None

    @staticmethod
    async def _empty_async_iter(*args, **kwargs):
        return
        yield  # make it an async generator

    @staticmethod
    def _make_async_iter(items):
        async def _iter(*args, **kwargs):
            for item in items:
                yield item

        return _iter
