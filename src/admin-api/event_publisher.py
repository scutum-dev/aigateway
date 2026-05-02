"""Event publisher — logs events and dispatches to matching subscriptions."""

import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SRE_AGENT_URL = os.getenv("SRE_AGENT_URL", "http://sre-agent:8092")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "")


async def publish_event(
    db_pool,
    event_type: str,
    payload: dict,
    source_service: str = "admin-api",
    http_client: Optional[httpx.AsyncClient] = None,
):
    """Record event in event_log and dispatch to matching active subscriptions.

    This is fire-and-forget — errors are logged but don't propagate.
    """
    if not db_pool:
        return

    try:
        async with db_pool.acquire() as conn:
            # 1. Insert into event_log
            await conn.execute(
                """
                INSERT INTO event_log (event_type, payload, source_service)
                VALUES ($1, $2::jsonb, $3)
                """,
                event_type,
                json.dumps(payload),
                source_service,
            )

            # 2. Find matching active subscriptions
            subscriptions = await conn.fetch(
                """
                SELECT * FROM event_subscriptions
                WHERE is_active = true AND $1 = ANY(event_types)
                """,
                event_type,
            )

            # 3. Dispatch to each subscription
            for sub in subscriptions:
                try:
                    channel = sub["channel"]
                    config = json.loads(sub["config"]) if isinstance(sub["config"], str) else (sub["config"] or {})

                    if channel == "webhook" and config.get("url") and http_client:
                        await http_client.post(
                            config["url"],
                            json={
                                "event_type": event_type,
                                "payload": payload,
                                "subscription": sub["name"],
                            },
                            timeout=10.0,
                        )
                        logger.info("Dispatched %s to webhook %s", event_type, sub["name"])
                    elif channel == "slack" and config.get("webhook_url") and http_client:
                        await http_client.post(
                            config["webhook_url"],
                            json={
                                "text": f"*[{event_type}]* {json.dumps(payload, default=str)[:500]}",
                            },
                            timeout=10.0,
                        )
                        logger.info("Dispatched %s to Slack %s", event_type, sub["name"])
                    elif channel == "sre_workflow" and http_client:
                        # Hand off to the sre-agent webhook. Agent opens an incident,
                        # runs diagnose+propose, and persists status='awaiting_approval'.
                        sre_url = config.get("url") or f"{SRE_AGENT_URL}/webhook"
                        headers = {}
                        if INTERNAL_SERVICE_KEY:
                            headers["X-Service-Key"] = INTERNAL_SERVICE_KEY
                        await http_client.post(
                            sre_url,
                            json={"event_type": event_type, "payload": payload},
                            headers=headers,
                            timeout=10.0,
                        )
                        logger.info("Dispatched %s to SRE agent (%s)", event_type, sub["name"])
                    else:
                        logger.debug("Channel %s not dispatched (no handler or missing config)", channel)
                except Exception as e:
                    logger.warning("Failed to dispatch event %s to %s: %s", event_type, sub["name"], e)
    except Exception as e:
        logger.warning("Failed to publish event %s: %s", event_type, e)
