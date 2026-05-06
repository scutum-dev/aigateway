"""Warm-pool fast path for trial provisioning.

Background loop keeps N pre-booted Fly machines stopped and ready. When a
user signs up we claim one, swap in their per-trial secrets, start it, and
they're in the dashboard in ~1 min instead of the ~10 min cold start.

State machine (see migration 029):

    NEW row at 'warming'
        │
        │  warm_one_machine: create app + IPs + volume + machine
        │  with placeholder env, wait readiness, stop machine
        │
        ▼
    'ready'  ──── stale (>14d) ────►  destroyed (recycler)
        │
        │  claim_warm_machine: PATCH per-trial env, add CF DNS
        │  + Fly cert, start machine, wait readiness
        ▼
    'claimed'  (FK on trial_instances; trial teardown destroys app)

Idempotency: each function is safe to retry. Fly resource creates catch
"already exists" (uniqueness constraint, name_taken, etc.) and resume.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import asyncpg
import httpx
from cloudflare import CloudflareAPIError, CloudflareClient
from fly import FlyAPIError, FlyClient

logger = logging.getLogger("trial-provisioner.pool")

MIN_POOL_SIZE = int(os.getenv("WARM_POOL_MIN_SIZE", "3"))
MAX_POOL_SIZE = int(os.getenv("WARM_POOL_MAX_SIZE", "10"))
POOL_REGION = os.getenv("FLY_REGION", "iad")
POOL_RECYCLE_AFTER_DAYS = int(os.getenv("WARM_POOL_RECYCLE_AFTER_DAYS", "14"))
WARMING_TIMEOUT_S = int(os.getenv("WARM_POOL_WARMING_TIMEOUT_S", "1800"))  # 30 min
WARM_READINESS_TIMEOUT_S = int(os.getenv("WARM_POOL_READINESS_TIMEOUT_S", "900"))  # 15 min
CLAIM_READINESS_TIMEOUT_S = int(os.getenv("WARM_POOL_CLAIM_READINESS_TIMEOUT_S", "300"))  # 5 min


def _is_already_exists_err(e: BaseException) -> bool:
    """Same substring set as the slow path's _is_already_exists. Duplicated
    here to avoid a circular import — pool is a leaf module, main imports it.
    """
    body = getattr(e, "body", "") or ""
    msg = str(e).lower()
    body_l = body.lower()
    needles = ("already been taken", "already exists", "name_taken", "duplicate", "uniqueness constraint")
    return any(n in msg or n in body_l for n in needles)


# ---- warmup ----------------------------------------------------------------


async def warm_one_machine(
    db_pool: asyncpg.Pool,
    fly: FlyClient,
    *,
    image: str,
    memory_mb: int,
    cpus: int,
    volume_gb: int,
) -> Optional[str]:
    """Create one warm machine: app + IPs + volume + machine with placeholder
    env, wait for readiness, then stop it. Returns the warm_machines.id on
    success, None on failure (the row is left at 'failed' with last_warm_error
    populated for the recycler to pick up later).

    Placeholder env values (`SCUTUM_API_KEY=warmup-placeholder` etc.) are
    intentionally non-secret — admin-api will start with these but no user
    can authenticate against a placeholder. They're swapped at claim time.
    """
    warm_id = await _claim_new_warm_row(db_pool, region=POOL_REGION)
    if warm_id is None:
        return None  # pool already at MAX or DB write failed

    # App naming: scutum-warm-<short> distinguishes pool machines from
    # claimed trials in the Fly dashboard. Once claimed, the user-facing
    # subdomain is the trial's <short>.scutum.dev pointing at this app.
    short = warm_id.split("-")[0]
    app_name = f"scutum-warm-{short}"
    fly_url = f"{app_name}.fly.dev"

    try:
        # Persist app_name immediately so a crash mid-warmup is recoverable.
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE warm_machines SET fly_app_name = $2 WHERE id = $1",
                warm_id,
                app_name,
            )

        logger.info("[warm %s] creating Fly app %s", warm_id, app_name)
        try:
            await fly.create_app(app_name)
        except FlyAPIError as e:
            if _is_already_exists_err(e):
                logger.info("[warm %s] app %s already exists — resuming warmup", warm_id, app_name)
            else:
                raise

        try:
            await fly.allocate_shared_ipv4(app_name)
            await fly.allocate_ipv6(app_name)
        except FlyAPIError as e:
            logger.warning("[warm %s] IP allocation non-fatal: %s", warm_id, e)

        logger.info("[warm %s] creating volume", warm_id)
        try:
            vol = await fly.create_volume(app_name=app_name, name="data", region=POOL_REGION, size_gb=volume_gb)
        except FlyAPIError as e:
            if _is_already_exists_err(e):
                vol = await _find_volume(fly, app_name, "data") or {}
            else:
                raise
        volume_id = vol.get("id")

        # Boot the monolith with placeholder env. install.sh reads these via
        # ${VAR:-randhex} — they're real values that will be overwritten when
        # this row is claimed (PATCH machine env), at which point dind +
        # services restart with the user's real per-trial secrets.
        existing_machines = await _list_machines(fly, app_name)
        if existing_machines:
            machine = existing_machines[0]
            machine_id = machine.get("id")
            logger.info("[warm %s] machine already exists (%s) — reusing", warm_id, machine_id)
        else:
            logger.info("[warm %s] starting machine (image=%s)", warm_id, image)
            machine = await fly.run_machine(
                app_name=app_name,
                image=image,
                region=POOL_REGION,
                env={
                    "TRIAL_ID": "warmup",
                    "PORT": "80",
                    # Real values; admin-api will run with these but no user
                    # logs in during warmup. Swapped on claim.
                    "SCUTUM_API_KEY": f"sk-warmup-{secrets.token_hex(16)}",
                    "BOOTSTRAP_TOKEN": secrets.token_hex(32),
                    "JWT_SECRET_KEY": secrets.token_hex(32),
                },
                ports=[
                    {"port": 443, "handlers": ["tls", "http"]},
                    {"port": 80, "handlers": ["http"]},
                ],
                memory_mb=memory_mb,
                cpus=cpus,
                volume_id=volume_id,
                volume_mount_path="/data",
            )
            machine_id = machine.get("id")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE warm_machines
                SET fly_machine_id = $2, fly_volume_id = $3
                WHERE id = $1
                """,
                warm_id,
                machine_id,
                volume_id,
            )

        # Wait for the in-machine stack to actually serve. The first warmup
        # of any monolith image flavour does the slow docker-load + alembic
        # + LiteLLM db push (~10 min). Subsequent warmups (after image
        # update) reuse the volume's golden-image marker and are faster.
        readiness_url = f"https://{fly_url}/api/v1/license"
        ready = await _wait_for_readiness(readiness_url, WARM_READINESS_TIMEOUT_S, who=f"warm {warm_id}")
        if not ready:
            raise RuntimeError(f"warmup readiness timeout after {WARM_READINESS_TIMEOUT_S}s")

        # Stop the machine — pool slot now ready to claim.
        logger.info("[warm %s] stopping machine for pool", warm_id)
        await fly.stop_machine(app_name, machine_id)

        recycle = datetime.now(timezone.utc) + timedelta(days=POOL_RECYCLE_AFTER_DAYS)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE warm_machines
                SET status = 'ready',
                    warmed_at = CURRENT_TIMESTAMP,
                    recycle_after = $2,
                    last_warm_error = NULL
                WHERE id = $1
                """,
                warm_id,
                recycle,
            )
        logger.info("[warm %s] WARM (recycle by %s)", warm_id, recycle.isoformat())
        return warm_id

    except Exception as e:  # noqa: BLE001
        logger.exception("[warm %s] warmup failed", warm_id)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE warm_machines
                SET status = 'failed',
                    last_warm_error = $2
                WHERE id = $1
                """,
                warm_id,
                f"{type(e).__name__}: {str(e)[:480]}",
            )
        return None


async def _claim_new_warm_row(db_pool: asyncpg.Pool, region: str) -> Optional[str]:
    """Insert a new 'warming' row, capping at MAX_POOL_SIZE total active
    (warming + ready) rows. Returns the new id, or None if pool is full.
    """
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM warm_machines
                WHERE status IN ('warming', 'ready') AND region = $1
                """,
                region,
            )
            if count and count >= MAX_POOL_SIZE:
                return None
            new_id = await conn.fetchval(
                """
                INSERT INTO warm_machines (fly_app_name, region, status)
                VALUES ($1, $2, 'warming')
                RETURNING id::text
                """,
                # Placeholder app_name (UNIQUE NOT NULL on column); replaced
                # in warm_one_machine. Use a UUID prefix so it's unique even
                # if the warm row insert races.
                f"placeholder-{secrets.token_hex(8)}",
                region,
            )
            return new_id


# ---- claim -----------------------------------------------------------------


async def claim_warm_machine(
    db_pool: asyncpg.Pool,
    fly: FlyClient,
    cf: CloudflareClient,
    *,
    trial_id: str,
    short_id: str,
    custom_fqdn: str,
    api_key: str,
    bootstrap_token: str,
    jwt_secret: str,
) -> Optional[Dict[str, Any]]:
    """Try to claim a 'ready' warm machine for this trial.

    Returns {"fly_app_name": ..., "fqdn": ...} on success, None if the pool
    is empty. None lets the caller fall back to the slow create-from-scratch
    path so a pool exhaustion never blocks signup.
    """
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # SKIP LOCKED so concurrent claims don't fight over the same row.
            row = await conn.fetchrow(
                """
                SELECT id::text, fly_app_name, fly_machine_id
                FROM warm_machines
                WHERE status = 'ready' AND region = $1
                ORDER BY warmed_at NULLS LAST
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """,
                POOL_REGION,
            )
            if not row:
                logger.info("[claim %s] pool empty in region %s — falling back to slow path", trial_id, POOL_REGION)
                return None
            await conn.execute(
                """
                UPDATE warm_machines
                SET status = 'claimed',
                    claimed_at = CURRENT_TIMESTAMP,
                    claimed_by_trial_id = $2::uuid
                WHERE id = $1::uuid
                """,
                row["id"],
                trial_id,
            )

    warm_app = row["fly_app_name"]
    warm_machine_id = row["fly_machine_id"]
    fly_url = f"{warm_app}.fly.dev"
    logger.info("[claim %s] claimed warm machine %s (app=%s)", trial_id, row["id"], warm_app)

    try:
        # 1. Fetch current machine config + PATCH per-trial env.
        machine = await fly.get_machine(warm_app, warm_machine_id)
        current_config = machine.get("config", {})
        await fly.update_machine_env(
            warm_app,
            warm_machine_id,
            current_config=current_config,
            env_overrides={
                "TRIAL_ID": trial_id,
                "SCUTUM_API_KEY": api_key,
                "BOOTSTRAP_TOKEN": bootstrap_token,
                "JWT_SECRET_KEY": jwt_secret,
            },
        )
        logger.info("[claim %s] machine env patched with per-trial secrets", trial_id)

        # 2. Add the brandable hostname → Fly cert + Cloudflare CNAME.
        custom_hostname_ready = False
        validation_record = None
        try:
            cert_resp = await fly.create_certificate(warm_app, custom_fqdn)
            cert_data = (cert_resp.get("addCertificate") or {}).get("certificate") or {}
            validation_record = cert_data.get("dnsValidationTarget")
            logger.info("[claim %s] Fly hostname registered (validation=%s)", trial_id, validation_record)
        except FlyAPIError as e:
            logger.warning("[claim %s] Fly addCertificate non-fatal: %s", trial_id, e)
        try:
            await cf.create_cname(name=custom_fqdn, target=fly_url, proxied=False)
            custom_hostname_ready = True
        except CloudflareAPIError as e:
            if "already exists" in str(e).lower() or e.status == 81057:
                custom_hostname_ready = True
            else:
                logger.warning("[claim %s] CF DNS create non-fatal: %s", trial_id, e)
        if validation_record:
            try:
                await cf.create_cname(name=f"_acme-challenge.{custom_fqdn}", target=validation_record, proxied=False)
            except CloudflareAPIError as e:
                if "already exists" in str(e).lower() or e.status == 81057:
                    pass
                else:
                    logger.warning("[claim %s] ACME validation CNAME non-fatal: %s", trial_id, e)

        # 3. Start the machine. The PATCH itself triggers a restart, so this
        # is a no-op on the happy path; safe to call regardless.
        await fly.start_machine(warm_app, warm_machine_id)
        logger.info("[claim %s] machine starting", trial_id)

        # 4. Wait for the stack to come back up with new env. ~30-60s normally,
        # since dockerd's data dir is preserved and only env propagation +
        # service restart is needed.
        readiness_url = f"https://{fly_url}/api/v1/license"
        ready = await _wait_for_readiness(readiness_url, CLAIM_READINESS_TIMEOUT_S, who=f"claim {trial_id}")
        if not ready:
            logger.warning(
                "[claim %s] readiness timeout after %ds — marking active anyway",
                trial_id,
                CLAIM_READINESS_TIMEOUT_S,
            )

        fqdn = custom_fqdn if custom_hostname_ready else fly_url
        return {"fly_app_name": warm_app, "fqdn": fqdn}

    except Exception as e:  # noqa: BLE001
        # Claim failed — release the row so the recycler/warmer can retry on
        # this Fly app rather than burning a pool slot. Mark 'failed' so the
        # warmer doesn't accidentally re-warm against a partially-touched
        # machine.
        logger.exception("[claim %s] claim failed; releasing warm row to 'failed'", trial_id)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE warm_machines
                SET status = 'failed',
                    last_warm_error = $2
                WHERE id = $1::uuid
                """,
                row["id"],
                f"{type(e).__name__} during claim: {str(e)[:480]}",
            )
        return None


# ---- recycler --------------------------------------------------------------


async def recycle_stale(db_pool: asyncpg.Pool, fly: FlyClient) -> None:
    """One-shot sweep: reap stuck-warming + past-recycle rows + failed rows.

    Stuck-warming: warmer crashed mid-flow, row left at 'warming' with no
    progress — flip to 'failed' so the warmer's normal failure-handling
    path picks it up next tick.

    Past-recycle: 'ready' machines that have been idle in the pool for >
    POOL_RECYCLE_AFTER_DAYS days. Volume cost adds up; reap and replenish
    so we always have fresh-ish images.

    Failed: destroy the Fly app (idempotent on 404) and mark 'recycled' so
    pool counts refresh and the warmer can spin a new slot.
    """
    cutoff_warming = datetime.now(timezone.utc) - timedelta(seconds=WARMING_TIMEOUT_S)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE warm_machines
            SET status = 'failed',
                last_warm_error = COALESCE(last_warm_error, '') || ' [stuck warming > ' || $2 || ' s]'
            WHERE status = 'warming' AND created_at < $1
            """,
            cutoff_warming,
            WARMING_TIMEOUT_S,
        )

        await conn.execute(
            """
            UPDATE warm_machines
            SET status = 'failed',
                last_warm_error = COALESCE(last_warm_error, '') || ' [past recycle deadline]'
            WHERE status = 'ready' AND recycle_after IS NOT NULL AND recycle_after < CURRENT_TIMESTAMP
            """
        )

        failed_rows = await conn.fetch(
            """
            SELECT id::text, fly_app_name FROM warm_machines
            WHERE status = 'failed' AND fly_app_name NOT LIKE 'placeholder-%'
            LIMIT 5
            """
        )

    for row in failed_rows:
        try:
            logger.info("[recycle] destroying %s", row["fly_app_name"])
            await fly.delete_app(row["fly_app_name"])
        except Exception as e:  # noqa: BLE001
            logger.warning("[recycle] delete_app %s failed: %s", row["fly_app_name"], e)
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE warm_machines SET status = 'recycled' WHERE id = $1::uuid",
                row["id"],
            )

    # Drop placeholder rows that never got past _claim_new_warm_row before
    # crashing — they have no Fly resources to delete.
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE warm_machines
            SET status = 'recycled'
            WHERE status = 'failed' AND fly_app_name LIKE 'placeholder-%'
            """
        )


# ---- warmer loop -----------------------------------------------------------


async def pool_warmer_loop(
    db_pool: asyncpg.Pool,
    fly: FlyClient,
    *,
    image: str,
    memory_mb: int,
    cpus: int,
    volume_gb: int,
    interval_s: int = 60,
) -> None:
    """Long-running task: keep (warming + ready) >= MIN_POOL_SIZE.

    Runs the recycler every tick + spawns warm_one_machine tasks until the
    pool is at target size. Warmups run concurrently — at startup with an
    empty pool we'll spawn MIN_POOL_SIZE in parallel.
    """
    logger.info(
        "pool warmer started (region=%s, min=%d, max=%d, recycle=%dd)",
        POOL_REGION,
        MIN_POOL_SIZE,
        MAX_POOL_SIZE,
        POOL_RECYCLE_AFTER_DAYS,
    )
    while True:
        try:
            await recycle_stale(db_pool, fly)
            async with db_pool.acquire() as conn:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM warm_machines
                    WHERE status IN ('warming', 'ready') AND region = $1
                    """,
                    POOL_REGION,
                )
            need = MIN_POOL_SIZE - (count or 0)
            if need > 0:
                logger.info("[pool] %d active, need %d more — spawning warmups", count or 0, need)
                for _ in range(need):
                    asyncio.create_task(
                        warm_one_machine(db_pool, fly, image=image, memory_mb=memory_mb, cpus=cpus, volume_gb=volume_gb)
                    )
        except asyncio.CancelledError:
            return
        except Exception as e:  # noqa: BLE001
            logger.warning("pool warmer iteration failed: %s", e)
        await asyncio.sleep(interval_s)


# ---- helpers ---------------------------------------------------------------


async def _find_volume(fly: FlyClient, app_name: str, name: str) -> Optional[Dict[str, Any]]:
    try:
        client = await fly._client()  # noqa: SLF001
        resp = await client.get(f"/apps/{app_name}/volumes")
        if resp.status_code == 200:
            for v in resp.json() or []:
                if v.get("name") == name:
                    return v
    except Exception:  # noqa: BLE001
        return None
    return None


async def _list_machines(fly: FlyClient, app_name: str) -> list:
    try:
        client = await fly._client()  # noqa: SLF001
        resp = await client.get(f"/apps/{app_name}/machines")
        if resp.status_code == 200:
            return resp.json() or []
    except Exception:  # noqa: BLE001
        return []
    return []


async def _wait_for_readiness(url: str, timeout_s: int, *, who: str) -> bool:
    """Poll the URL until it returns JSON. Same semantics as
    main._wait_for_readiness (kept here to avoid the circular import).
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await client.get(url)
                ctype = r.headers.get("content-type", "")
                if "json" in ctype.lower():
                    logger.info("[%s] readiness passed: %s → %d", who, url, r.status_code)
                    return True
            except (httpx.HTTPError, httpx.TimeoutException):
                pass
            await asyncio.sleep(5)
    return False
