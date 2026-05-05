"""Thin async client for Fly.io Machines API.

Just the calls the trial-provisioner needs:
- create app
- create volume (persistent disk for the trial's stateful data)
- run machine (single container, scale-to-zero enabled)
- delete app (full teardown — removes machine, volume, certificates)

All calls are httpx-based, async, and return Fly's response JSON. Errors
raise FlyAPIError with the response status + body for the caller to handle.

Reference: https://fly.io/docs/machines/api/ (api.machines.dev)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

FLY_API_BASE = "https://api.machines.dev/v1"


class FlyAPIError(RuntimeError):
    def __init__(self, status: int, body: str, *, op: str):
        super().__init__(f"Fly API {op} failed: HTTP {status} — {body[:300]}")
        self.status = status
        self.body = body
        self.op = op


class FlyClient:
    """Async wrapper over Fly Machines API.

    Construction is cheap (no network); reuse one client per process and
    pass it to the provisioner methods.
    """

    def __init__(
        self, api_token: Optional[str] = None, org_slug: Optional[str] = None, http: Optional[httpx.AsyncClient] = None
    ):
        self.api_token = api_token or os.getenv("FLY_API_TOKEN", "")
        self.org_slug = org_slug or os.getenv("FLY_ORG_SLUG", "personal")
        self.http = http  # injected for tests; lazily created if None

    async def _client(self) -> httpx.AsyncClient:
        if self.http is None:
            self.http = httpx.AsyncClient(
                base_url=FLY_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self.http

    async def aclose(self) -> None:
        if self.http is not None:
            await self.http.aclose()
            self.http = None

    # ---- apps -----------------------------------------------------------------

    async def create_app(self, app_name: str) -> Dict[str, Any]:
        """Create a new Fly app under the configured org."""
        client = await self._client()
        resp = await client.post(
            "/apps",
            json={"app_name": app_name, "org_slug": self.org_slug},
        )
        if resp.status_code not in (200, 201):
            raise FlyAPIError(resp.status_code, resp.text, op="create_app")
        return resp.json() if resp.text else {}

    async def delete_app(self, app_name: str) -> None:
        """Delete an app and everything it owns (machine, volumes, certs).

        Idempotent: 404 is treated as success so the lifecycle scheduler
        can safely re-run on partially-cleaned-up rows.
        """
        client = await self._client()
        resp = await client.delete(f"/apps/{app_name}")
        if resp.status_code in (200, 202, 204, 404):
            return
        raise FlyAPIError(resp.status_code, resp.text, op="delete_app")

    # ---- volumes --------------------------------------------------------------

    async def create_volume(self, app_name: str, name: str, region: str, size_gb: int) -> Dict[str, Any]:
        client = await self._client()
        resp = await client.post(
            f"/apps/{app_name}/volumes",
            json={"name": name, "region": region, "size_gb": size_gb},
        )
        if resp.status_code not in (200, 201):
            raise FlyAPIError(resp.status_code, resp.text, op="create_volume")
        return resp.json()

    # ---- machines -------------------------------------------------------------

    async def run_machine(
        self,
        app_name: str,
        *,
        image: str,
        region: str,
        env: Dict[str, str],
        ports: List[Dict[str, Any]],
        cpu_kind: str = "shared",
        cpus: int = 1,
        memory_mb: int = 2048,
        volume_id: Optional[str] = None,
        volume_mount_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Boot a machine with auto-stop-on-idle + auto-start-on-traffic.

        The combination of `auto_stop_machines=stop` + `auto_start_machines=true`
        + `min_machines_running=0` is the scale-to-zero primitive — no cost
        when idle, ~300 ms wake on incoming traffic.
        """
        services = [
            {
                "ports": ports,
                "protocol": "tcp",
                "internal_port": 80,
                "auto_stop_machines": "stop",
                "auto_start_machines": True,
                "min_machines_running": 0,
            }
        ]
        config: Dict[str, Any] = {
            "image": image,
            "env": env,
            "services": services,
            "guest": {"cpu_kind": cpu_kind, "cpus": cpus, "memory_mb": memory_mb},
        }
        if volume_id and volume_mount_path:
            config["mounts"] = [{"volume": volume_id, "path": volume_mount_path}]

        client = await self._client()
        resp = await client.post(
            f"/apps/{app_name}/machines",
            json={"region": region, "config": config},
        )
        if resp.status_code not in (200, 201):
            raise FlyAPIError(resp.status_code, resp.text, op="run_machine")
        return resp.json()

    # ---- certificates (custom hostname) ---------------------------------------

    async def create_certificate(self, app_name: str, hostname: str) -> Dict[str, Any]:
        client = await self._client()
        resp = await client.post(
            f"/apps/{app_name}/certificates",
            json={"hostname": hostname},
        )
        if resp.status_code not in (200, 201):
            raise FlyAPIError(resp.status_code, resp.text, op="create_certificate")
        return resp.json()
