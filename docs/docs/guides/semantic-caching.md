# Semantic Caching Guide

Reduce latency and cost by caching LLM responses using embedding similarity rather than exact string matching.

## Overview

Traditional caching only works when requests are identical. Semantic caching uses vector embeddings to match requests that are similar in meaning -- so "What is the capital of France?" and "Tell me France's capital city" return the same cached response.

### How It Works

```
User Request ──▶ Generate Embedding ──▶ Search Redis Cache
                                              │
                                    ┌─────────┴─────────┐
                                    │                    │
                              Similarity ≥ 0.92    Similarity < 0.92
                              (Cache Hit)          (Cache Miss)
                                    │                    │
                                    ▼                    ▼
                              Return Cached        Call LLM Provider
                              Response             Store in Cache
```

1. The incoming prompt is converted to a vector embedding via the configured embedding model.
2. The embedding is compared (cosine similarity) against all cached embeddings for the same model.
3. If any cached entry exceeds the similarity threshold (default 0.92), the cached response is returned.
4. On a miss, the actual LLM call is made and the response is stored in Redis for future hits.

## Enabling Semantic Caching

The semantic cache runs as a separate service in the `experimental` profile:

```bash
docker compose --env-file config/.env --profile experimental up -d
```

This starts the semantic cache on **http://localhost:8083** alongside the policy router.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection for cache storage |
| `LITELLM_URL` | `http://localhost:4000` | LiteLLM endpoint for generating embeddings |
| `LITELLM_API_KEY` | `""` | API key for embedding calls |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Model used to generate embeddings |
| `SIMILARITY_THRESHOLD` | `0.92` | Minimum cosine similarity for a cache hit (0.0 to 1.0) |
| `CACHE_TTL_SECONDS` | `3600` | Time-to-live for cached entries (seconds) |
| `MAX_CACHE_ENTRIES` | `10000` | Maximum number of cache entries |

### Tuning the Similarity Threshold

The threshold controls the trade-off between cache hit rate and response accuracy:

| Threshold | Behavior |
|-----------|----------|
| `0.95+` | Very strict -- only nearly identical prompts match. Low hit rate, high accuracy. |
| `0.90-0.95` | Balanced -- catches paraphrased questions while avoiding false matches. **Recommended.** |
| `0.85-0.90` | Aggressive -- higher hit rate but may return responses for semantically different questions. |
| `< 0.85` | Not recommended -- too many false positives. |

The Docker Compose default is `0.90`. Adjust via the `SIMILARITY_THRESHOLD` environment variable.

## API Endpoints

### Cache Lookup

```bash
curl -X POST http://localhost:8083/lookup \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the capital of France?"}],
    "model": "gpt-5",
    "user_id": "user-123"
  }'
```

Response (cache hit):
```json
{
  "hit": true,
  "response": {"choices": [{"message": {"content": "Paris is the capital of France."}}]},
  "similarity": 0.97,
  "cache_key": "abc123...",
  "ttl_remaining": 2847
}
```

Response (cache miss):
```json
{
  "hit": false,
  "response": null,
  "similarity": 0.0
}
```

### Store Response

After a cache miss and successful LLM call, store the result:

```bash
curl -X POST http://localhost:8083/store \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the capital of France?"}],
    "model": "gpt-5",
    "response": {"choices": [{"message": {"content": "Paris is the capital of France."}}]},
    "user_id": "user-123",
    "tokens_used": 42
  }'
```

### Cache Statistics

```bash
curl http://localhost:8083/stats
```

```json
{
  "total_entries": 1523,
  "total_hits": 8934,
  "total_misses": 4211,
  "hit_rate": 0.68,
  "memory_used_bytes": 4521984,
  "tokens_saved": 189420,
  "cost_saved": 3.79
}
```

### Cache Invalidation

```bash
# Invalidate a specific entry
curl -X DELETE http://localhost:8083/invalidate/abc123

# Invalidate all entries for a model
curl -X DELETE http://localhost:8083/invalidate-model/gpt-5

# Invalidate all entries for a user
curl -X DELETE http://localhost:8083/invalidate-user/user-123
```

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check with Redis status and config |
| `POST` | `/warmup` | Bulk-store entries to warm the cache |
| `GET` | `/entries` | List cache entries (debug, max 100) |
| `POST` | `/similarity` | Compute similarity between two arbitrary texts |

## Cache Isolation

### Per-Model Isolation

Cache keys are namespaced by model (`semantic_cache:{model}:{hash}`). A cached GPT-5 response will never match a Claude query, even if the prompts are identical. This ensures model-specific responses are returned correctly.

### Per-User Isolation

When `user_id` is provided on lookup, entries belonging to a different user are skipped. This prevents users from seeing each other's cached responses -- important for multi-tenant deployments.

## Redis Storage

Cache entries are stored in Redis with automatic TTL expiry:

- **Key pattern:** `semantic_cache:{model}:{sha256_hash}`
- **Value:** JSON blob containing the embedding vector, original response, metadata, and expiration timestamp
- **TTL:** Configurable via `CACHE_TTL_SECONDS` (default 1 hour)

The service requires the same Redis instance used by the core platform. No additional Redis setup is needed.

## OpenTelemetry Integration

The semantic cache emits detailed OTEL traces for every operation:

| Span | Attributes |
|------|------------|
| `cache_lookup` | model, threshold, hit/miss, similarity score |
| `cache_store` | model, cache_key, ttl |
| `get_embedding` | model, embedding dimensions |
| `find_similar_cached` | model, entries scanned, best similarity |

When the observability profile is active, these traces appear in Jaeger under the `semantic-cache` service.

## Production Considerations

- **Scaling:** The current implementation scans all Redis keys per model for similarity. This works well for caches under a few thousand entries. For larger deployments, consider switching to Redis Vector Search (RediSearch) or pgvector.
- **Stats persistence:** Hit/miss counters are stored in memory and reset on service restart. For persistent stats, the OTEL metrics exported to Prometheus provide durable tracking.
- **Embedding costs:** Each cache lookup requires one embedding API call. Use a small, fast embedding model (like `text-embedding-3-small`) to minimize this overhead.
- **TTL strategy:** Set TTL based on how frequently your data changes. For factual queries, longer TTLs (hours) work well. For time-sensitive data, use shorter TTLs (minutes).

## Related Guides

- [Observability Guide](./observability.md) -- monitor cache hit rates in Grafana
- [Cost Management Guide](./cost-management.md) -- how caching reduces spend
- [API Integration Guide](./api-integration.md) -- code examples for the LLM API
