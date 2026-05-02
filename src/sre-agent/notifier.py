"""Fan out incident summaries to active event subscriptions.

Reuses the existing event_subscriptions table (channel ∈ webhook/slack/
pagerduty/email). Reads active rows whose event_types include 'sre.incident'
and dispatches a JSON payload. Operators add subscriptions through the
existing Events admin UI — no new config surface.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


async def notify_all(
    db_pool,
    http_client: httpx.AsyncClient,
    severity: str,
    summary: str,
    incident_id: str,
    extra: Optional[Dict[str, Any]] = None,
) -> int:
    """Dispatch to every active subscription for 'sre.incident'. Returns count delivered."""
    if not db_pool:
        return 0

    payload = {
        "incident_id": incident_id,
        "severity": severity,
        "summary": summary,
        "ui_url": _incident_url(incident_id),
        "extra": extra or {},
    }

    delivered = 0
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT name, channel, config
                FROM event_subscriptions
                WHERE is_active = true AND 'sre.incident' = ANY(event_types)
                """,
            )
            for row in rows:
                try:
                    config = json.loads(row["config"]) if isinstance(row["config"], str) else (row["config"] or {})
                    if await _dispatch(http_client, row["channel"], config, payload):
                        delivered += 1
                except Exception as e:
                    logger.warning("Notify dispatch failed for %s: %s", row["name"], e)
    except Exception as e:
        logger.warning("Notify lookup failed: %s", e)
    return delivered


async def _dispatch(
    http_client: httpx.AsyncClient,
    channel: str,
    config: Dict[str, Any],
    payload: Dict[str, Any],
) -> bool:
    if channel == "webhook" and config.get("url"):
        await http_client.post(config["url"], json=payload, timeout=10.0)
        return True
    if channel == "slack" and config.get("webhook_url"):
        await http_client.post(
            config["webhook_url"],
            json={"text": _slack_text(payload)},
            timeout=10.0,
        )
        return True
    if channel == "pagerduty" and config.get("routing_key"):
        await http_client.post(
            "https://events.pagerduty.com/v2/enqueue",
            json={
                "routing_key": config["routing_key"],
                "event_action": "trigger",
                "payload": {
                    "summary": payload["summary"],
                    "severity": payload["severity"],
                    "source": "sre-agent",
                    "custom_details": payload,
                },
            },
            timeout=10.0,
        )
        return True
    return False


def _slack_text(payload: Dict[str, Any]) -> str:
    sev = payload["severity"].upper()
    return f"*[SRE {sev}]* {payload['summary']}\nIncident: {payload['ui_url']}"


def _incident_url(incident_id: str) -> str:
    base = os.getenv("ADMIN_UI_URL", "http://localhost:5173")
    return f"{base.rstrip('/')}/sre?incident={incident_id}"
