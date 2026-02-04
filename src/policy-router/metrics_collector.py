"""
Prometheus metrics collector for model performance data.

Fetches real-time latency, error rates, and availability metrics
to inform routing decisions.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects model performance metrics from Prometheus.

    Used to make real-time routing decisions based on:
    - Current latency (p50, p95, p99)
    - Error rates
    - Request volume
    - Model availability
    """

    def __init__(self, prometheus_url: str, cache_ttl_seconds: int = 30):
        """
        Initialize metrics collector.

        Args:
            prometheus_url: Prometheus server URL
            cache_ttl_seconds: How long to cache metrics
        """
        self.prometheus_url = prometheus_url.rstrip('/')
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _query_prometheus(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Execute a PromQL query."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return data.get("data", {}).get("result", [])
            else:
                logger.warning(f"Prometheus query failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Prometheus query error: {e}")

        return None

    async def get_model_latency(self, model: str, percentile: int = 95) -> Optional[float]:
        """
        Get model latency at specified percentile.

        Args:
            model: Model identifier
            percentile: Latency percentile (50, 95, 99)

        Returns:
            Latency in milliseconds or None if unavailable
        """
        # Try LiteLLM metrics first
        query = f'histogram_quantile(0.{percentile}, sum(rate(litellm_request_duration_seconds_bucket{{model="{model}"}}[5m])) by (le)) * 1000'

        results = await self._query_prometheus(query)
        if results and len(results) > 0:
            try:
                return float(results[0].get("value", [None, None])[1])
            except (IndexError, ValueError, TypeError):
                pass

        # Fallback to generic HTTP metrics
        query = f'histogram_quantile(0.{percentile}, sum(rate(http_request_duration_seconds_bucket{{model="{model}"}}[5m])) by (le)) * 1000'

        results = await self._query_prometheus(query)
        if results and len(results) > 0:
            try:
                return float(results[0].get("value", [None, None])[1])
            except (IndexError, ValueError, TypeError):
                pass

        return None

    async def get_model_error_rate(self, model: str) -> Optional[float]:
        """
        Get current error rate for a model.

        Args:
            model: Model identifier

        Returns:
            Error rate (0.0 to 1.0) or None if unavailable
        """
        # Calculate error rate from LiteLLM metrics
        error_query = f'sum(rate(litellm_requests_total{{model="{model}",status=~"5.."}}[5m]))'
        total_query = f'sum(rate(litellm_requests_total{{model="{model}"}}[5m]))'

        errors = await self._query_prometheus(error_query)
        total = await self._query_prometheus(total_query)

        if errors and total:
            try:
                error_count = float(errors[0].get("value", [None, 0])[1]) if errors else 0
                total_count = float(total[0].get("value", [None, 0])[1]) if total else 0

                if total_count > 0:
                    return error_count / total_count
            except (IndexError, ValueError, TypeError):
                pass

        return None

    async def get_model_rpm(self, model: str) -> Optional[int]:
        """
        Get requests per minute for a model.

        Args:
            model: Model identifier

        Returns:
            Requests per minute or None if unavailable
        """
        query = f'sum(rate(litellm_requests_total{{model="{model}"}}[1m])) * 60'

        results = await self._query_prometheus(query)
        if results and len(results) > 0:
            try:
                return int(float(results[0].get("value", [None, 0])[1]))
            except (IndexError, ValueError, TypeError):
                pass

        return None

    async def is_model_available(self, model: str) -> bool:
        """
        Check if a model is available (responding to requests).

        Args:
            model: Model identifier

        Returns:
            True if model is available
        """
        # Check if there have been any requests in the last minute
        query = f'sum(increase(litellm_requests_total{{model="{model}"}}[5m])) > 0'

        results = await self._query_prometheus(query)

        # If we can't determine, assume available
        if results is None:
            return True

        # If no results, check error rate isn't 100%
        error_rate = await self.get_model_error_rate(model)
        if error_rate is not None and error_rate >= 1.0:
            return False

        return True

    async def get_all_model_metrics(self, models: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for all specified models.

        Args:
            models: List of model identifiers

        Returns:
            Dict mapping model ID to metrics dict
        """
        # Check cache
        now = datetime.utcnow()
        if self._cache_timestamp and (now - self._cache_timestamp) < self.cache_ttl:
            # Return cached values for requested models
            return {m: self._cache.get(m, {}) for m in models if m in self._cache}

        metrics = {}

        for model in models:
            model_metrics = {
                "latency_p50_ms": await self.get_model_latency(model, 50),
                "latency_p95_ms": await self.get_model_latency(model, 95),
                "latency_p99_ms": await self.get_model_latency(model, 99),
                "error_rate": await self.get_model_error_rate(model),
                "rpm": await self.get_model_rpm(model),
                "is_available": await self.is_model_available(model),
                "collected_at": now.isoformat()
            }
            metrics[model] = model_metrics

        # Update cache
        self._cache = metrics
        self._cache_timestamp = now

        return metrics

    async def get_provider_health(self, provider: str) -> Dict[str, Any]:
        """
        Get aggregate health metrics for a provider.

        Args:
            provider: Provider name (openai, anthropic, etc.)

        Returns:
            Dict with provider health metrics
        """
        # Query for aggregate provider metrics
        latency_query = f'avg(histogram_quantile(0.95, sum(rate(litellm_request_duration_seconds_bucket{{provider="{provider}"}}[5m])) by (le, model))) * 1000'
        error_query = f'sum(rate(litellm_requests_total{{provider="{provider}",status=~"5.."}}[5m])) / sum(rate(litellm_requests_total{{provider="{provider}"}}[5m]))'
        rpm_query = f'sum(rate(litellm_requests_total{{provider="{provider}"}}[1m])) * 60'

        latency_results = await self._query_prometheus(latency_query)
        error_results = await self._query_prometheus(error_query)
        rpm_results = await self._query_prometheus(rpm_query)

        return {
            "provider": provider,
            "avg_latency_p95_ms": float(latency_results[0].get("value", [None, None])[1]) if latency_results else None,
            "error_rate": float(error_results[0].get("value", [None, None])[1]) if error_results else None,
            "total_rpm": int(float(rpm_results[0].get("value", [None, 0])[1])) if rpm_results else None,
        }
