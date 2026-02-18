"""Event System router -- subscriptions management and event log querying."""

import json
import logging
from typing import Dict, List, Optional

import deps
from auth import UserInfo, get_current_user, require_admin
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class EventSubscriptionCreate(BaseModel):
    name: str
    event_types: List[str]
    channel: str
    config: Dict
    filters: Optional[Dict] = None


class EventSubscriptionUpdate(BaseModel):
    name: Optional[str] = None
    event_types: Optional[List[str]] = None
    channel: Optional[str] = None
    config: Optional[Dict] = None
    filters: Optional[Dict] = None
    is_active: Optional[bool] = None


class TestEventRequest(BaseModel):
    event_type: str
    payload: Dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_subscription(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "event_types": list(row["event_types"]) if row["event_types"] else [],
        "channel": row["channel"],
        "config": json.loads(row["config"]) if isinstance(row["config"], str) else (row["config"] or {}),
        "filters": json.loads(row["filters"]) if isinstance(row["filters"], str) else row["filters"],
        "is_active": row["is_active"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
    }


def _row_to_event(row) -> dict:
    return {
        "id": str(row["id"]),
        "event_type": row["event_type"],
        "payload": json.loads(row["payload"]) if isinstance(row["payload"], str) else (row["payload"] or {}),
        "source_service": row["source_service"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
    }


# ---------------------------------------------------------------------------
# Subscription endpoints
# ---------------------------------------------------------------------------


@router.get("/events/subscriptions")
async def list_subscriptions(user: UserInfo = Depends(get_current_user)):
    """List all event subscriptions."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM event_subscriptions ORDER BY created_at DESC"
        )
        return [_row_to_subscription(row) for row in rows]


@router.post("/events/subscriptions")
async def create_subscription(
    data: EventSubscriptionCreate,
    user: UserInfo = Depends(require_admin),
):
    """Create a new event subscription."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO event_subscriptions (name, event_types, channel, config, filters)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
            RETURNING *
            """,
            data.name,
            data.event_types,
            data.channel,
            json.dumps(data.config),
            json.dumps(data.filters) if data.filters else None,
        )
        logger.info("Event subscription created: %s by %s", data.name, user.user_id)
        return _row_to_subscription(row)


@router.get("/events/subscriptions/{subscription_id}")
async def get_subscription(
    subscription_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """Get a specific event subscription."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM event_subscriptions WHERE id = $1::uuid",
            subscription_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return _row_to_subscription(row)


@router.put("/events/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    data: EventSubscriptionUpdate,
    user: UserInfo = Depends(require_admin),
):
    """Update an event subscription."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM event_subscriptions WHERE id = $1::uuid",
            subscription_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Subscription not found")

        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.event_types is not None:
            updates["event_types"] = data.event_types
        if data.channel is not None:
            updates["channel"] = data.channel
        if data.config is not None:
            updates["config"] = json.dumps(data.config)
        if data.filters is not None:
            updates["filters"] = json.dumps(data.filters)
        if data.is_active is not None:
            updates["is_active"] = data.is_active

        if not updates:
            return _row_to_subscription(existing)

        set_clauses = []
        values = []
        for i, (key, value) in enumerate(updates.items(), start=1):
            if key in ("config", "filters"):
                set_clauses.append(f"{key} = ${i}::jsonb")
            else:
                set_clauses.append(f"{key} = ${i}")
            values.append(value)

        values.append(subscription_id)
        query = f"""
            UPDATE event_subscriptions
            SET {', '.join(set_clauses)}
            WHERE id = ${len(values)}::uuid
            RETURNING *
        """
        row = await conn.fetchrow(query, *values)
        logger.info("Event subscription updated: %s by %s", subscription_id, user.user_id)
        return _row_to_subscription(row)


@router.delete("/events/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    user: UserInfo = Depends(require_admin),
):
    """Delete an event subscription."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM event_subscriptions WHERE id = $1::uuid",
            subscription_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Subscription not found")
        logger.info("Event subscription deleted: %s by %s", subscription_id, user.user_id)
        return {"status": "ok"}


# ---------------------------------------------------------------------------
# Event log endpoints
# ---------------------------------------------------------------------------


@router.get("/events/log")
async def list_events(
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserInfo = Depends(get_current_user),
):
    """Query event log with optional filtering."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        if event_type:
            rows = await conn.fetch(
                """
                SELECT * FROM event_log
                WHERE event_type = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                event_type,
                limit,
                offset,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM event_log
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
        return [_row_to_event(row) for row in rows]


@router.post("/events/test")
async def send_test_event(
    data: TestEventRequest,
    user: UserInfo = Depends(require_admin),
):
    """Send a test event (inserts into event_log)."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO event_log (event_type, payload, source_service)
            VALUES ($1, $2::jsonb, $3)
            RETURNING *
            """,
            data.event_type,
            json.dumps(data.payload),
            "admin-api-test",
        )
        logger.info("Test event sent: %s by %s", data.event_type, user.user_id)
        return _row_to_event(row)
