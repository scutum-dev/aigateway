"""Global mutable state for A2A runtime."""

from typing import Optional

import redis.asyncio as redis
from temporalio.client import Client as TemporalClient
from temporalio.worker import Worker

redis_client: Optional[redis.Redis] = None
temporal_client: Optional[TemporalClient] = None
worker: Optional[Worker] = None
