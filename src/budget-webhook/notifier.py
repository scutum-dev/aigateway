"""
Multi-channel alert notification dispatcher.

Sends budget alerts to configured channels:
- Slack (Block Kit formatting)
- Email (HTML via SMTP)
- PagerDuty (Events API v2)
- Generic webhook (existing behavior)
"""

import os
import asyncio
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# Channel configuration from environment
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
PAGERDUTY_ROUTING_KEY = os.getenv("PAGERDUTY_ROUTING_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_ALERT_RECIPIENTS = os.getenv("SMTP_ALERT_RECIPIENTS", "")
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

# Severity routing: which channels fire for which alert types
SEVERITY_MAP = {
    "approaching_limit": {"slack": True, "email": True, "pagerduty": False, "webhook": True},
    "budget_exceeded": {"slack": True, "email": True, "pagerduty": True, "webhook": True},
    "request_exceeds_budget": {"slack": True, "email": False, "pagerduty": False, "webhook": True},
}

# Slack color coding by alert type
SLACK_COLORS = {
    "approaching_limit": "#f0ad4e",   # yellow/warning
    "budget_exceeded": "#d9534f",     # red/critical
    "request_exceeds_budget": "#5bc0de",  # blue/info
}


async def send_all_notifications(alert, http_client: httpx.AsyncClient):
    """Dispatch alert to all configured channels in parallel."""
    routing = SEVERITY_MAP.get(alert.alert_type, SEVERITY_MAP["request_exceeds_budget"])

    tasks = []
    if routing["slack"] and SLACK_WEBHOOK_URL:
        tasks.append(_send_with_retry(_send_slack, alert, http_client, channel="slack"))
    if routing["email"] and SMTP_HOST and SMTP_ALERT_RECIPIENTS:
        tasks.append(_send_with_retry(_send_email, alert, channel="email"))
    if routing["pagerduty"] and PAGERDUTY_ROUTING_KEY:
        tasks.append(_send_with_retry(_send_pagerduty, alert, http_client, channel="pagerduty"))
    if routing["webhook"] and ALERT_WEBHOOK_URL:
        tasks.append(_send_with_retry(_send_generic_webhook, alert, http_client, channel="webhook"))

    if not tasks:
        logger.info(f"Alert (no channels configured): {alert.message}")
        return

    await asyncio.gather(*tasks, return_exceptions=True)


async def _send_with_retry(fn, *args, channel: str, max_retries: int = 3):
    """Retry with exponential backoff."""
    for attempt in range(max_retries):
        try:
            await fn(*args)
            logger.info(f"Alert sent via {channel}")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"{channel} attempt {attempt + 1} failed: {e}, retrying in {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"{channel} delivery failed after {max_retries} attempts: {e}")


async def _send_slack(alert, http_client: httpx.AsyncClient):
    """Send Slack notification using Block Kit format."""
    entity = alert.user_id or alert.team_id or "global"
    entity_type = "User" if alert.user_id else "Team" if alert.team_id else "Global"
    pct = (alert.current_spend / alert.budget_limit * 100) if alert.budget_limit > 0 else 0
    filled = int(pct / 5)
    progress = "█" * min(filled, 20) + "░" * max(0, 20 - filled)
    color = SLACK_COLORS.get(alert.alert_type, "#808080")

    payload = {
        "attachments": [{
            "color": color,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"Budget Alert: {alert.alert_type.replace('_', ' ').title()}"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*{entity_type}:*\n{entity}"},
                        {"type": "mrkdwn", "text": f"*Threshold:*\n{alert.threshold_percent:.1f}%"},
                        {"type": "mrkdwn", "text": f"*Spend:*\n${alert.current_spend:.2f}"},
                        {"type": "mrkdwn", "text": f"*Limit:*\n${alert.budget_limit:.2f}"},
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{progress}``` {pct:.1f}%"}
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"AI Control Plane | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"}
                    ]
                }
            ]
        }]
    }

    response = await http_client.post(SLACK_WEBHOOK_URL, json=payload)
    response.raise_for_status()


async def _send_email(alert):
    """Send HTML email via SMTP."""
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
    except ImportError:
        logger.warning("aiosmtplib not installed, skipping email notification")
        return

    entity = alert.user_id or alert.team_id or "global"
    pct = (alert.current_spend / alert.budget_limit * 100) if alert.budget_limit > 0 else 0

    subject_map = {
        "approaching_limit": f"⚠️ Budget Warning: {pct:.0f}% used ({entity})",
        "budget_exceeded": f"🚨 Budget EXCEEDED: {entity}",
        "request_exceeds_budget": f"ℹ️ Request blocked: insufficient budget ({entity})",
    }
    subject = subject_map.get(alert.alert_type, f"Budget Alert: {alert.alert_type}")

    filled_width = min(int(pct), 100)
    color = "#f0ad4e" if alert.alert_type == "approaching_limit" else "#d9534f" if alert.alert_type == "budget_exceeded" else "#5bc0de"

    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: {color};">{alert.alert_type.replace('_', ' ').title()}</h2>
        <p>{alert.message}</p>
        <div style="background: #eee; border-radius: 8px; overflow: hidden; height: 24px; margin: 16px 0;">
            <div style="background: {color}; height: 100%; width: {filled_width}%; border-radius: 8px;"></div>
        </div>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Current Spend</strong></td><td>${alert.current_spend:.2f}</td></tr>
            <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Budget Limit</strong></td><td>${alert.budget_limit:.2f}</td></tr>
            <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Usage</strong></td><td>{pct:.1f}%</td></tr>
        </table>
        <p style="color: #888; font-size: 12px; margin-top: 24px;">AI Control Plane | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
    </body></html>
    """

    recipients = [r.strip() for r in SMTP_ALERT_RECIPIENTS.split(",") if r.strip()]
    if not recipients:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER or None,
        password=SMTP_PASSWORD or None,
        start_tls=True,
    )


async def _send_pagerduty(alert, http_client: httpx.AsyncClient):
    """Trigger PagerDuty incident via Events API v2 (critical alerts only)."""
    entity = alert.user_id or alert.team_id or "global"
    dedup_key = f"budget-{entity}-{alert.alert_type}"

    payload = {
        "routing_key": PAGERDUTY_ROUTING_KEY,
        "event_action": "trigger",
        "dedup_key": dedup_key,
        "payload": {
            "summary": f"Budget exceeded: {entity} at {alert.threshold_percent:.1f}% (${alert.current_spend:.2f}/${alert.budget_limit:.2f})",
            "source": "ai-control-plane",
            "severity": "critical",
            "custom_details": {
                "user_id": alert.user_id,
                "team_id": alert.team_id,
                "current_spend": alert.current_spend,
                "budget_limit": alert.budget_limit,
                "threshold_percent": alert.threshold_percent,
            },
        },
    }

    response = await http_client.post(
        "https://events.pagerduty.com/v2/enqueue",
        json=payload,
    )
    response.raise_for_status()


async def _send_generic_webhook(alert, http_client: httpx.AsyncClient):
    """Send to generic webhook URL (existing behavior)."""
    await http_client.post(
        ALERT_WEBHOOK_URL,
        json={
            "type": alert.alert_type,
            "user_id": alert.user_id,
            "team_id": alert.team_id,
            "threshold": alert.threshold_percent,
            "current_spend": alert.current_spend,
            "budget_limit": alert.budget_limit,
            "message": alert.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
