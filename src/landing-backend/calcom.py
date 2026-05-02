"""Thin Cal.com REST client.

Cal.com v1 API: https://cal.com/docs/api-reference. We only need:
- GET /v1/availability   (with eventTypeId, dateFrom, dateTo)
- POST /v1/bookings      (create a booking; Cal.com auto-emails the requester)

If CALCOM_API_KEY or CALCOM_EVENT_TYPE_ID is unset, the client returns degraded
results so the form still works (DB persistence, manual follow-up).
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

CALCOM_BASE_URL = os.getenv("CALCOM_BASE_URL", "https://api.cal.com/v1")
CALCOM_API_KEY = os.getenv("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID = os.getenv("CALCOM_EVENT_TYPE_ID", "")


def is_configured() -> bool:
    return bool(CALCOM_API_KEY and CALCOM_EVENT_TYPE_ID)


async def get_availability(
    http_client: httpx.AsyncClient,
    date_from: str,
    date_to: str,
) -> Dict[str, Any]:
    """Return Cal.com availability for the configured event type, or {} if unconfigured."""
    if not is_configured():
        return {"configured": False, "slots": []}

    params = {
        "apiKey": CALCOM_API_KEY,
        "eventTypeId": CALCOM_EVENT_TYPE_ID,
        "dateFrom": date_from,
        "dateTo": date_to,
    }
    try:
        resp = await http_client.get(f"{CALCOM_BASE_URL}/availability", params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return {"configured": True, "slots": data.get("slots", []), "raw": data}
    except Exception as e:
        logger.warning("Cal.com availability lookup failed: %s", e)
        return {"configured": True, "slots": [], "error": str(e)}


async def create_booking(
    http_client: httpx.AsyncClient,
    *,
    name: str,
    email: str,
    start_iso: str,
    end_iso: str,
    notes: Optional[str] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """Create a Cal.com booking. Returns {ok, booking_id, meeting_url, error}."""
    if not is_configured():
        return {"ok": False, "configured": False, "error": "Cal.com not configured"}

    payload = {
        "eventTypeId": int(CALCOM_EVENT_TYPE_ID),
        "start": start_iso,
        "end": end_iso,
        "responses": {
            "name": name,
            "email": email,
            "notes": notes or "",
        },
        "timeZone": timezone,
        "language": "en",
        "metadata": {"source": "landing-page"},
    }
    try:
        resp = await http_client.post(
            f"{CALCOM_BASE_URL}/bookings",
            params={"apiKey": CALCOM_API_KEY},
            json=payload,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        booking = data.get("booking") or data
        meeting_url = booking.get("meetingUrl") or booking.get("location")
        return {
            "ok": True,
            "configured": True,
            "booking_id": str(booking.get("id") or booking.get("uid", "")),
            "meeting_url": meeting_url,
            "raw": data,
        }
    except httpx.HTTPStatusError as e:
        body = _safe_text(e.response)
        logger.warning("Cal.com booking failed (%s): %s", e.response.status_code, body)
        return {
            "ok": False,
            "configured": True,
            "error": f"HTTP {e.response.status_code}",
            "body": body,
        }
    except Exception as e:
        logger.warning("Cal.com booking error: %s", e)
        return {"ok": False, "configured": True, "error": str(e)}


def _safe_text(resp: httpx.Response) -> str:
    try:
        return resp.text[:1000]
    except Exception:
        return ""
