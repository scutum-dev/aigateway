"""Integration tests for the Semantic Cache API.

Tests HTTP endpoints and ServiceAuthMiddleware via ASGI test client.
"""

import os
import json
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest
import httpx

# Load the semantic-cache module
_service_path = os.path.join(os.path.dirname(__file__), "../../src/semantic-cache/main.py")
_spec = importlib.util.spec_from_file_location("semantic_cache_integ", _service_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

app = _mod.app

SERVICE_KEY = "test-integration-key"


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module state between tests."""
    original_key = _mod.INTERNAL_SERVICE_KEY
    original_redis = _mod.redis_client
    original_http = _mod.http_client
    original_stats = dict(_mod.cache_stats)
    yield
    _mod.INTERNAL_SERVICE_KEY = original_key
    _mod.redis_client = original_redis
    _mod.http_client = original_http
    _mod.cache_stats.update(original_stats)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    r = AsyncMock()
    r.ping.return_value = True
    r.get.return_value = None
    r.set.return_value = True
    r.delete.return_value = 1
    r.ttl.return_value = 3600
    r.info.return_value = {"used_memory": 1024 * 1024}

    async def empty_scan(*args, **kwargs):
        return
        yield

    r.scan_iter = empty_scan
    return r


@pytest.fixture
def client(mock_redis):
    """ASGI test client (dev mode)."""
    _mod.INTERNAL_SERVICE_KEY = ""
    _mod.redis_client = mock_redis
    _mod.http_client = AsyncMock()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def authed_client(mock_redis):
    """ASGI test client with auth required."""
    _mod.INTERNAL_SERVICE_KEY = SERVICE_KEY
    _mod.redis_client = mock_redis
    _mod.http_client = AsyncMock()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# ServiceAuthMiddleware
# ============================================================================


class TestServiceAuthMiddleware:
    @pytest.mark.asyncio
    async def test_health_exempt(self, authed_client):
        """Health endpoint should bypass auth."""
        resp = await authed_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reject_without_key(self, authed_client):
        """Protected endpoint should return 401."""
        resp = await authed_client.get("/stats")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_accept_correct_key(self, authed_client, mock_redis):
        """Protected endpoint should work with correct key."""
        resp = await authed_client.get(
            "/stats",
            headers={"X-Service-Key": SERVICE_KEY}
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_dev_mode_no_auth(self, client):
        """Dev mode should allow all requests."""
        resp = await client.get("/stats")
        assert resp.status_code == 200


# ============================================================================
# /health
# ============================================================================


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_redis_ok(self, client, mock_redis):
        """Should return healthy when Redis is connected."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["redis"] == "connected"

    @pytest.mark.asyncio
    async def test_health_redis_down(self, client, mock_redis):
        """Should return degraded when Redis is down."""
        mock_redis.ping.side_effect = ConnectionError("Connection refused")
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["redis"] == "disconnected"


# ============================================================================
# /lookup
# ============================================================================


class TestLookupEndpoint:
    @pytest.mark.asyncio
    async def test_cache_miss(self, client, mock_redis):
        """Should return cache miss when no matching entry."""
        # Mock get_embedding to return a vector
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}]
        }
        _mod.http_client.post.return_value = mock_resp

        resp = await client.post("/lookup", json={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "gpt-4o",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hit"] is False

    @pytest.mark.asyncio
    async def test_cache_hit(self, client, mock_redis):
        """Should return cached response on hit."""
        # Mock get_embedding
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"embedding": [1.0, 0.0, 0.0]}]
        }
        _mod.http_client.post.return_value = mock_resp

        # Set up a cached entry that will match
        now = datetime.utcnow()
        entry = _mod.CacheEntry(
            key="test-key",
            embedding=[1.0, 0.0, 0.0],  # identical to query
            response={"choices": [{"text": "Hi!"}]},
            model="gpt-4o",
            user_id=None,
            team_id=None,
            temperature=None,
            input_tokens=10,
            output_tokens=5,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
        )

        # Mock scan_iter to return one key, get to return the entry
        async def mock_scan(*args, **kwargs):
            yield b"semantic_cache:gpt-4o:test-key"

        mock_redis.scan_iter = mock_scan
        mock_redis.get.return_value = json.dumps(entry.model_dump()).encode()

        resp = await client.post("/lookup", json={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "gpt-4o",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hit"] is True
        assert data["similarity"] > 0.99
        assert data["response"]["choices"][0]["text"] == "Hi!"


# ============================================================================
# /store
# ============================================================================


class TestStoreEndpoint:
    @pytest.mark.asyncio
    async def test_store_entry(self, client, mock_redis):
        """Should store a cache entry."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.5, 0.5, 0.5]}]
        }
        _mod.http_client.post.return_value = mock_resp

        resp = await client.post("/store", json={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "gpt-4o",
            "response": {"choices": [{"text": "Hi!"}]},
            "input_tokens": 10,
            "output_tokens": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stored"
        assert "cache_key" in data
        assert "expires_at" in data

        # Verify Redis was called
        mock_redis.set.assert_called_once()


# ============================================================================
# /invalidate
# ============================================================================


class TestInvalidateEndpoints:
    @pytest.mark.asyncio
    async def test_invalidate_by_key_and_model(self, client, mock_redis):
        """Should invalidate a specific cache entry."""
        resp = await client.delete("/invalidate/test-key", params={"model": "gpt-4o"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invalidated"
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_model(self, client, mock_redis):
        """Should invalidate all entries for a model."""
        async def mock_scan(*args, **kwargs):
            yield b"semantic_cache:gpt-4o:key1"
            yield b"semantic_cache:gpt-4o:key2"

        mock_redis.scan_iter = mock_scan

        resp = await client.delete("/invalidate-model/gpt-4o")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invalidated"
        assert data["deleted"] == 2

    @pytest.mark.asyncio
    async def test_invalidate_user(self, client, mock_redis):
        """Should invalidate all entries for a user."""
        entry = {"user_id": "user-1", "key": "test"}

        async def mock_scan(*args, **kwargs):
            yield b"semantic_cache:gpt-4o:key1"

        mock_redis.scan_iter = mock_scan
        mock_redis.get.return_value = json.dumps(entry).encode()

        resp = await client.delete("/invalidate-user/user-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invalidated"


# ============================================================================
# /stats
# ============================================================================


class TestStatsEndpoint:
    @pytest.mark.asyncio
    async def test_stats(self, client, mock_redis):
        """Should return cache statistics."""
        resp = await client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_entries" in data
        assert "hits" in data
        assert "misses" in data
        assert "hit_rate" in data
        assert "memory_used_mb" in data


# ============================================================================
# /entries
# ============================================================================


class TestEntriesEndpoint:
    @pytest.mark.asyncio
    async def test_list_empty(self, client, mock_redis):
        """Should return empty list when no entries."""
        resp = await client.get("/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_list_with_entries(self, client, mock_redis):
        """Should return cached entries."""
        entry = {
            "key": "test",
            "embedding": [0.1, 0.2],
            "response": {"choices": []},
            "model": "gpt-4o",
            "user_id": None,
            "created_at": "2025-01-01T00:00:00",
        }

        async def mock_scan(*args, **kwargs):
            yield b"semantic_cache:gpt-4o:test"

        mock_redis.scan_iter = mock_scan
        mock_redis.get.return_value = json.dumps(entry).encode()

        resp = await client.get("/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        # Embedding should be stripped from response
        assert "embedding" not in data["entries"][0]
