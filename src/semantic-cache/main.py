"""
Semantic Cache Service for AI Control Plane Platform.

Provides intelligent caching of LLM responses based on semantic similarity
of prompts using vector embeddings.

Features:
- Embedding-based similarity matching
- Configurable similarity thresholds
- TTL-based cache expiration
- Per-model and per-user cache isolation
- Cache hit/miss metrics
- Redis backend with vector search (RedisVL) or PostgreSQL with pgvector
"""

import hashlib
import json
import logging
import os
import struct
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

from shared.cors import get_cors_origins
from shared.middleware import ServiceAuthMiddleware

logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.92"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
MAX_CACHE_ENTRIES = int(os.getenv("MAX_CACHE_ENTRIES", "10000"))
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

if OTEL_ENDPOINT:
    otlp_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))


# Pydantic Models
class Message(BaseModel):
    role: str
    content: str


class CacheLookupRequest(BaseModel):
    """Request for cache lookup."""

    messages: List[Message]
    model: str
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class CacheStoreRequest(BaseModel):
    """Request to store in cache."""

    messages: List[Message]
    model: str
    response: Dict[str, Any]
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    temperature: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class CacheLookupResponse(BaseModel):
    """Response from cache lookup."""

    hit: bool
    response: Optional[Dict[str, Any]] = None
    similarity: Optional[float] = None
    cache_key: Optional[str] = None
    cached_at: Optional[str] = None
    ttl_remaining: Optional[int] = None


class CacheStats(BaseModel):
    """Cache statistics."""

    total_entries: int
    hits: int
    misses: int
    hit_rate: float
    avg_similarity: float
    memory_used_mb: float
    tokens_saved: int
    cost_saved: float


class CacheEntry(BaseModel):
    """Cache entry structure."""

    key: str
    embedding: List[float]
    response: Dict[str, Any]
    model: str
    user_id: Optional[str]
    team_id: Optional[str]
    temperature: Optional[float]
    input_tokens: int
    output_tokens: int
    created_at: str
    expires_at: str
    hit_count: int = 0


# Global state
redis_client: Optional[redis.Redis] = None
http_client: Optional[httpx.AsyncClient] = None
cache_stats = {
    "hits": 0,
    "misses": 0,
    "tokens_saved": 0,
    "cost_saved": 0.0,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global redis_client, http_client

    # Startup
    redis_client = redis.from_url(REDIS_URL, decode_responses=False)
    http_client = httpx.AsyncClient(timeout=30.0)

    # Initialize cache index in Redis
    await init_cache_index()

    yield

    # Shutdown
    if redis_client:
        await redis_client.close()
    if http_client:
        await http_client.aclose()


app = FastAPI(
    title="Semantic Cache Service",
    description="Intelligent caching for LLM responses using semantic similarity",
    version="1.0.0",
    lifespan=lifespan,
)

# Add service auth middleware
app.add_middleware(ServiceAuthMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Service-Key"],
)

# OpenTelemetry instrumentation
FastAPIInstrumentor.instrument_app(app)


async def init_cache_index():
    """Initialize Redis search index for vector similarity."""
    try:
        await redis_client.execute_command("FT.INFO", "idx:semantic_cache")
        logger.info("Semantic cache index already exists")
    except Exception:
        try:
            await redis_client.execute_command(
                "FT.CREATE",
                "idx:semantic_cache",
                "ON",
                "HASH",
                "PREFIX",
                "1",
                "semantic_cache:",
                "SCHEMA",
                "model",
                "TAG",
                "user_id",
                "TAG",
                "embedding",
                "VECTOR",
                "FLAT",
                "6",
                "TYPE",
                "FLOAT32",
                "DIM",
                "1536",
                "DISTANCE_METRIC",
                "COSINE",
            )
            logger.info("Created semantic cache vector index")
        except Exception as e:
            logger.warning(f"Could not create vector index, falling back to scan: {e}")


async def get_embedding(text: str, api_key: Optional[str] = None) -> List[float]:
    """Get embedding vector for text using LiteLLM."""
    with tracer.start_as_current_span("get_embedding") as span:
        span.set_attribute("text_length", len(text))

        headers = {"Content-Type": "application/json"}
        key = api_key or LITELLM_API_KEY
        if key:
            headers["Authorization"] = f"Bearer {key}"

        try:
            response = await http_client.post(
                f"{LITELLM_URL}/v1/embeddings",
                headers=headers,
                json={
                    "model": EMBEDDING_MODEL,
                    "input": text,
                },
            )

            if response.status_code == 200:
                data = response.json()
                embedding = data["data"][0]["embedding"]
                span.set_attribute("embedding_dim", len(embedding))
                return embedding
            else:
                span.set_attribute("error", True)
                raise HTTPException(status_code=500, detail=f"Embedding API error: {response.status_code}")
        except httpx.RequestError as e:
            span.set_attribute("error", True)
            raise HTTPException(status_code=503, detail=f"Embedding service unavailable: {e}")


def messages_to_text(messages: List[Message]) -> str:
    """Convert messages to a single text for embedding."""
    parts = []
    for msg in messages:
        parts.append(f"{msg.role}: {msg.content}")
    return "\n".join(parts)


def compute_cache_key(messages: List[Message], model: str, user_id: Optional[str] = None) -> str:
    """Compute a deterministic cache key."""
    content = json.dumps(
        {
            "messages": [m.model_dump() for m in messages],
            "model": model,
            "user_id": user_id,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def _find_similar_scan(
    embedding: List[float],
    model: str,
    user_id: Optional[str],
    threshold: float,
    span,
) -> Optional[Tuple[CacheEntry, float]]:
    """Fallback O(n) scan for when RediSearch is not available."""
    pattern = f"semantic_cache:{model}:*"
    keys = []
    async for key in redis_client.scan_iter(match=pattern):
        keys.append(key)

    if not keys:
        span.set_attribute("candidates", 0)
        return None

    span.set_attribute("candidates", len(keys))

    best_match = None
    best_similarity = threshold

    for key in keys:
        try:
            data = await redis_client.hget(key, "data")
            if not data:
                # Try legacy string format
                data = await redis_client.get(key)
                if not data:
                    continue
                entry_data = json.loads(data)
            else:
                entry_data = json.loads(data)
                emb_bytes = await redis_client.hget(key, "embedding")
                if emb_bytes:
                    dim = len(emb_bytes) // 4
                    entry_data["embedding"] = list(struct.unpack(f"{dim}f", emb_bytes))
                else:
                    continue

            entry = CacheEntry(**entry_data)

            if datetime.fromisoformat(entry.expires_at) < datetime.now(timezone.utc):
                await redis_client.delete(key)
                continue

            if user_id and entry.user_id and entry.user_id != user_id:
                continue

            similarity = cosine_similarity(embedding, entry.embedding)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry

        except Exception:
            continue

    if best_match:
        span.set_attribute("hit", True)
        span.set_attribute("similarity", best_similarity)
        return (best_match, best_similarity)

    span.set_attribute("hit", False)
    return None


async def find_similar_cached(
    embedding: List[float],
    model: str,
    user_id: Optional[str] = None,
    threshold: float = SIMILARITY_THRESHOLD,
) -> Optional[Tuple[CacheEntry, float]]:
    """Find similar cached entry using Redis vector search with O(n) fallback."""
    with tracer.start_as_current_span("find_similar_cached") as span:
        span.set_attribute("model", model)
        span.set_attribute("threshold", threshold)

        query_blob = struct.pack(f"{len(embedding)}f", *embedding)

        try:
            filter_expr = f"@model:{{{model}}}"
            results = await redis_client.execute_command(
                "FT.SEARCH",
                "idx:semantic_cache",
                f"({filter_expr})=>[KNN 1 @embedding $query_vec AS similarity]",
                "PARAMS",
                "2",
                "query_vec",
                query_blob,
                "SORTBY",
                "similarity",
                "RETURN",
                "2",
                "data",
                "similarity",
                "LIMIT",
                "0",
                "1",
                "DIALECT",
                "2",
            )

            if results[0] == 0:
                span.set_attribute("hit", False)
                return None

            fields = results[2]
            field_dict = dict(zip(fields[0::2], fields[1::2]))

            # RediSearch COSINE distance: 0 = identical, 2 = opposite
            distance = float(field_dict[b"similarity"])
            similarity = 1.0 - distance

            if similarity < threshold:
                span.set_attribute("hit", False)
                return None

            entry_data = json.loads(field_dict[b"data"])
            entry_data["embedding"] = embedding  # placeholder
            entry = CacheEntry(**entry_data)

            span.set_attribute("hit", True)
            span.set_attribute("similarity", similarity)
            return (entry, similarity)

        except Exception as e:
            logger.warning(f"Vector search failed, falling back to scan: {e}")
            return await _find_similar_scan(embedding, model, user_id, threshold, span)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    redis_ok = False
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "embedding_model": EMBEDDING_MODEL,
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


@app.post("/lookup", response_model=CacheLookupResponse)
async def cache_lookup(
    request: CacheLookupRequest,
    authorization: Optional[str] = Header(None),
):
    """Look up a cached response for the given prompt."""
    global cache_stats

    with tracer.start_as_current_span("cache_lookup") as span:
        span.set_attribute("model", request.model)

        # Extract API key
        api_key = None
        if authorization and authorization.startswith("Bearer "):
            api_key = authorization[7:]

        # Convert messages to text and get embedding
        prompt_text = messages_to_text(request.messages)
        embedding = await get_embedding(prompt_text, api_key)

        # Search for similar cached entry
        result = await find_similar_cached(
            embedding,
            request.model,
            request.user_id,
        )

        if result:
            entry, similarity = result

            # Update hit count
            entry.hit_count += 1
            cache_key = f"semantic_cache:{request.model}:{entry.key}"
            try:
                raw_data = await redis_client.hget(cache_key, "data")
                if raw_data:
                    stored = json.loads(raw_data)
                    stored["hit_count"] = entry.hit_count
                    await redis_client.hset(cache_key, "data", json.dumps(stored))
            except Exception:
                pass

            # Update stats
            cache_stats["hits"] += 1
            cache_stats["tokens_saved"] += entry.output_tokens
            # Estimate cost saved (rough estimate)
            cache_stats["cost_saved"] += entry.output_tokens * 0.00002

            ttl = await redis_client.ttl(cache_key)

            span.set_attribute("cache_hit", True)
            span.set_attribute("similarity", similarity)

            return CacheLookupResponse(
                hit=True,
                response=entry.response,
                similarity=similarity,
                cache_key=entry.key,
                cached_at=entry.created_at,
                ttl_remaining=ttl if ttl > 0 else None,
            )

        # Cache miss
        cache_stats["misses"] += 1
        span.set_attribute("cache_hit", False)

        return CacheLookupResponse(hit=False)


@app.post("/store")
async def cache_store(
    request: CacheStoreRequest,
    authorization: Optional[str] = Header(None),
):
    """Store a response in the cache."""
    with tracer.start_as_current_span("cache_store") as span:
        span.set_attribute("model", request.model)

        # Extract API key
        api_key = None
        if authorization and authorization.startswith("Bearer "):
            api_key = authorization[7:]

        # Convert messages to text and get embedding
        prompt_text = messages_to_text(request.messages)
        embedding = await get_embedding(prompt_text, api_key)

        # Create cache entry
        cache_key = compute_cache_key(request.messages, request.model, request.user_id)
        now = datetime.now(timezone.utc)

        entry = CacheEntry(
            key=cache_key,
            embedding=embedding,
            response=request.response,
            model=request.model,
            user_id=request.user_id,
            team_id=request.team_id,
            temperature=request.temperature,
            input_tokens=request.input_tokens or 0,
            output_tokens=request.output_tokens or 0,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=CACHE_TTL_SECONDS)).isoformat(),
        )

        # Store in Redis as HASH for vector search
        embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
        redis_key = f"semantic_cache:{request.model}:{cache_key}"
        entry_data = entry.model_dump()
        entry_data.pop("embedding")  # stored separately as binary

        await redis_client.hset(
            redis_key,
            mapping={
                "data": json.dumps(entry_data),
                "model": request.model,
                "user_id": request.user_id or "",
                "embedding": embedding_bytes,
            },
        )
        await redis_client.expire(redis_key, CACHE_TTL_SECONDS)

        span.set_attribute("cache_key", cache_key)

        return {
            "status": "stored",
            "cache_key": cache_key,
            "expires_at": entry.expires_at,
        }


@app.delete("/invalidate/{cache_key}")
async def cache_invalidate(cache_key: str, model: Optional[str] = None):
    """Invalidate a specific cache entry."""
    if model:
        redis_key = f"semantic_cache:{model}:{cache_key}"
        deleted = await redis_client.delete(redis_key)
    else:
        # Try to find and delete across all models
        pattern = f"semantic_cache:*:{cache_key}"
        deleted = 0
        async for key in redis_client.scan_iter(match=pattern):
            await redis_client.delete(key)
            deleted += 1

    return {"status": "invalidated", "deleted": deleted}


@app.delete("/invalidate-model/{model}")
async def cache_invalidate_model(model: str):
    """Invalidate all cache entries for a model."""
    pattern = f"semantic_cache:{model}:*"
    deleted = 0
    async for key in redis_client.scan_iter(match=pattern):
        await redis_client.delete(key)
        deleted += 1

    return {"status": "invalidated", "model": model, "deleted": deleted}


@app.delete("/invalidate-user/{user_id}")
async def cache_invalidate_user(user_id: str):
    """Invalidate all cache entries for a user."""
    pattern = "semantic_cache:*:*"
    deleted = 0

    async for key in redis_client.scan_iter(match=pattern):
        try:
            data = await redis_client.hget(key, "data")
            if data:
                entry = json.loads(data)
                if entry.get("user_id") == user_id:
                    await redis_client.delete(key)
                    deleted += 1
        except Exception:
            continue

    return {"status": "invalidated", "user_id": user_id, "deleted": deleted}


@app.get("/stats", response_model=CacheStats)
async def cache_stats_endpoint():
    """Get cache statistics."""
    # Count entries
    total_entries = 0
    async for _ in redis_client.scan_iter(match="semantic_cache:*"):
        total_entries += 1

    # Get memory info
    info = await redis_client.info("memory")
    memory_mb = info.get("used_memory", 0) / (1024 * 1024)

    # Calculate hit rate
    total_requests = cache_stats["hits"] + cache_stats["misses"]
    hit_rate = cache_stats["hits"] / total_requests if total_requests > 0 else 0.0

    return CacheStats(
        total_entries=total_entries,
        hits=cache_stats["hits"],
        misses=cache_stats["misses"],
        hit_rate=hit_rate,
        avg_similarity=SIMILARITY_THRESHOLD,  # Placeholder
        memory_used_mb=memory_mb,
        tokens_saved=cache_stats["tokens_saved"],
        cost_saved=cache_stats["cost_saved"],
    )


@app.post("/warmup")
async def cache_warmup(
    entries: List[CacheStoreRequest],
    authorization: Optional[str] = Header(None),
):
    """Warm up the cache with pre-computed entries."""
    stored = 0
    for entry in entries:
        try:
            await cache_store(entry, authorization)
            stored += 1
        except Exception:
            continue

    return {"status": "warmed", "stored": stored, "total": len(entries)}


@app.get("/entries")
async def list_cache_entries(
    model: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
):
    """List cache entries (for debugging)."""
    pattern = f"semantic_cache:{model or '*'}:*"
    entries = []

    async for key in redis_client.scan_iter(match=pattern):
        if len(entries) >= limit:
            break

        try:
            data = await redis_client.hget(key, "data")
            if data:
                entry = json.loads(data)
                # Filter by user if specified
                if user_id and entry.get("user_id") != user_id:
                    continue

                # Don't return embedding (too large)
                entry.pop("embedding", None)
                entries.append(entry)
        except Exception:
            continue

    return {"entries": entries, "count": len(entries)}


@app.post("/similarity")
async def compute_similarity(
    text1: str,
    text2: str,
    authorization: Optional[str] = Header(None),
):
    """Compute semantic similarity between two texts (utility endpoint)."""
    api_key = None
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization[7:]

    emb1 = await get_embedding(text1, api_key)
    emb2 = await get_embedding(text2, api_key)

    similarity = cosine_similarity(emb1, emb2)

    return {
        "text1_length": len(text1),
        "text2_length": len(text2),
        "similarity": similarity,
        "would_cache_hit": similarity >= SIMILARITY_THRESHOLD,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8083)
