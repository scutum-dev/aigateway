"""Trial signup router — entry point for the /try flow.

Three endpoints:
- `POST /api/v1/trial-signup` (public): validates Cloudflare Turnstile, dedupes
  by email, creates a `users` + `organizations` + `trial_instances` row in
  pending_verification state, sends a verification email.
- `GET /api/v1/trial-signup/{trial_id}/verify?token=...` (public): the link
  the user clicks in the verification email. Flips the trial to `provisioning`
  and emits a Postgres NOTIFY so the trial-provisioner can pick it up.
- `GET /api/v1/trial-signup/{trial_id}/status` (public): polled by the /try
  page while the user waits. Returns `{status, url?, error?, expires_at}`.

Public-by-design (no auth gate) but rate-limited per-IP and gated by Turnstile;
the same pattern landing-backend uses for `/api/demo-request`.

The Fly + Cloudflare provisioning lives in `src/trial-provisioner/` and runs
out-of-band — this router only writes the row and emits the NOTIFY.
"""

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import deps
import httpx
from audit import log_audit_event
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---- config (read once at import) -------------------------------------------

TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

TRIAL_LIFETIME_DAYS = int(os.getenv("TRIAL_LIFETIME_DAYS", "30"))
TRIAL_BASE_DOMAIN = os.getenv("TRIAL_BASE_DOMAIN", "trial.scutum.dev")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://scutum.dev")

# Rate limit on /api/v1/trial-signup keyed by source IP.
SIGNUP_RATE_LIMIT_MAX = int(os.getenv("SIGNUP_RATE_LIMIT_MAX", "5"))
SIGNUP_RATE_LIMIT_WINDOW_S = int(os.getenv("SIGNUP_RATE_LIMIT_WINDOW_S", "3600"))

# Verification token TTL — short by design; user must click within this window.
VERIFICATION_TTL_HOURS = 24


# ---- pydantic models --------------------------------------------------------


class TrialSignupRequest(BaseModel):
    email: EmailStr = Field(description="Work email address. One trial per address.")
    turnstile_token: str = Field(min_length=1, description="Cloudflare Turnstile cf-turnstile-response value.")


class TrialSignupResponse(BaseModel):
    trial_id: str = Field(description="UUID of the trial row; used for status polling.")
    status: str = Field(description="Always 'pending_verification' on success.")


class TrialStatusResponse(BaseModel):
    status: str = Field(description="One of pending_verification|provisioning|active|expired|deleted|failed.")
    url: Optional[str] = Field(default=None, description="Trial URL when status=active.")
    error: Optional[str] = Field(default=None, description="provision_error when status=failed.")
    expires_at: Optional[str] = Field(default=None, description="ISO timestamp when the trial will be deleted.")


# ---- helpers ----------------------------------------------------------------


async def _verify_turnstile(token: str, source_ip: Optional[str]) -> bool:
    """Server-side validation of the Turnstile widget's response token.

    When TURNSTILE_SECRET_KEY is unset (dev/test), accept any non-empty token
    so the form is testable without spinning up Cloudflare config. Production
    deploy must set the secret.
    """
    if not TURNSTILE_SECRET_KEY:
        logger.warning("TURNSTILE_SECRET_KEY unset — accepting token without verification (dev mode).")
        return bool(token)

    if not deps.http_client:
        # Without a shared client we can't reach Turnstile; fail closed.
        logger.error("http_client unavailable; cannot verify Turnstile token")
        return False

    payload = {"secret": TURNSTILE_SECRET_KEY, "response": token}
    if source_ip:
        payload["remoteip"] = source_ip
    try:
        resp = await deps.http_client.post(TURNSTILE_VERIFY_URL, data=payload, timeout=5.0)
        body = resp.json()
        return bool(body.get("success"))
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Turnstile verification failed: %s", e)
        return False


async def _check_rate_limit(conn, source_ip: str) -> bool:
    """Return True if the IP is under the limit, False if it should be blocked.

    Uses a small Postgres-backed counter so we don't need Redis on the marketing
    VM. Window is rolling — rows older than the window are eligible for cleanup
    by a separate sweep but only matter for the count here.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=SIGNUP_RATE_LIMIT_WINDOW_S)
    count = await conn.fetchval(
        """
        SELECT COUNT(*) FROM trial_signup_attempts
        WHERE source_ip = $1 AND created_at > $2
        """,
        source_ip,
        cutoff,
    )
    return (count or 0) < SIGNUP_RATE_LIMIT_MAX


async def _record_attempt(conn, source_ip: str, email: str, success: bool) -> None:
    """Append an attempt row for rate-limit accounting + abuse forensics."""
    await conn.execute(
        """
        INSERT INTO trial_signup_attempts (source_ip, email, success)
        VALUES ($1, $2, $3)
        """,
        source_ip,
        email,
        success,
    )


def _client_ip(request: Request) -> str:
    """Best-effort source-IP extraction (Cloudflare → nginx → us)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _slug_from_email(email: str) -> str:
    """Generate a unique-enough org slug from the email + a short random suffix."""
    local = email.split("@", 1)[0].lower()
    safe = "".join(c if c.isalnum() else "-" for c in local).strip("-") or "trial"
    return f"{safe[:20]}-{secrets.token_hex(3)}"


async def _send_verification_email(email: str, trial_id: str, token: str) -> bool:
    """Send the click-to-verify email. Reuses landing-backend's SMTP config.

    Returns True if dispatched, False if SMTP isn't configured (dev mode); in
    that case the caller logs the verify URL so the developer can click it.
    """
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        logger.warning("SMTP unconfigured — verification email not sent for trial %s", trial_id)
        return False
    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        import aiosmtplib
    except ImportError:
        logger.warning("aiosmtplib not installed; cannot send verification email")
        return False

    verify_url = f"{PUBLIC_BASE_URL}/api/v1/trial-signup/{trial_id}/verify?token={token}"
    text_body = (
        "You're one click away from your Scutum trial.\n\n"
        "Verify your email and we'll start provisioning your instance:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in {VERIFICATION_TTL_HOURS} hours.\n\n"
        "If you didn't request this, ignore the email — nothing was created.\n\n"
        "— Scutum\n"
        "https://scutum.dev/"
    )
    # Minimal inline-styled HTML so the email looks intentional in any client.
    html_body = f"""\
<!DOCTYPE html>
<html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; max-width: 560px; margin: 32px auto; padding: 0 24px; color: #0A0A0A; line-height: 1.6;">
  <p style="font-family: 'Iowan Old Style', Georgia, serif; font-style: italic; font-size: 28px; margin: 0 0 24px;">Scutum</p>
  <p>You're one click away from your Scutum trial.</p>
  <p style="margin: 32px 0;">
    <a href="{verify_url}" style="background: #0A0A0A; color: #FFFFFF; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 500;">Verify email and start trial</a>
  </p>
  <p style="font-size: 13px; color: #525252;">
    Or paste this link into your browser:<br>
    <a href="{verify_url}" style="color: #525252; word-break: break-all;">{verify_url}</a>
  </p>
  <p style="font-size: 13px; color: #525252;">This link expires in {VERIFICATION_TTL_HOURS} hours. If you didn't request a trial, ignore this email — nothing was created.</p>
  <hr style="border: none; border-top: 1px solid #E5E5E5; margin: 32px 0;">
  <p style="font-size: 12px; color: #6B7280;">
    Scutum · <a href="https://scutum.dev/" style="color: #6B7280;">scutum.dev</a>
  </p>
</body></html>
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verify your Scutum trial"
    msg["From"] = os.getenv("DEMO_FROM", "hello@scutum.dev")
    msg["To"] = email
    msg["Reply-To"] = os.getenv("DEMO_REPLY_TO", "hello@scutum.dev")
    # Order matters: the last attachment is the preferred one shown to the
    # client. text first, html second → HTML rendered when supported.
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=int(os.getenv("SMTP_PORT", "587")),
            username=os.getenv("SMTP_USER") or None,
            password=os.getenv("SMTP_PASSWORD") or None,
            start_tls=True,
        )
        logger.info("Verification email dispatched (trial=%s)", trial_id)
        return True
    except Exception as e:
        logger.warning("SMTP send failed for trial %s: %s", trial_id, e)
        return False


# ---- routes -----------------------------------------------------------------


@router.post("/trial-signup", response_model=TrialSignupResponse)
async def create_trial_signup(data: TrialSignupRequest, request: Request) -> TrialSignupResponse:
    """Public signup endpoint. Validates Turnstile, dedupes email, sends verify email."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    source_ip = _client_ip(request)
    email = data.email.lower()

    async with deps.db_pool.acquire() as conn:
        # Rate limit before anything expensive.
        if not await _check_rate_limit(conn, source_ip):
            await _record_attempt(conn, source_ip, email, success=False)
            raise HTTPException(status_code=429, detail="Too many signup attempts; try again in an hour.")

        # Bot-check.
        if not await _verify_turnstile(data.turnstile_token, source_ip):
            await _record_attempt(conn, source_ip, email, success=False)
            raise HTTPException(status_code=400, detail="Bot-check failed; please retry.")

        # Dedupe: one trial per email, regardless of status. Even an expired
        # trial blocks re-signup with the same address — operator can clear.
        existing_user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
        if existing_user:
            existing_trial = await conn.fetchrow(
                "SELECT id, status FROM trial_instances WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
                existing_user["id"],
            )
            if existing_trial:
                await _record_attempt(conn, source_ip, email, success=False)
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "A trial already exists for this email. Check your inbox for the verification "
                        "link, or email hello@scutum.dev if you've lost the URL."
                    ),
                )

        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.now(timezone.utc) + timedelta(hours=VERIFICATION_TTL_HOURS)

        # Single transaction so the user/org/trial triple lands atomically.
        async with conn.transaction():
            user_id = await conn.fetchval(
                """
                INSERT INTO users (email, display_name, auth_provider, is_active, is_platform_admin)
                VALUES ($1, $2, 'trial', TRUE, FALSE)
                ON CONFLICT (email) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                email,
                email.split("@", 1)[0],
            )
            org_name = f"Trial · {email}"
            org_slug = _slug_from_email(email)
            org_id = await conn.fetchval(
                """
                INSERT INTO organizations (name, slug, description, is_active)
                VALUES ($1, $2, 'Auto-provisioned trial org', TRUE)
                RETURNING id
                """,
                org_name,
                org_slug,
            )
            trial_id = await conn.fetchval(
                """
                INSERT INTO trial_instances
                    (user_id, org_id, status, verification_token, verification_expires_at)
                VALUES ($1, $2, 'pending_verification', $3, $4)
                RETURNING id
                """,
                user_id,
                org_id,
                verification_token,
                verification_expires,
            )

        await _record_attempt(conn, source_ip, email, success=True)

    await log_audit_event(
        actor_id=str(user_id),
        actor_email=email,
        action="trial_signup",
        resource_type="trial_instance",
        resource_id=str(trial_id),
        org_id=str(org_id),
        request=request,
    )

    sent = await _send_verification_email(email, str(trial_id), verification_token)
    if not sent:
        # Dev mode: surface the URL in the log so a developer can click through
        # without actually receiving an email.
        logger.warning(
            "Verification URL (no SMTP): %s/api/v1/trial-signup/%s/verify?token=%s",
            PUBLIC_BASE_URL,
            trial_id,
            verification_token,
        )

    return TrialSignupResponse(trial_id=str(trial_id), status="pending_verification")


@router.get("/trial-signup/{trial_id}/verify")
async def verify_trial_signup(trial_id: str, token: str, request: Request):
    """Click-target for the verification email.

    Flips trial status pending_verification → provisioning, emits
    `pg_notify('trial_provision', trial_id)` so the trial-provisioner picks
    the row up, then 302-redirects to /try/?trial_id=... so the user lands on
    a friendly status page rather than seeing JSON.
    """
    from fastapi.responses import RedirectResponse

    def _redirect(suffix: str) -> RedirectResponse:
        # 303 See Other — proper status for a successful POST/GET that hands
        # the user off to a viewable page (some browsers re-execute the GET
        # on a 302; 303 forces a clean GET on the destination).
        return RedirectResponse(url=f"{PUBLIC_BASE_URL}/try/{suffix}", status_code=303)

    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        uuid.UUID(trial_id)  # noqa: BLE001 — just want the validity check
    except (ValueError, TypeError):
        return _redirect("?error=invalid")

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, status, verification_token, verification_expires_at, user_id, org_id
            FROM trial_instances
            WHERE id = $1
            """,
            trial_id,
        )
        if not row:
            return _redirect("?error=not_found")

        if row["status"] != "pending_verification":
            # Idempotent — clicking the link a second time after we've moved on
            # is a no-op. Redirect into /try with the trial id so the polling
            # picks up wherever it currently is.
            return _redirect(f"?trial_id={trial_id}")

        if not secrets.compare_digest(row["verification_token"] or "", token):
            return _redirect("?error=invalid_token")

        expires_at = row["verification_expires_at"]
        if expires_at and expires_at < datetime.now(timezone.utc):
            return _redirect("?error=expired")

        # Flip status, clear the token, stamp verified_at, then NOTIFY so the
        # provisioner picks it up.
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE trial_instances
                SET status = 'provisioning',
                    verification_token = NULL,
                    verification_expires_at = NULL,
                    verified_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                trial_id,
            )
            await conn.execute("SELECT pg_notify('trial_provision', $1)", trial_id)

        await log_audit_event(
            actor_id=str(row["user_id"]),
            action="trial_verified",
            resource_type="trial_instance",
            resource_id=str(trial_id),
            org_id=str(row["org_id"]),
            request=request,
        )

    return _redirect(f"?trial_id={trial_id}")


@router.get("/trial-signup/{trial_id}/status", response_model=TrialStatusResponse)
async def trial_status(trial_id: str) -> TrialStatusResponse:
    """Polling endpoint for the /try page while provisioning runs."""
    if not deps.db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        uuid.UUID(trial_id)  # noqa: BLE001
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid trial id.") from None

    async with deps.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT status, fqdn, provision_error, expires_at
            FROM trial_instances
            WHERE id = $1
            """,
            trial_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Trial not found.")

    url = f"https://{row['fqdn']}" if row["fqdn"] else None
    return TrialStatusResponse(
        status=row["status"],
        url=url if row["status"] == "active" else None,
        error=row["provision_error"] if row["status"] == "failed" else None,
        expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
    )
