"""Semantic Cache router -- cache statistics, entries management, and settings."""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

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


class CacheLookupRequest(BaseModel):
    prompt: str = Field(..., description="Prompt text to look up in cache")
    model: Optional[str] = Field(None, description="Filter by model name")


class CacheStoreRequest(BaseModel):
    prompt: str
    model: str
    response_body: dict
    token_count: Optional[int] = None
    ttl_seconds: Optional[int] = Field(None, description="Time-to-live for cache entries in seconds")


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
    row = await conn.fetchrow(
        "SELECT value FROM platform_settings WHERE key = $1", f"cache_{key}"
    )
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


async def _get_embedding(text: str) -> list[float] | None:
    """Generate embedding via LiteLLM /embeddings endpoint."""
    if not deps.http_client:
        return None
    try:
        resp = await deps.http_client.post(
            f"{deps.LITELLM_URL}/v1/embeddings",
            headers={
                "Authorization": f"Bearer {deps.LITELLM_MASTER_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "text-embedding-3-small", "input": text},
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["data"][0]["embedding"]
        logger.debug("Embedding request returned %s", resp.status_code)
    except Exception as e:
        logger.debug("Failed to get embedding: %s", e)
    return None


async def _check_pgvector_available(conn) -> bool:
    """Check if pgvector extension is available."""
    try:
        row = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        return bool(row)
    except Exception:
        return False


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
        similarity_threshold = await _get_cache_setting(
            conn, "similarity_threshold", "0.92"
        )
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
    """Update cache settings (threshold, TTL, enabled, max_entries)."""
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
                    "type": "redis",
                    "ttl": data.ttl_seconds,
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


@router.post("/cache/lookup")
async def cache_lookup(
    data: CacheLookupRequest,
    user: UserInfo = Depends(get_current_user),
):
    """Look up a cached response by prompt hash (exact match) with semantic fallback.

    First tries SHA-256 hash exact matching, then falls back to embedding-based
    semantic similarity search when pgvector is available.
    """
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    prompt_hash = hashlib.sha256(data.prompt.encode()).hexdigest()

    async with deps.db_pool.acquire() as conn:
        # Check if caching is enabled
        enabled = await _get_cache_setting(conn, "enabled", "true")
        if str(enabled).lower() not in ("true", "1", "yes"):
            return {"hit": False, "reason": "cache_disabled"}

        # Check if table exists
        table_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'semantic_cache')"
        )
        if not table_exists:
            return {"hit": False, "reason": "table_not_found"}

        # Hash-based exact match lookup
        conditions = ["prompt_hash = $1", "(expires_at IS NULL OR expires_at > NOW())"]
        params: list = [prompt_hash]
        idx = 2

        if data.model:
            conditions.append(f"model = ${idx}")
            params.append(data.model)
            idx += 1

        where = " AND ".join(conditions)
        row = await conn.fetchrow(
            f"""
            SELECT id, prompt_hash, model, response_body, token_count, hit_count, created_at
            FROM semantic_cache
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT 1
            """,
            *params,
        )

        if row:
            # Update hit count
            await conn.execute(
                "UPDATE semantic_cache SET hit_count = hit_count + 1, last_hit_at = NOW() WHERE id = $1",
                row["id"],
            )
            response_body = row["response_body"]
            if isinstance(response_body, str):
                response_body = json.loads(response_body)

            return {
                "hit": True,
                "match_type": "exact",
                "cache_id": str(row["id"]),
                "model": row["model"],
                "response": response_body,
                "token_count": row["token_count"],
                "hit_count": (row["hit_count"] or 0) + 1,
            }

        # ----- Semantic similarity fallback -----
        has_pgvector = await _check_pgvector_available(conn)
        if has_pgvector:
            threshold_setting = await _get_cache_setting(
                conn, "similarity_threshold", "0.92"
            )
            threshold = float(threshold_setting)

            embedding = await _get_embedding(data.prompt)
            if embedding is not None:
                embedding_str = json.dumps(embedding)

                sem_row = await conn.fetchrow(
                    """
                    SELECT id, prompt_hash, model, response_body, token_count,
                           hit_count, created_at,
                           1 - (embedding <=> $1::vector) as similarity
                    FROM semantic_cache
                    WHERE (expires_at IS NULL OR expires_at > NOW())
                      AND embedding IS NOT NULL
                      AND 1 - (embedding <=> $1::vector) >= $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT 1
                    """,
                    embedding_str,
                    threshold,
                )

                if sem_row:
                    await conn.execute(
                        "UPDATE semantic_cache SET hit_count = hit_count + 1, last_hit_at = NOW() WHERE id = $1",
                        sem_row["id"],
                    )
                    response_body = sem_row["response_body"]
                    if isinstance(response_body, str):
                        response_body = json.loads(response_body)

                    return {
                        "hit": True,
                        "match_type": "semantic",
                        "similarity": round(float(sem_row["similarity"]), 4),
                        "cache_id": str(sem_row["id"]),
                        "model": sem_row["model"],
                        "response": response_body,
                        "token_count": sem_row["token_count"],
                        "hit_count": (sem_row["hit_count"] or 0) + 1,
                    }

        return {"hit": False, "reason": "no_match"}


@router.post("/cache/store")
async def cache_store(
    data: CacheStoreRequest,
    user: UserInfo = Depends(require_admin),
):
    """Store a prompt-response pair in the cache."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    prompt_hash = hashlib.sha256(data.prompt.encode()).hexdigest()

    async with deps.db_pool.acquire() as conn:
        # Check if caching is enabled
        enabled = await _get_cache_setting(conn, "enabled", "true")
        if str(enabled).lower() not in ("true", "1", "yes"):
            raise HTTPException(status_code=400, detail="Cache is disabled")

        table_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'semantic_cache')"
        )
        if not table_exists:
            raise HTTPException(status_code=503, detail="Cache table not found")

        # Get TTL from settings or override
        ttl = data.ttl_seconds
        if not ttl:
            ttl_setting = await _get_cache_setting(conn, "ttl_seconds", "3600")
            ttl = int(ttl_setting)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        # Generate embedding (best-effort, store without if it fails)
        embedding = None
        has_pgvector = await _check_pgvector_available(conn)
        if has_pgvector:
            embedding = await _get_embedding(data.prompt)

        # Check if entry with same hash exists
        existing = await conn.fetchrow(
            "SELECT id FROM semantic_cache WHERE prompt_hash = $1 AND model = $2",
            prompt_hash, data.model,
        )

        if existing:
            # Update existing entry
            if embedding is not None:
                embedding_str = json.dumps(embedding)
                await conn.execute(
                    """
                    UPDATE semantic_cache
                    SET response_body = $1::jsonb, token_count = $2,
                        expires_at = $3, embedding = $4::vector
                    WHERE id = $5
                    """,
                    json.dumps(data.response_body),
                    data.token_count,
                    expires_at,
                    embedding_str,
                    existing["id"],
                )
            else:
                await conn.execute(
                    """
                    UPDATE semantic_cache
                    SET response_body = $1::jsonb, token_count = $2, expires_at = $3
                    WHERE id = $4
                    """,
                    json.dumps(data.response_body),
                    data.token_count,
                    expires_at,
                    existing["id"],
                )
            cache_id = str(existing["id"])
        else:
            if embedding is not None:
                embedding_str = json.dumps(embedding)
                row = await conn.fetchrow(
                    """
                    INSERT INTO semantic_cache
                        (prompt_hash, model, request_body, response_body,
                         token_count, expires_at, embedding)
                    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7::vector)
                    RETURNING id
                    """,
                    prompt_hash,
                    data.model,
                    json.dumps({"prompt": data.prompt}),
                    json.dumps(data.response_body),
                    data.token_count,
                    expires_at,
                    embedding_str,
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO semantic_cache
                        (prompt_hash, model, request_body, response_body,
                         token_count, expires_at)
                    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6)
                    RETURNING id
                    """,
                    prompt_hash,
                    data.model,
                    json.dumps({"prompt": data.prompt}),
                    json.dumps(data.response_body),
                    data.token_count,
                    expires_at,
                )
            cache_id = str(row["id"])

        logger.info("Cached response for model %s (hash: %s)", data.model, prompt_hash[:12])
        return {"status": "stored", "cache_id": cache_id, "expires_at": str(expires_at)}


@router.delete("/cache/entries/{entry_id}")
async def delete_cache_entry(entry_id: str, user: UserInfo = Depends(require_admin)):
    """Delete a specific cache entry."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM semantic_cache WHERE id = $1::uuid", entry_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Cache entry not found")
        return {"status": "ok"}
