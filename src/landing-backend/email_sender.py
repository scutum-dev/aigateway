"""Internal SMTP sender for the founder-facing demo-request alert.

Mirrors the budget-webhook _send_email pattern (aiosmtplib + MIMEText). No-op
when SMTP is unconfigured — the request is still persisted to DB and Cal.com
sends the user-facing confirmation.

Module is named `email_sender` rather than `email` to avoid shadowing the
stdlib `email` package needed for MIME types.
"""

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
DEMO_FROM = os.getenv("DEMO_FROM", "hello@scutum.dev")
DEMO_INBOX = os.getenv("DEMO_INBOX", "")
DEMO_REPLY_TO = os.getenv("DEMO_REPLY_TO", DEMO_FROM)


def is_configured() -> bool:
    return bool(SMTP_HOST and DEMO_INBOX)


async def send_internal_alert(request: Dict[str, Any]) -> bool:
    """Send a plain notification to DEMO_INBOX. Returns True if dispatched, False if skipped."""
    if not is_configured():
        logger.info("SMTP unconfigured; skipping internal demo alert (request_id=%s)", request.get("id"))
        return False

    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        import aiosmtplib
    except ImportError:
        logger.warning("aiosmtplib not installed, skipping internal alert")
        return False

    subject = f"New demo request: {request.get('company') or request.get('name')}"

    body_lines = [
        f"Name:       {request.get('name', '')}",
        f"Email:      {request.get('work_email', '')}",
        f"Company:    {request.get('company', '')}",
        f"Role:       {request.get('role', '')}",
        f"Team size:  {request.get('team_size', '')}",
        "",
        "Use case:",
        request.get("use_case", "") or "(none)",
        "",
        f"Preferred window: {request.get('preferred_window', '(any)')}",
        f"Cal.com booking:  {request.get('calcom_meeting_url') or '(not booked yet)'}",
        f"Source IP:        {request.get('source_ip', '')}",
        f"Request id:       {request.get('id', '')}",
    ]
    body_text = "\n".join(body_lines)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = DEMO_FROM
    msg["To"] = DEMO_INBOX
    msg["Reply-To"] = DEMO_REPLY_TO
    msg.attach(MIMEText(body_text, "plain"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER or None,
            password=SMTP_PASSWORD or None,
            start_tls=True,
        )
        logger.info("Internal demo alert sent for %s", request.get("id"))
        return True
    except Exception as e:
        logger.warning("SMTP send failed for demo request %s: %s", request.get("id"), e)
        return False
