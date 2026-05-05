"""Trial provisioner — consumes pg_notify('trial_provision', trial_id) and
spins up a real Fly app + Cloudflare DNS record for each new verified trial.

Architecture:

    admin-api ─NOTIFY─► postgres ─LISTEN─► trial-provisioner
                                                   │
                                                   ▼
                                      ┌─────────────────────────┐
                                      │ for each trial id:      │
                                      │  1. fly apps create     │
                                      │  2. fly volumes create  │
                                      │  3. fly machines create │
                                      │  4. fly certs create    │
                                      │  5. cloudflare CNAME    │
                                      │  6. UPDATE trial row    │
                                      └─────────────────────────┘

Failures: write the error to trial_instances.provision_error and flip status
to 'failed' so the user sees a meaningful message on /try. Operator can then
manually clean up via the Fly + Cloudflare dashboards or rerun by flipping
status back to 'provisioning' and re-firing the NOTIFY.

For MVP the per-trial machine image is `MACHINE_IMAGE` env (default a tiny
nginx-alpine showing 'Coming soon'). Replace with the real Scutum monolith
image once §2 of the plan ships.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import asyncpg
from fastapi import FastAPI

# Allow `from cloudflare import ...` style imports when running under uvicorn.
sys.path.insert(0, str(Path(__file__).parent))

from cloudflare import CloudflareAPIError, CloudflareClient  # noqa: E402
from fly import FlyAPIError, FlyClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("trial-provisioner")


DATABASE_URL = os.getenv("DATABASE_URL", "")
TRIAL_BASE_DOMAIN = os.getenv("TRIAL_BASE_DOMAIN", "scutum.dev")
TRIAL_LIFETIME_DAYS = int(os.getenv("TRIAL_LIFETIME_DAYS", "30"))
FLY_REGION = os.getenv("FLY_REGION", "iad")  # us-east default; matches lowest-latency for US/EU mix
FLY_VOLUME_GB = int(os.getenv("FLY_VOLUME_GB", "5"))
# Default placeholder is nginx:alpine (listens on 80; runs as root inside the
# isolated Fly micro-VM which is fine for a trial). The unprivileged variant
# listens on 8080 and would mismatch our internal_port=80 below.
MACHINE_IMAGE = os.getenv("MACHINE_IMAGE", "nginx:alpine")
MACHINE_MEMORY_MB = int(os.getenv("MACHINE_MEMORY_MB", "2048"))
SCHEDULER_INTERVAL_S = int(os.getenv("SCHEDULER_INTERVAL_S", "3600"))

# Module-level state set in lifespan.
_db_pool: Optional[asyncpg.Pool] = None
_fly: Optional[FlyClient] = None
_cf: Optional[CloudflareClient] = None
_listener_task: Optional[asyncio.Task] = None
_scheduler_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot the DB pool + Fly/Cloudflare clients + start the listener loop."""
    global _db_pool, _fly, _cf, _listener_task, _scheduler_task

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be set")

    _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=4)
    _fly = FlyClient()
    _cf = CloudflareClient()

    # Sweep any 'provisioning' rows we might have missed during a restart —
    # NOTIFY is fire-and-forget, so a worker restart loses in-flight events.
    asyncio.create_task(_resume_in_flight())

    _listener_task = asyncio.create_task(_listen_loop())
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info(
        "trial-provisioner started (region=%s, image=%s, base_domain=%s)",
        FLY_REGION,
        MACHINE_IMAGE,
        TRIAL_BASE_DOMAIN,
    )

    try:
        yield
    finally:
        for t in (_listener_task, _scheduler_task):
            if t and not t.done():
                t.cancel()
        if _fly:
            await _fly.aclose()
        if _cf:
            await _cf.aclose()
        if _db_pool:
            await _db_pool.close()


app = FastAPI(title="Scutum trial-provisioner", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "db": _db_pool is not None,
        "fly_token_present": bool(_fly and _fly.api_token),
        "cloudflare_token_present": bool(_cf and _cf.api_token),
        "image": MACHINE_IMAGE,
    }


# ----------------------------------------------------------------------------
# listener loop


async def _listen_loop() -> None:
    """Subscribe to pg_notify('trial_provision'). Re-enqueue + retry on disconnect.

    Each NOTIFY payload is a trial_instances.id; the handler runs the
    provisioning for that row in a fire-and-forget task so one slow run
    doesn't block the next notification.
    """
    while True:
        try:
            async with _db_pool.acquire() as conn:
                await conn.add_listener("trial_provision", _handle_notify)
                logger.info("listening on pg_notify('trial_provision')")
                while True:
                    await asyncio.sleep(60)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning("listener loop error: %s — reconnecting in 5s", e)
            await asyncio.sleep(5)


def _handle_notify(connection, pid, channel, payload: str) -> None:
    """asyncpg passes notifications synchronously; spawn the actual work."""
    logger.info("NOTIFY received: trial_id=%s", payload)
    asyncio.create_task(_provision(payload))


async def _resume_in_flight() -> None:
    """On startup, kick off provisioning for any rows already at status='provisioning'.

    asyncpg's NOTIFY only delivers to live connections, so a restart loses
    pending events. We re-issue them ourselves at boot.
    """
    if not _db_pool:
        return
    try:
        rows = await _db_pool.fetch(
            "SELECT id::text FROM trial_instances WHERE status = 'provisioning' AND fly_app_name IS NULL"
        )
    except Exception as e:
        logger.warning("resume_in_flight query failed: %s", e)
        return
    for row in rows:
        logger.info("resuming in-flight trial %s after restart", row["id"])
        asyncio.create_task(_provision(row["id"]))


# ----------------------------------------------------------------------------
# provisioning


async def _provision(trial_id: str) -> None:
    """Create the Fly app + DNS for one trial. Idempotent on retry."""
    if not _db_pool or not _fly or not _cf:
        logger.error("provisioner not initialised; cannot provision %s", trial_id)
        return

    try:
        uuid.UUID(trial_id)
    except (ValueError, TypeError):
        logger.warning("ignoring NOTIFY with non-UUID payload: %r", trial_id)
        return

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, status, fly_app_name FROM trial_instances WHERE id = $1",
            trial_id,
        )
        if not row:
            logger.warning("trial %s vanished before provisioning", trial_id)
            return
        if row["status"] != "provisioning":
            logger.info("trial %s is %s, not provisioning — skipping", trial_id, row["status"])
            return

    # Names: keep them short + DNS-safe. Fly app names must be <30 chars
    # globally unique; the 12-char hex suffix is plenty.
    short_id = trial_id.split("-")[0]
    app_name = f"scutum-trial-{short_id}"
    fly_url = f"{app_name}.fly.dev"
    # Custom hostname is one level under scutum.dev so it's covered by
    # Cloudflare Universal SSL (free wildcard) — no per-trial cert issuance
    # needed. Cloudflare proxied=true terminates TLS at the edge with that
    # cert; Fly addCertificate registers the hostname so Fly's edge routes
    # the proxied request to the right app.
    custom_fqdn = f"{short_id}.{TRIAL_BASE_DOMAIN}"
    # Surface the brandable hostname; falls back to fly.dev if Cloudflare DNS
    # creation fails (the route updates fqdn at the very end of provisioning).
    fqdn = fly_url

    try:
        # 1. Fly app.
        logger.info("[%s] creating Fly app %s", trial_id, app_name)
        await _fly.create_app(app_name)

        # 2. Public IPs. Without these the app gets only private 6PN routing
        # and *.fly.dev doesn't resolve. shared_v4 is free; v6 is free + dedicated.
        try:
            logger.info("[%s] allocating shared IPv4 + IPv6", trial_id)
            await _fly.allocate_shared_ipv4(app_name)
            await _fly.allocate_ipv6(app_name)
        except FlyAPIError as e:
            logger.warning("[%s] IP allocation non-fatal: %s", trial_id, e)

        # 3. Persistent volume (so postgres data inside the trial survives sleeps).
        logger.info("[%s] creating volume", trial_id)
        vol = await _fly.create_volume(
            app_name=app_name,
            name="data",
            region=FLY_REGION,
            size_gb=FLY_VOLUME_GB,
        )
        volume_id = vol.get("id")

        # 4. Machine: scale-to-zero, mounts the volume.
        logger.info("[%s] starting machine (image=%s)", trial_id, MACHINE_IMAGE)
        await _fly.run_machine(
            app_name=app_name,
            image=MACHINE_IMAGE,
            region=FLY_REGION,
            env={"TRIAL_ID": trial_id, "PORT": "80"},
            ports=[{"port": 443, "handlers": ["tls", "http"]}, {"port": 80, "handlers": ["http"]}],
            memory_mb=MACHINE_MEMORY_MB,
            volume_id=volume_id,
            volume_mount_path="/data",
        )

        # 5. Custom hostname — three steps, each best-effort:
        #    a. Fly addCertificate registers the hostname for routing AND
        #       returns the DNS-01 validation target (Fly uses LE DNS-01).
        #    b. Cloudflare CNAME (DNS-only) so traffic resolves to Fly.
        #    c. Cloudflare CNAME for `_acme-challenge.<id>.scutum.dev` →
        #       <flydns.net> so Let's Encrypt validates the cert request.
        #
        # Once (c) is in place, Fly's LE poll picks it up within ~30 seconds
        # and the per-trial cert is live. Until then, traffic falls through
        # CF's Universal SSL on cached resolvers (still HTTPS, just CF cert
        # instead of Fly cert). Either way the user sees a green padlock.
        #
        # SSL mode note: Cloudflare proxied=true would also work, but the
        # CF→Fly leg would need zone-wide SSL set to "Full" (not Flexible).
        # We can't change zone-wide SSL without breaking the Flexible-mode
        # marketing site at scutum.dev → OCI. Per-hostname overrides need Pro.
        custom_hostname_ready = False
        validation_record = None  # filled by addCertificate response
        try:
            cert_resp = await _fly.create_certificate(app_name, custom_fqdn)
            cert_data = (cert_resp.get("addCertificate") or {}).get("certificate") or {}
            validation_record = cert_data.get("dnsValidationTarget")
            logger.info(
                "[%s] Fly hostname registered: %s (validation_target=%s)",
                trial_id,
                custom_fqdn,
                validation_record,
            )
        except FlyAPIError as e:
            logger.warning("[%s] Fly addCertificate non-fatal: %s", trial_id, e)
        try:
            await _cf.create_cname(name=custom_fqdn, target=fly_url, proxied=False)
            logger.info("[%s] CF CNAME (DNS-only) %s → %s", trial_id, custom_fqdn, fly_url)
            custom_hostname_ready = True
        except CloudflareAPIError as e:
            if "already exists" in str(e).lower() or e.status == 81057:
                logger.info("[%s] CF record already exists, ok", trial_id)
                custom_hostname_ready = True
            else:
                logger.warning("[%s] CF DNS create non-fatal: %s", trial_id, e)
        # ACME DNS-01 validation record so Fly's LE flow can issue the cert.
        if validation_record:
            try:
                await _cf.create_cname(
                    name=f"_acme-challenge.{custom_fqdn}",
                    target=validation_record,
                    proxied=False,
                )
                logger.info(
                    "[%s] ACME validation CNAME _acme-challenge.%s → %s", trial_id, custom_fqdn, validation_record
                )
            except CloudflareAPIError as e:
                if "already exists" in str(e).lower() or e.status == 81057:
                    logger.info("[%s] ACME validation CNAME already exists, ok", trial_id)
                else:
                    logger.warning("[%s] ACME validation CNAME create non-fatal: %s", trial_id, e)

        # Promote fqdn to the brandable hostname iff CF DNS creation succeeded
        # — that means CF Universal SSL covers it and the URL works in the
        # browser. Otherwise stay on fly.dev.
        if custom_hostname_ready:
            fqdn = custom_fqdn

        # 6. Mark active.
        expires = datetime.now(timezone.utc) + timedelta(days=TRIAL_LIFETIME_DAYS)
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE trial_instances
                SET status = 'active',
                    fly_app_name = $2,
                    fqdn = $3,
                    activated_at = CURRENT_TIMESTAMP,
                    expires_at = $4,
                    provision_error = NULL
                WHERE id = $1
                """,
                trial_id,
                app_name,
                fqdn,
                expires,
            )
        logger.info("[%s] trial active at https://%s (expires %s)", trial_id, fqdn, expires.isoformat())

    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] provisioning failed", trial_id)
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE trial_instances
                SET status = 'failed',
                    provision_error = $2
                WHERE id = $1
                """,
                trial_id,
                f"{type(e).__name__}: {str(e)[:500]}",
            )


# ----------------------------------------------------------------------------
# lifecycle scheduler — daily-ish sweep for expired + reminder-due trials


async def _scheduler_loop() -> None:
    while True:
        try:
            await asyncio.sleep(SCHEDULER_INTERVAL_S)
            await _delete_expired_trials()
            # 3-day reminder email is a follow-up; not in MVP. Stub left
            # in the trial_instances.reminder_email_sent_at column for
            # later wiring.
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning("scheduler iteration failed: %s", e)


async def _delete_expired_trials() -> None:
    if not _db_pool or not _fly or not _cf:
        return
    rows = await _db_pool.fetch(
        """
        SELECT id::text AS id, fly_app_name, fqdn
        FROM trial_instances
        WHERE status = 'active' AND expires_at < CURRENT_TIMESTAMP
        """
    )
    for row in rows:
        trial_id = row["id"]
        app_name = row["fly_app_name"]
        fqdn = row["fqdn"]
        logger.info("[%s] expired — tearing down %s", trial_id, app_name)
        try:
            if app_name:
                await _fly.delete_app(app_name)
            if fqdn:
                rid = await _cf.find_record_id(fqdn)
                if rid:
                    await _cf.delete_record(rid)
            await _db_pool.execute(
                "UPDATE trial_instances SET status='deleted', deleted_at=CURRENT_TIMESTAMP WHERE id=$1",
                trial_id,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("[%s] teardown failed: %s — will retry next sweep", trial_id, e)
