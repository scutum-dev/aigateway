"""Shared test fixtures for unit and integration tests."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure `from shared.xxx import ...` works for all test modules that load service code.
# The shared package lives at src/shared/, so its parent (src/) must be on sys.path.
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_repo_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool, conn


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    client = AsyncMock()
    client.ping.return_value = True
    client.get.return_value = None
    client.set.return_value = True
    client.delete.return_value = 1
    return client


@pytest.fixture
def mock_http_client():
    """Mock httpx.AsyncClient."""
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {}
    response.raise_for_status = MagicMock()
    client.get.return_value = response
    client.post.return_value = response
    return client, response
