"""Auth-bearing httpx wrapper for admin-api calls.

Mints a JWT at startup against admin-api /auth/login using the master key,
sends both Bearer JWT and X-Service-Key headers (the latter satisfies
ServiceAuthMiddleware on services that have it). Refreshes on 401.
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class AdminClient:
    def __init__(self, base_url: str, api_key: str, service_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.service_key = service_key
        self._token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _login(self) -> None:
        if not self.api_key:
            raise RuntimeError("SRE_AGENT_API_KEY (or LITELLM_MASTER_KEY) is required")
        resp = await self._client.post(
            f"{self.base_url}/auth/login",
            json={"api_key": self.api_key},
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        logger.info("SRE agent authenticated to admin-api")

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        if self.service_key:
            h["X-Service-Key"] = self.service_key
        return h

    async def call(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute method+path on admin-api with auto-refresh on 401."""
        if not self._token:
            await self._login()

        url = f"{self.base_url}{path}"
        for attempt in (1, 2):
            resp = await self._client.request(
                method,
                url,
                json=body,
                headers=self._headers(),
            )
            if resp.status_code == 401 and attempt == 1:
                logger.info("Admin-API returned 401; refreshing JWT and retrying")
                self._token = None
                await self._login()
                continue
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                return {
                    "ok": False,
                    "status": resp.status_code,
                    "error": str(e),
                    "body": _safe_json(resp),
                }
            return {"ok": True, "status": resp.status_code, "body": _safe_json(resp)}

        return {"ok": False, "status": 401, "error": "Unauthenticated after refresh"}


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def build_admin_client() -> AdminClient:
    return AdminClient(
        base_url=os.getenv("ADMIN_API_URL", "http://admin-api:8086"),
        api_key=os.getenv("SRE_AGENT_API_KEY") or os.getenv("LITELLM_MASTER_KEY", ""),
        service_key=os.getenv("INTERNAL_SERVICE_KEY", ""),
    )
