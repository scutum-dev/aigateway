#!/bin/bash
# Scutum monolith entrypoint — boot dockerd, install Scutum, start the stack,
# bring up the front-of-house nginx, and tail combined logs.
#
# Idempotent: re-runs after a Fly machine restart pick up existing state from
# /var/lib/docker (the persistent volume). Postgres + Redis data survives.
set -euo pipefail

log() { echo "[scutum-monolith] $(date -Iseconds) $*"; }

# Boot ordering rationale (read top-to-bottom):
#   0. front-of-house nginx FIRST  → :80 serves /booting before dockerd/stack
#   1. dockerd (storage=fuse-overlayfs for nested-VM support)
#   2. golden-image docker-load    → first boot only, skips ghcr.io pulls
#   3. install.sh                  → first boot only, drops release artifacts
#   4. docker compose up           → 5-attempt retry loop, fail loudly if all fail
#   5. background watchdogs        → dockerd + compose self-heal every 30s
#   6. log tail (foreground)
# All long-running children get SIGTERM in the trap below for graceful shutdown.

# 0. Start the front-of-house nginx FIRST so the public :80 has something to
# serve during the dockerd + stack boot. Its config has a /booting error_page
# fallback (see nginx.conf), so any inbound request gets the friendly waiting
# page rather than connection-refused / Fly 502 splash.
log "starting front-of-house nginx on :80 (booting page until upstreams are up)"
nginx &
NGINX_PID=$!

# 1. Start dockerd in the background (dind base image entrypoint normally
# does this, but we want full control of the boot sequence).
start_dockerd() {
    # overlay2 doesn't work inside Fly's Firecracker micro-VM (kernel doesn't
    # expose nested overlayfs upperdir). fuse-overlayfs runs in userspace and
    # works in nested-virtualization environments.
    dockerd-entrypoint.sh dockerd \
        --host=unix:///var/run/docker.sock \
        --storage-driver=fuse-overlayfs \
        >>/var/log/dockerd.log 2>&1 &
    DOCKERD_PID=$!
}
log "starting dockerd (storage-driver=fuse-overlayfs for nested-VM support)..."
start_dockerd

# Wait for the daemon socket to be ready before issuing any docker commands.
log "waiting for dockerd to come online..."
for i in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
        log "dockerd ready after ${i}s"
        break
    fi
    sleep 1
done
if ! docker info >/dev/null 2>&1; then
    log "FATAL: dockerd never came up; tail of log:"
    tail -50 /var/log/dockerd.log
    exit 1
fi

# 2. Golden-image cache load (first boot only). The Dockerfile COPYs a
# docker-save tarball of all 6 Scutum service images into /opt; loading it
# into dind's image cache eliminates the per-trial 5-7 min ghcr.io pull.
#
# State (markers + install bundle) lives under /var/lib/docker/scutum-state/.
# The trial-provisioner mounts the Fly persistent volume AT /var/lib/docker,
# so this path survives Fly machine update / PATCH restarts. The previous
# location (/etc/scutum) was an anonymous Docker volume that got tossed
# whenever Fly created a fresh writable layer (= every config PATCH), which
# made every claim re-run the 8-min docker-load from scratch.
SCUTUM_STATE=/var/lib/docker/scutum-state
mkdir -p "$SCUTUM_STATE"
GOLDEN_TARBALL=/opt/scutum-images.tar.gz
GOLDEN_MARKER="$SCUTUM_STATE/golden-loaded"
if [ -f "$GOLDEN_TARBALL" ] && [ ! -f "$GOLDEN_MARKER" ]; then
    log "loading golden image cache from $GOLDEN_TARBALL into dind"
    if gunzip -c "$GOLDEN_TARBALL" | docker load; then
        touch "$GOLDEN_MARKER"
        # Don't rm the tarball: it's part of the image layer and will
        # reappear on every fresh writable layer anyway. The marker is
        # the durable record that we already loaded these images into
        # /var/lib/docker (which IS now persistent).
        log "golden image cache loaded; marker written to $GOLDEN_MARKER"
    else
        log "WARN: docker load failed — falling back to runtime ghcr.io pulls"
    fi
elif [ -f "$GOLDEN_MARKER" ]; then
    log "golden image cache already loaded (marker present) — skipping"
fi

# 3. Drop the install bundle on first boot. Skip if already installed (this
# is just an idempotent re-fetch of the release artifacts). Bundle lives
# under /var/lib/docker/scutum-state/install/ so it survives PATCH restarts.
SCUTUM_DIR="$SCUTUM_STATE/install"
if [ ! -d "$SCUTUM_DIR/scutum" ]; then
    log "first boot: running install.sh"
    mkdir -p "$SCUTUM_DIR"
    cd "$SCUTUM_DIR"
    # Pull the release artifacts off scutum.dev (same source customers use).
    SCUTUM_VERSION=${SCUTUM_VERSION:-0.1.0}
    curl -fsSL "https://scutum.dev/install.sh" | sh -s -- || {
        log "FATAL: install.sh failed"; exit 1;
    }
fi
cd "$SCUTUM_DIR/scutum"

# 3b. Sync host env vars into config/.env for the per-trial secrets.
# install.sh wrote these from the FIRST-BOOT env values; if the warm pool's
# claim flow PATCHed the Fly machine env afterwards, the host env has the
# real per-trial values but config/.env still has the warmup placeholders.
# `docker compose --env-file config/.env` reads the file on disk, so without
# this sync admin-api boots with stale secrets — user types their emailed
# API key and gets 401 because LITELLM_MASTER_KEY is the warmup placeholder.
# Run on every boot; cheap (no-op when values match).
ENV_FILE="$SCUTUM_DIR/scutum/config/.env"
if [ -f "$ENV_FILE" ]; then
    for var in SCUTUM_API_KEY BOOTSTRAP_TOKEN JWT_SECRET_KEY; do
        host_val="$(printenv "$var" || true)"
        [ -z "$host_val" ] && continue
        if grep -q "^${var}=" "$ENV_FILE"; then
            # awk for portable in-place edit — sed -i differs between BSD/GNU
            # and special chars in the secret would break naive sed escaping.
            tmp="$(mktemp)"
            awk -v var="$var" -v val="$host_val" -F= '
                BEGIN { OFS = "=" }
                $1 == var { print var "=" val; next }
                { print }
            ' "$ENV_FILE" > "$tmp" && mv "$tmp" "$ENV_FILE"
        else
            printf "%s=%s\n" "$var" "$host_val" >> "$ENV_FILE"
        fi
    done
    log "synced per-trial secrets from host env into config/.env"
fi

# 4. Bring up the stack with a retry loop. Without retry, a transient
# pull/network blip permanently broke the trial — `|| true` swallowed the
# error and the readiness probe just timed out. The retry gives us 5
# attempts spaced 10s apart before declaring the trial dead.
COMPOSE_ATTEMPTS=5
compose_up_with_retry() {
    local attempt
    for attempt in $(seq 1 $COMPOSE_ATTEMPTS); do
        log "compose up attempt ${attempt}/${COMPOSE_ATTEMPTS}"
        if ./scutum up 2>/tmp/compose-err; then
            log "compose up succeeded on attempt ${attempt}"
            return 0
        fi
        log "compose up attempt ${attempt} failed; stderr:"
        tail -30 /tmp/compose-err || true
        sleep 10
    done
    log "FATAL: compose up failed after ${COMPOSE_ATTEMPTS} attempts"
    return 1
}
if ! compose_up_with_retry; then
    log "compose stack failed to come up — leaving nginx serving /booting; watchdog will keep retrying"
    # Don't exit — the watchdog below keeps trying so a transient ghcr.io
    # outage at boot doesn't permanently brick the trial machine.
fi

# Wait until admin-ui responds — purely informational at this point. nginx is
# already serving the /booting fallback to anyone who hits :80 in the meantime;
# once admin-ui returns 200, normal proxy_pass takes over automatically.
log "waiting for admin-ui to come online..."
for i in $(seq 1 300); do
    if curl -fsS -o /dev/null --max-time 2 http://localhost:5173/ 2>/dev/null; then
        log "admin-ui ready after ${i}s"
        break
    fi
    sleep 1
done

# 5. Watchdogs — keep the trial alive across dockerd crashes / compose drops.
# Both run in the background; either one detecting a fault triggers a
# self-heal that restarts the lost component without operator intervention.
watchdog_loop() {
    local last_dockerd_check=0
    while true; do
        sleep 30
        # Dockerd liveness — `docker info` is the canonical check; if it
        # fails, dockerd has died and we restart it.
        if ! docker info >/dev/null 2>&1; then
            log "WATCHDOG: dockerd not responding — restarting"
            start_dockerd
            # Give it 30s to come back before checking compose.
            sleep 30
            continue
        fi
        # Compose stack — if any service we depend on isn't running, kick
        # `up -d` to bring it back. Idempotent, just no-ops if everything
        # is fine. Cheap (one docker compose call every 30s).
        if ! (cd "$SCUTUM_DIR/scutum" && ./scutum up >/dev/null 2>&1); then
            log "WATCHDOG: compose up returned non-zero (service drop?) — retrying next tick"
        fi
    done
}
log "starting dockerd + compose watchdog (30s tick)"
watchdog_loop &
WATCHDOG_PID=$!

# 6. Tail the combined Scutum logs as the foreground process so Fly's log
# stream picks up everything.
log "tailing stack logs..."
docker compose --env-file config/.env logs -f --tail=20 &
TAIL_PID=$!

# Forward SIGTERM/SIGINT to children for graceful shutdown.
trap 'kill -TERM $WATCHDOG_PID $NGINX_PID $TAIL_PID $DOCKERD_PID 2>/dev/null; wait' SIGTERM SIGINT

wait $TAIL_PID
