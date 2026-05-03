"""Asyncpg storage for demo_requests."""

import json
import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def recent_request_by_email(db_pool, work_email: str, window_seconds: int) -> Optional[str]:
    """Return the id of the most recent demo_request from this email within the
    window, or None. Used by the dedup gate so a single requester refreshing
    the form (or a bot fanning out from many IPs but a single email) doesn't
    create duplicate rows. Per-IP rate limiting is the IP-axis defence; this is
    the email-axis dedup.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text AS id
            FROM demo_requests
            WHERE LOWER(work_email) = LOWER($1)
              AND created_at > NOW() - ($2 || ' seconds')::interval
            ORDER BY created_at DESC
            LIMIT 1
            """,
            work_email,
            str(window_seconds),
        )
        return row["id"] if row else None


async def insert_demo_request(
    db_pool,
    *,
    name: str,
    work_email: str,
    company: Optional[str],
    role: Optional[str],
    team_size: Optional[str],
    use_case: Optional[str],
    preferred_window: Optional[Dict[str, Any]],
    source_ip: Optional[str],
    user_agent: Optional[str],
) -> str:
    """Insert a new demo_requests row. Returns the new id."""
    new_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO demo_requests
                (id, name, work_email, company, role, team_size, use_case,
                 preferred_window, source_ip, user_agent, status)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, 'new')
            """,
            new_id,
            name,
            work_email,
            company,
            role,
            team_size,
            use_case,
            json.dumps(preferred_window) if preferred_window else None,
            source_ip,
            user_agent,
        )
    return new_id


async def attach_calcom_booking(
    db_pool,
    request_id: str,
    booking_id: str,
    meeting_url: Optional[str],
) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE demo_requests
            SET calcom_booking_id = $1,
                calcom_meeting_url = $2,
                status = 'scheduled'
            WHERE id = $3::uuid
            """,
            booking_id,
            meeting_url,
            request_id,
        )
