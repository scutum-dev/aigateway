"""Shared middleware for AI Control Plane services."""
import os
import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request


class ServiceAuthMiddleware(BaseHTTPMiddleware):
    """Verify X-Service-Key header for inter-service calls.

    Skips auth for health probe paths and OPTIONS preflight.
    If INTERNAL_SERVICE_KEY env var is not set, all requests pass through.
    """

    UNAUTHENTICATED_PATHS = {"/health", "/ready", "/live", "/healthz"}

    def __init__(self, app, unauthenticated_paths=None):
        super().__init__(app)
        if unauthenticated_paths:
            self.UNAUTHENTICATED_PATHS = set(unauthenticated_paths)

    async def dispatch(self, request: Request, call_next):
        service_key = os.getenv("INTERNAL_SERVICE_KEY", "")
        if not service_key:
            return await call_next(request)
        if request.url.path in self.UNAUTHENTICATED_PATHS:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        provided = request.headers.get("X-Service-Key", "")
        if not hmac.compare_digest(provided, service_key):
            return Response(
                content='{"detail": "Unauthorized: invalid or missing service key"}',
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent DoS attacks."""

    def __init__(self, app, max_size: int = None):
        super().__init__(app)
        self.max_size = max_size or int(os.getenv("MAX_REQUEST_SIZE_BYTES", 1_048_576))

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return Response(
                content='{"detail": "Request body too large"}',
                status_code=413,
                media_type="application/json",
            )
        return await call_next(request)
