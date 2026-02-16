"""
Shared dependencies for Admin API routers.

Module-level state is set during the application lifespan (see main.py).
Routers should import this module and access attributes via `deps.db_pool`, etc.
"""

import os
from typing import Optional

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import HTTPException

# Shared connection pools / clients (set in main.py lifespan)
db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None
redis_client: Optional[aioredis.Redis] = None

# Configuration
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "$LITELLM_KEY")
WORKFLOW_ENGINE_URL = os.getenv("WORKFLOW_ENGINE_URL", "http://localhost:8085")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "")


async def get_db() -> asyncpg.Pool:
    """Dependency that returns the database pool or raises 503."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    return db_pool


def _internal_headers() -> dict:
    """Return headers for inter-service calls."""
    headers = {}
    if INTERNAL_SERVICE_KEY:
        headers["X-Service-Key"] = INTERNAL_SERVICE_KEY
    return headers
