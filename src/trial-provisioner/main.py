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
import secrets
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import httpx
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
# Fly shared-cpu sizing rule: max memory_mb is cpus*2048 (2 GiB per vCPU on
# the shared class). Auto-derive cpus from the configured memory so an
# operator can just set MACHINE_MEMORY_MB and we pick the right cpu_kind.
MACHINE_CPUS = max(1, (MACHINE_MEMORY_MB + 2047) // 2048)
SCHEDULER_INTERVAL_S = int(os.getenv("SCHEDULER_INTERVAL_S", "3600"))
# Max seconds to wait for the trial machine to start serving HTTP 200 before
# we flip to 'active'. Cold-boot of dockerd + the full Scutum stack inside a
# 2GB Fly machine takes 2-4 min on the happy path; give 7 min of headroom.
# If the machine is still not ready after this, we mark active anyway and
# accept the user might see /booting briefly — better than failing.
READINESS_TIMEOUT_S = int(os.getenv("READINESS_TIMEOUT_S", "420"))
READINESS_POLL_S = int(os.getenv("READINESS_POLL_S", "5"))

# Provisioning sweeper: how often to scan for stuck 'provisioning' rows, and
# how long a row must have been at 'provisioning' before the sweeper retries.
# This is the safety net for: (a) NOTIFY events lost while the provisioner
# was restarting, (b) crashes mid-provision that left a row partially set up.
PROVISIONING_SWEEP_INTERVAL_S = int(os.getenv("PROVISIONING_SWEEP_INTERVAL_S", "60"))
PROVISIONING_STUCK_AFTER_S = int(os.getenv("PROVISIONING_STUCK_AFTER_S", "90"))
# Hard cap on automatic retries before a row is parked at 'failed' for a human.
PROVISION_MAX_ATTEMPTS = int(os.getenv("PROVISION_MAX_ATTEMPTS", "5"))

# Module-level state set in lifespan.
_db_pool: Optional[asyncpg.Pool] = None
_fly: Optional[FlyClient] = None
_cf: Optional[CloudflareClient] = None
_listener_task: Optional[asyncio.Task] = None
_scheduler_task: Optional[asyncio.Task] = None
_provisioning_sweeper_task: Optional[asyncio.Task] = None
# In-process guard against concurrent _provision() runs for the same trial id.
# (Postgres advisory lock would be more robust, but an in-process set covers
# the common case — sweeper firing while listener is also running.)
_provision_in_flight: set[str] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot the DB pool + Fly/Cloudflare clients + start the listener loop."""
    global _db_pool, _fly, _cf, _listener_task, _scheduler_task, _provisioning_sweeper_task

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
    # Periodic sweeper that re-issues provisioning for any row stuck at
    # 'provisioning' for more than PROVISIONING_STUCK_AFTER_S seconds. This is
    # the durability guarantee for the verify→provision handoff: even if a
    # NOTIFY is dropped, the row is picked up within ~60s.
    _provisioning_sweeper_task = asyncio.create_task(_provisioning_sweeper_loop())
    logger.info(
        "trial-provisioner started (region=%s, image=%s, base_domain=%s, sweep_interval=%ds)",
        FLY_REGION,
        MACHINE_IMAGE,
        TRIAL_BASE_DOMAIN,
        PROVISIONING_SWEEP_INTERVAL_S,
    )

    try:
        yield
    finally:
        for t in (_listener_task, _scheduler_task, _provisioning_sweeper_task):
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
    """On startup, kick off provisioning for any row at status='provisioning'.

    asyncpg's NOTIFY only delivers to live connections, so a restart loses
    pending events. We re-issue them ourselves at boot. We pick up rows
    regardless of whether `fly_app_name` is set — `_provision_inner` is
    idempotent and will resume from whatever state the Fly resources are in.
    """
    if not _db_pool:
        return
    try:
        rows = await _db_pool.fetch("SELECT id::text FROM trial_instances WHERE status = 'provisioning'")
    except Exception as e:
        logger.warning("resume_in_flight query failed: %s", e)
        return
    for row in rows:
        logger.info("resuming in-flight trial %s after restart", row["id"])
        asyncio.create_task(_provision(row["id"]))


# ----------------------------------------------------------------------------
# provisioning


async def _provision(trial_id: str) -> None:
    """Create the Fly app + DNS for one trial. Idempotent on retry.

    The function may be invoked multiple times for the same trial — by NOTIFY,
    by `_resume_in_flight` after restart, and by the periodic sweeper. The
    in-process `_provision_in_flight` set prevents two concurrent runs for
    the same id within one process; the early status check skips work for
    rows that have already moved to active/failed/deleted.
    """
    if not _db_pool or not _fly or not _cf:
        logger.error("provisioner not initialised; cannot provision %s", trial_id)
        return

    try:
        uuid.UUID(trial_id)
    except (ValueError, TypeError):
        logger.warning("ignoring NOTIFY with non-UUID payload: %r", trial_id)
        return

    if trial_id in _provision_in_flight:
        logger.info("trial %s already being provisioned in this process — skipping", trial_id)
        return
    _provision_in_flight.add(trial_id)

    try:
        await _provision_inner(trial_id)
    finally:
        _provision_in_flight.discard(trial_id)


async def _provision_inner(trial_id: str) -> None:
    assert _db_pool and _fly and _cf  # guaranteed by caller
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

    # Claim ownership of this app name + provision the per-trial credentials
    # immediately. If the row had a previous fly_app_name set (mid-flow crash),
    # we keep using that one and reuse the same secrets — never generate new
    # tokens for the same trial id, since the Fly machine is already booted
    # against the previous values.
    #
    # Three secrets fed to the trial machine via Fly env so install.sh respects
    # them (it has a `${VAR:-randhex}` fallback):
    #   - SCUTUM_API_KEY     — long-lived admin credential the user keeps,
    #   - BOOTSTRAP_TOKEN    — one-shot, exchanged at /auth/bootstrap for a JWT,
    #   - JWT_SECRET_KEY     — pinned so admin-api signs tokens deterministically
    #                          (would otherwise be randomised per install).
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT fly_app_name, api_key, bootstrap_token, jwt_secret FROM trial_instances WHERE id = $1",
            trial_id,
        )
        api_key = row["api_key"] if row and row["api_key"] else f"sk-{secrets.token_hex(32)}"
        bootstrap_token = row["bootstrap_token"] if row and row["bootstrap_token"] else secrets.token_hex(32)
        jwt_secret = row["jwt_secret"] if row and row["jwt_secret"] else secrets.token_hex(32)
        if row and row["fly_app_name"]:
            app_name = row["fly_app_name"]
            fly_url = f"{app_name}.fly.dev"
            fqdn = fly_url
        await conn.execute(
            """
            UPDATE trial_instances
            SET fly_app_name = COALESCE(fly_app_name, $2),
                api_key = $3,
                bootstrap_token = $4,
                jwt_secret = $5
            WHERE id = $1
            """,
            trial_id,
            app_name,
            api_key,
            bootstrap_token,
            jwt_secret,
        )

    try:
        # 1. Fly app — idempotent. "Already exists" means a previous run got
        # this far and crashed; we keep using the existing app.
        logger.info("[%s] creating Fly app %s", trial_id, app_name)
        try:
            await _fly.create_app(app_name)
        except FlyAPIError as e:
            if _is_already_exists(e):
                logger.info("[%s] Fly app %s already exists — resuming", trial_id, app_name)
            else:
                raise

        # 2. Public IPs. Without these the app gets only private 6PN routing
        # and *.fly.dev doesn't resolve. shared_v4 is free; v6 is free + dedicated.
        # Already-allocated IPs return errors that we treat as success.
        try:
            logger.info("[%s] allocating shared IPv4 + IPv6", trial_id)
            await _fly.allocate_shared_ipv4(app_name)
            await _fly.allocate_ipv6(app_name)
        except FlyAPIError as e:
            logger.warning("[%s] IP allocation non-fatal: %s", trial_id, e)

        # 3. Persistent volume — idempotent. If a volume named "data" already
        # exists for this app (previous run), reuse it.
        logger.info("[%s] creating volume", trial_id)
        try:
            vol = await _fly.create_volume(
                app_name=app_name,
                name="data",
                region=FLY_REGION,
                size_gb=FLY_VOLUME_GB,
            )
        except FlyAPIError as e:
            if _is_already_exists(e):
                logger.info("[%s] volume already exists — looking up existing volume", trial_id)
                vol = await _find_existing_volume(app_name) or {}
            else:
                raise
        volume_id = vol.get("id")

        # 4. Machine: scale-to-zero, mounts the volume. If a machine already
        # exists for this app (previous run), skip — we don't run a second one.
        existing_machines = await _list_machines(app_name)
        if existing_machines:
            logger.info(
                "[%s] machine already running on app %s (count=%d) — skipping run_machine",
                trial_id,
                app_name,
                len(existing_machines),
            )
        else:
            logger.info("[%s] starting machine (image=%s)", trial_id, MACHINE_IMAGE)
            await _fly.run_machine(
                app_name=app_name,
                image=MACHINE_IMAGE,
                region=FLY_REGION,
                env={
                    "TRIAL_ID": trial_id,
                    "PORT": "80",
                    # install.sh reads these via ${VAR:-randhex N} so the
                    # injected values win over random generation. Without
                    # this, the trial admin-api would have an unknown master
                    # key and the user could never log in.
                    "SCUTUM_API_KEY": api_key,
                    "BOOTSTRAP_TOKEN": bootstrap_token,
                    "JWT_SECRET_KEY": jwt_secret,
                },
                ports=[{"port": 443, "handlers": ["tls", "http"]}, {"port": 80, "handlers": ["http"]}],
                memory_mb=MACHINE_MEMORY_MB,
                cpus=MACHINE_CPUS,
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

        # 5b. Wait for the in-machine stack to actually answer HTTP 200 before
        # flipping to 'active'. The Fly machine "started" event fires when the
        # container is running, but inside it dockerd + postgres + admin-api +
        # litellm still need ~3 min to become reachable. Without this gate the
        # /try page redirects users to a URL that 502s for several minutes.
        # Note: front-of-house nginx serves a /booting page during this window
        # (see fly-monolith/nginx.conf) — we look for a JSON response from
        # admin-api specifically, which only happens once admin-api is up.
        # Using the *.fly.dev hostname (not the brandable one) so we don't
        # race the per-trial Let's Encrypt cert issuance.
        readiness_url = f"https://{fly_url}/api/v1/license"
        ready = await _wait_for_readiness(trial_id, readiness_url)
        if not ready:
            logger.warning("[%s] readiness timeout after %ds — marking active anyway", trial_id, READINESS_TIMEOUT_S)

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
        # Decide whether to park as failed (hard) or leave at provisioning
        # for the sweeper to retry (transient). We default to retry-friendly
        # because Fly/Cloudflare 5xx + network blips are far more common than
        # genuine misconfiguration. The sweeper enforces PROVISION_MAX_ATTEMPTS
        # so a truly broken row eventually parks at 'failed' with the error.
        attempts = await _bump_attempts_and_get(trial_id, e)
        retryable = _is_retryable_error(e) and attempts < PROVISION_MAX_ATTEMPTS
        if retryable:
            logger.warning(
                "[%s] provision attempt %d failed (transient): %s — sweeper will retry",
                trial_id,
                attempts,
                e,
            )
            # Leave status at 'provisioning' so the sweeper picks it up. We
            # only stamped provision_error so the user sees current diagnostic
            # text on the /try status poll.
            return
        logger.exception("[%s] provisioning failed permanently after %d attempts", trial_id, attempts)
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
# provisioning helpers — idempotency + retry classification


def _is_already_exists(e: FlyAPIError) -> bool:
    """True if a Fly API error indicates the resource already exists.

    Fly returns 422 with a body like 'Validation failed: Name has already been taken'
    for duplicate apps, and similar for volumes. The exact wording isn't part
    of an API contract, so match defensively on common substrings.
    """
    body = getattr(e, "body", "") or ""
    msg = str(e).lower()
    body_l = body.lower()
    needles = ("already been taken", "already exists", "name_taken", "duplicate")
    return any(n in msg or n in body_l for n in needles)


def _is_retryable_error(e: BaseException) -> bool:
    """Classify an exception as transient (worth retrying) vs hard.

    Retryable: network errors, Fly/CF 5xx, timeouts, anything not clearly
    a 4xx misconfiguration we can't fix by retrying.
    """
    if isinstance(e, (httpx.HTTPError, httpx.TimeoutException, ConnectionError, OSError)):
        return True
    if isinstance(e, FlyAPIError):
        return e.status >= 500 or e.status == 429
    if isinstance(e, CloudflareAPIError):
        # CF status codes can be HTTP or their internal numeric codes; play safe
        # and retry anything that's not obviously auth/validation.
        return e.status >= 500 or e.status == 429
    return False


async def _bump_attempts_and_get(trial_id: str, exc: BaseException) -> int:
    """Stamp provision_error and increment a counter held in provision_error
    via attempt-tag prefix. We don't have a dedicated column, so we encode
    attempts inline at the front of provision_error: '[attempt=N] <msg>'.

    Returns the new attempt count.
    """
    if not _db_pool:
        return PROVISION_MAX_ATTEMPTS  # caller treats as hard-fail
    async with _db_pool.acquire() as conn:
        existing = await conn.fetchval("SELECT provision_error FROM trial_instances WHERE id = $1", trial_id)
    attempts = 1
    if existing and isinstance(existing, str) and existing.startswith("[attempt="):
        try:
            n = int(existing.split("[attempt=", 1)[1].split("]", 1)[0])
            attempts = n + 1
        except (ValueError, IndexError):
            pass
    tagged = f"[attempt={attempts}] {type(exc).__name__}: {str(exc)[:480]}"
    async with _db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE trial_instances SET provision_error = $2 WHERE id = $1",
            trial_id,
            tagged,
        )
    return attempts


async def _find_existing_volume(app_name: str) -> Optional[Dict[str, Any]]:
    """Look up an existing 'data' volume on an app, if any."""
    if not _fly:
        return None
    try:
        client = await _fly._client()  # noqa: SLF001 — internal helper, single-process
        resp = await client.get(f"/apps/{app_name}/volumes")
        if resp.status_code == 200:
            for v in resp.json() or []:
                if v.get("name") == "data":
                    return v
    except Exception as e:  # noqa: BLE001
        logger.warning("could not list volumes on %s: %s", app_name, e)
    return None


async def _list_machines(app_name: str) -> List[Dict[str, Any]]:
    """List machines on an app. Empty list on error (treat as 'no machines')."""
    if not _fly:
        return []
    try:
        client = await _fly._client()  # noqa: SLF001
        resp = await client.get(f"/apps/{app_name}/machines")
        if resp.status_code == 200:
            return resp.json() or []
    except Exception as e:  # noqa: BLE001
        logger.warning("could not list machines on %s: %s", app_name, e)
    return []


# ----------------------------------------------------------------------------
# provisioning sweeper — durability net for the verify→provision handoff


async def _provisioning_sweeper_loop() -> None:
    """Periodically scan for stuck 'provisioning' rows and re-run them.

    Catches three failure modes that would otherwise leave a trial wedged:
      a) NOTIFY was emitted while the listener was disconnected (LISTEN
         delivery is best-effort; reconnect doesn't replay).
      b) provisioner process restarted between NOTIFY and provision start.
      c) provision crashed mid-flow (e.g. Fly transient 5xx) and is now in a
         retryable state.
    """
    # Initial delay so a freshly-started listener has time to drain real
    # NOTIFYs before the sweeper starts second-guessing it.
    await asyncio.sleep(PROVISIONING_SWEEP_INTERVAL_S)
    while True:
        try:
            if _db_pool:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=PROVISIONING_STUCK_AFTER_S)
                rows = await _db_pool.fetch(
                    """
                    SELECT id::text AS id
                    FROM trial_instances
                    WHERE status = 'provisioning'
                      AND verified_at IS NOT NULL
                      AND verified_at < $1
                    ORDER BY verified_at
                    """,
                    cutoff,
                )
                for row in rows:
                    trial_id = row["id"]
                    if trial_id in _provision_in_flight:
                        continue
                    logger.info(
                        "[sweeper] resuming stuck trial %s (verified > %ds ago)",
                        trial_id,
                        PROVISIONING_STUCK_AFTER_S,
                    )
                    asyncio.create_task(_provision(trial_id))
        except asyncio.CancelledError:
            return
        except Exception as e:  # noqa: BLE001
            logger.warning("provisioning sweeper iteration failed: %s", e)
        await asyncio.sleep(PROVISIONING_SWEEP_INTERVAL_S)


async def _wait_for_readiness(trial_id: str, url: str) -> bool:
    """Poll the trial URL until it returns a 2xx/4xx (= the real stack is up).

    Returns True on success, False on timeout. We accept any 2xx OR a 4xx —
    a 401/403/404 from admin-api means the FastAPI process is alive and
    routing requests, which is what we care about. The /booting fallback
    page returns 200 too but with content-type=text/html (not JSON), so we
    additionally require the JSON content-type to confirm we hit admin-api
    rather than the still-booting nginx fallback.
    """
    deadline = asyncio.get_event_loop().time() + READINESS_TIMEOUT_S
    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        verify=True,  # CF/Fly cert chain; trust default CA bundle
    ) as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await client.get(url)
                ctype = r.headers.get("content-type", "")
                if "json" in ctype.lower():
                    logger.info("[%s] readiness check passed: %s → %d", trial_id, url, r.status_code)
                    return True
                logger.debug("[%s] readiness probe got %d (ctype=%s) — still booting", trial_id, r.status_code, ctype)
            except (httpx.HTTPError, httpx.HTTPStatusError):
                pass  # connection refused / TLS handshake failure — retry
            await asyncio.sleep(READINESS_POLL_S)
    return False


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
