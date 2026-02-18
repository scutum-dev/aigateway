"""Semantic Cache router -- cache statistics, entries management, and settings.

Caching is handled transparently by LiteLLM's built-in redis-semantic cache.
These endpoints provide a management layer for the Admin UI to view stats,
adjust settings, and clear the cache.
"""

import json
import logging

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CacheSettings(BaseModel):
    enabled: bool = Field(True, description="Whether the semantic cache is active")
    similarity_threshold: float = Field(0.92, description="Minimum similarity for a cache hit (0.0-1.0)")
    ttl_seconds: int = 3600
    max_entries: int = Field(10000, description="Maximum number of cached entries")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_entry(row) -> dict:
    return {
        "id": str(row["id"]),
        "prompt_hash": row["prompt_hash"],
        "model": row["model"],
        "token_count": row["token_count"],
        "hit_count": row["hit_count"],
        "last_hit_at": str(row["last_hit_at"]) if row["last_hit_at"] else None,
        "created_at": str(row["created_at"]) if row["created_at"] else None,
        "expires_at": str(row["expires_at"]) if row["expires_at"] else None,
    }


async def _get_cache_setting(conn, key: str, default: str) -> str:
    """Read a cache setting from platform_settings."""
    row = await conn.fetchrow("SELECT value FROM platform_settings WHERE key = $1", f"cache_{key}")
    if row:
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]
    return default


async def _set_cache_setting(conn, key: str, value) -> None:
    """Write a cache setting to platform_settings."""
    await conn.execute(
        """
        INSERT INTO platform_settings (key, value)
        VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE SET value = $2
        """,
        f"cache_{key}",
        json.dumps(value),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/cache/stats")
async def get_cache_stats(user: UserInfo = Depends(get_current_user)):
    """Get cache statistics (total entries, hit rate, size)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        # Check if table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'semantic_cache'
            )
            """
        )
        if not table_exists:
            return {
                "total_entries": 0,
                "total_hits": 0,
                "hit_rate": 0.0,
                "cache_size_mb": 0.0,
                "avg_token_savings": 0.0,
            }

        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total_entries,
                COALESCE(SUM(hit_count), 0) AS total_hits,
                COALESCE(AVG(token_count), 0) AS avg_token_count
            FROM semantic_cache
            """
        )

        total_entries = stats["total_entries"] or 0
        total_hits = stats["total_hits"] or 0
        avg_token_count = float(stats["avg_token_count"] or 0)

        # Estimate cache size from table
        size_row = await conn.fetchrow(
            """
            SELECT pg_total_relation_size('semantic_cache') AS size_bytes
            """
        )
        size_mb = (size_row["size_bytes"] or 0) / (1024 * 1024)

        # Hit rate: total_hits / (total_hits + total_entries) as a rough estimate
        hit_rate = 0.0
        if total_hits + total_entries > 0:
            hit_rate = round(total_hits / (total_hits + total_entries) * 100, 2)

        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "hit_rate": hit_rate,
            "cache_size_mb": round(size_mb, 2),
            "avg_token_savings": round(avg_token_count, 1),
        }


@router.post("/cache/clear")
async def clear_cache(user: UserInfo = Depends(require_admin)):
    """Clear all cache entries."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'semantic_cache'
            )
            """
        )
        if not table_exists:
            return {"status": "ok", "deleted": 0}

        result = await conn.execute("DELETE FROM semantic_cache")
        count = int(result.split(" ")[-1]) if result else 0
        logger.info("Cache cleared: %d entries deleted by %s", count, user.user_id)
        return {"status": "ok", "deleted": count}


@router.get("/cache/settings")
async def get_cache_settings(user: UserInfo = Depends(get_current_user)):
    """Get current cache settings."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        enabled = await _get_cache_setting(conn, "enabled", "true")
        similarity_threshold = await _get_cache_setting(conn, "similarity_threshold", "0.92")
        ttl_seconds = await _get_cache_setting(conn, "ttl_seconds", "3600")
        max_entries = await _get_cache_setting(conn, "max_entries", "10000")

    return CacheSettings(
        enabled=str(enabled).lower() in ("true", "1", "yes"),
        similarity_threshold=float(similarity_threshold),
        ttl_seconds=int(ttl_seconds),
        max_entries=int(max_entries),
    )


@router.put("/cache/settings")
async def update_cache_settings(
    data: CacheSettings,
    user: UserInfo = Depends(require_admin),
):
    """Update cache settings (threshold, TTL, enabled, max_entries).

    Syncs enabled/TTL to LiteLLM's redis-semantic cache at runtime.
    """
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        await _set_cache_setting(conn, "enabled", data.enabled)
        await _set_cache_setting(conn, "similarity_threshold", data.similarity_threshold)
        await _set_cache_setting(conn, "ttl_seconds", data.ttl_seconds)
        await _set_cache_setting(conn, "max_entries", data.max_entries)

    # Sync cache settings to LiteLLM
    if deps.http_client:
        try:
            litellm_cache_config = {
                "cache": data.enabled,
            }
            if data.enabled:
                litellm_cache_config["cache_params"] = {
                    "type": "redis-semantic",
                    "ttl": data.ttl_seconds,
                    "similarity_threshold": data.similarity_threshold,
                }
            resp = await deps.http_client.post(
                f"{deps.LITELLM_URL}/cache/set",
                headers={
                    "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
                    "Content-Type": "application/json",
                },
                json=litellm_cache_config,
            )
            if resp.status_code == 200:
                logger.info("Synced cache settings to LiteLLM: enabled=%s ttl=%s", data.enabled, data.ttl_seconds)
            else:
                logger.debug("LiteLLM /cache/set returned %s (may not be supported)", resp.status_code)
        except Exception as e:
            logger.debug("Could not sync cache settings to LiteLLM: %s", e)

    return {
        "enabled": data.enabled,
        "similarity_threshold": data.similarity_threshold,
        "ttl_seconds": data.ttl_seconds,
        "max_entries": data.max_entries,
    }


@router.get("/cache/entries")
async def list_cache_entries(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserInfo = Depends(get_current_user),
):
    """List recent cache entries (paginated)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'semantic_cache'
            )
            """
        )
        if not table_exists:
            return []

        rows = await conn.fetch(
            """
            SELECT id, prompt_hash, model, token_count, hit_count,
                   last_hit_at, created_at, expires_at
            FROM semantic_cache
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [_row_to_entry(row) for row in rows]


@router.delete("/cache/entries/{entry_id}")
async def delete_cache_entry(entry_id: str, user: UserInfo = Depends(require_admin)):
    """Delete a specific cache entry."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM semantic_cache WHERE id = $1::uuid", entry_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Cache entry not found")
        return {"status": "ok"}
