"""Thin async client for Cloudflare DNS API.

Just the calls trial-provisioner needs: create / delete DNS records under
the configured zone. Used to point `trial-{id}.trial.scutum.dev` CNAME at
the Fly app's `<app>.fly.dev` hostname so the trial URL is brandable.

Reference: https://developers.cloudflare.com/api/operations/dns-records-for-a-zone-list-dns-records
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareAPIError(RuntimeError):
    def __init__(self, status: int, body: str, *, op: str):
        super().__init__(f"Cloudflare API {op} failed: HTTP {status} — {body[:300]}")
        self.status = status
        self.body = body
        self.op = op


class CloudflareClient:
    def __init__(
        self, api_token: Optional[str] = None, zone_id: Optional[str] = None, http: Optional[httpx.AsyncClient] = None
    ):
        self.api_token = api_token or os.getenv("CLOUDFLARE_API_TOKEN", "")
        self.zone_id = zone_id or os.getenv("CLOUDFLARE_ZONE_ID", "")
        self.http = http

    async def _client(self) -> httpx.AsyncClient:
        if self.http is None:
            self.http = httpx.AsyncClient(
                base_url=CLOUDFLARE_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                timeout=20.0,
            )
        return self.http

    async def aclose(self) -> None:
        if self.http is not None:
            await self.http.aclose()
            self.http = None

    async def create_cname(self, name: str, target: str, *, proxied: bool = False) -> Dict[str, Any]:
        """Create a CNAME pointing `name` → `target` in the configured zone.

        `proxied=False` for trial subdomains because Fly already handles TLS
        on their wildcard *.fly.dev cert + the custom-hostname Let's Encrypt
        cert; double-proxying through Cloudflare's edge breaks the cert chain
        unless we also set up Cloudflare → Fly's Origin SSL correctly.
        """
        client = await self._client()
        resp = await client.post(
            f"/zones/{self.zone_id}/dns_records",
            json={"type": "CNAME", "name": name, "content": target, "proxied": proxied, "ttl": 1},
        )
        if resp.status_code not in (200, 201):
            raise CloudflareAPIError(resp.status_code, resp.text, op="create_cname")
        body = resp.json()
        if not body.get("success"):
            raise CloudflareAPIError(resp.status_code, resp.text, op="create_cname")
        return body["result"]

    async def delete_record(self, record_id: str) -> None:
        """Delete a DNS record by id. Idempotent (404 is treated as success)."""
        client = await self._client()
        resp = await client.delete(f"/zones/{self.zone_id}/dns_records/{record_id}")
        if resp.status_code in (200, 204, 404):
            return
        raise CloudflareAPIError(resp.status_code, resp.text, op="delete_record")

    async def find_record_id(self, name: str) -> Optional[str]:
        """Look up a DNS record id by exact name (used for cleanup)."""
        client = await self._client()
        resp = await client.get(
            f"/zones/{self.zone_id}/dns_records",
            params={"name": name},
        )
        if resp.status_code != 200:
            raise CloudflareAPIError(resp.status_code, resp.text, op="find_record_id")
        results = resp.json().get("result", [])
        return results[0]["id"] if results else None
