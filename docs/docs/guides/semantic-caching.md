# Semantic Caching Guide

Reduce latency and cost by caching LLM responses using embedding similarity rather than exact string matching.

## Overview

Traditional caching only works when requests are identical. Semantic caching uses vector embeddings to match requests that are similar in meaning -- so "What is the capital of France?" and "Tell me France's capital city" return the same cached response.

### How It Works

```
User Request ──▶ LiteLLM Proxy (:4000)
                       │
                       ├── Generate Embedding (text-embedding-3-small)
                       ├── Search Redis Cache (cosine similarity)
                       │
                 ┌─────┴─────────┐
                 │                │
           Similarity ≥ 0.92   Similarity < 0.92
           (Cache Hit)          (Cache Miss)
                 │                │
                 ▼                ▼
           Return Cached    Call LLM Provider
           Response         Store in Redis Cache
```

Semantic caching is handled transparently by LiteLLM's built-in `redis-semantic` cache. Every request through `/v1/chat/completions` is automatically checked against the cache -- no client-side changes needed.

1. The incoming prompt is converted to a vector embedding via `text-embedding-3-small`.
2. The embedding is compared (cosine similarity) against cached embeddings in Redis.
3. If any cached entry exceeds the similarity threshold (default 0.92), the cached response is returned immediately.
4. On a miss, the LLM call proceeds normally and the response is stored in Redis for future hits.

## Configuration

Semantic caching is enabled by default in `config/litellm/config.yaml`:

```yaml
cache: true
cache_params:
  type: "redis-semantic"
  host: "redis"
  port: 6379
  ttl: 3600
  namespace: "litellm"
  similarity_threshold: 0.92
  redis_semantic_cache_embedding_model: "text-embedding-3-small"
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `type` | `redis-semantic` | Cache type. Use `redis` for exact-match only. |
| `similarity_threshold` | `0.92` | Minimum cosine similarity for a cache hit (0.0 to 1.0) |
| `redis_semantic_cache_embedding_model` | `text-embedding-3-small` | Model used to generate embeddings |
| `ttl` | `3600` | Time-to-live for cached entries in seconds |
| `host` | `redis` | Redis hostname |
| `port` | `6379` | Redis port |

### Tuning the Similarity Threshold

The threshold controls the trade-off between cache hit rate and response accuracy:

| Threshold | Behavior |
|-----------|----------|
| `0.95+` | Very strict -- only nearly identical prompts match. Low hit rate, high accuracy. |
| `0.90-0.95` | Balanced -- catches paraphrased questions while avoiding false matches. **Recommended.** |
| `0.85-0.90` | Aggressive -- higher hit rate but may return responses for semantically different questions. |
| `< 0.85` | Not recommended -- too many false positives. |

### Toggling via Admin UI

The Admin UI Settings page exposes `enable_caching` and `cache_ttl_seconds`. Changes are synced to LiteLLM at runtime without a restart.

## Admin API Management Endpoints

The Admin API (port 8086) provides endpoints for cache visibility and management, used by the Admin UI:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/cache/stats` | Cache statistics (entries, hit rate, size) |
| `GET` | `/api/v1/cache/settings` | Current cache settings |
| `PUT` | `/api/v1/cache/settings` | Update settings (syncs to LiteLLM) |
| `GET` | `/api/v1/cache/entries` | List cached entries (paginated) |
| `DELETE` | `/api/v1/cache/entries/{id}` | Delete a specific entry |
| `POST` | `/api/v1/cache/clear` | Clear all cache entries |

### Example: View Cache Stats

```bash
TOKEN="your-jwt-token"

curl http://localhost:8086/api/v1/cache/stats \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "total_entries": 1523,
  "total_hits": 8934,
  "hit_rate": 68.0,
  "cache_size_mb": 4.31,
  "avg_token_savings": 142.5
}
```

### Example: Update Settings

```bash
curl -X PUT http://localhost:8086/api/v1/cache/settings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "enabled": true,
    "similarity_threshold": 0.90,
    "ttl_seconds": 7200,
    "max_entries": 20000
  }'
```

## Testing Semantic Caching

Send the same question phrased differently and observe the cached response:

```bash
# First request -- cache miss, calls the LLM
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{"model": "gpt-5-mini", "messages": [{"role": "user", "content": "What is the capital of France?"}]}'

# Second request -- paraphrased, should be a cache hit
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -d '{"model": "gpt-5-mini", "messages": [{"role": "user", "content": "Tell me the capital city of France"}]}'
```

The second request should return faster with the cached response. Check the response headers or Grafana metrics to confirm cache hits.

## Disabling Semantic Caching

To switch back to exact-match caching, change the config:

```yaml
cache_params:
  type: "redis"      # exact-match only
  host: "redis"
  port: 6379
  ttl: 3600
```

Or disable caching entirely via the Admin UI Settings page (`enable_caching: false`).

## Production Considerations

- **Embedding costs**: Each cache miss requires one embedding API call (`text-embedding-3-small` is ~$0.02 per 1M tokens). This overhead is negligible compared to the LLM call cost saved on cache hits.
- **Redis memory**: Cached embeddings consume Redis memory. Monitor Redis usage and set `max_entries` to cap growth.
- **TTL strategy**: Set TTL based on how frequently your data changes. Factual queries benefit from longer TTLs (hours). Time-sensitive data should use shorter TTLs (minutes).
- **Model isolation**: Cache keys are namespaced by model. A cached GPT-5 response will not match a Claude query, even if the prompts are identical.

## Related Guides

- [Observability Guide](./observability.md) -- monitor cache hit rates in Grafana
- [Cost Management Guide](./cost-management.md) -- how caching reduces spend
- [LiteLLM Deep Dive](./litellm-integration.md) -- full LiteLLM configuration reference
