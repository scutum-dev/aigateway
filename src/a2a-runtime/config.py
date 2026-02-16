import os

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "a2a-agents")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
AGENT_GATEWAY_URL = os.getenv("AGENT_GATEWAY_URL", "http://localhost:9000")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "")
