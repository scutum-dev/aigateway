#!/bin/bash
# Scutum monolith entrypoint — boot dockerd, install Scutum, start the stack,
# bring up the front-of-house nginx, and tail combined logs.
#
# Idempotent: re-runs after a Fly machine restart pick up existing state from
# /var/lib/docker (the persistent volume). Postgres + Redis data survives.
set -euo pipefail

log() { echo "[scutum-monolith] $(date -Iseconds) $*"; }

# 1. Start dockerd in the background (dind base image entrypoint normally
# does this, but we want full control of the boot sequence).
log "starting dockerd (storage-driver=fuse-overlayfs for nested-VM support)..."
# overlay2 doesn't work inside Fly's Firecracker micro-VM (kernel doesn't
# expose nested overlayfs upperdir). fuse-overlayfs runs in userspace and
# works in nested-virtualization environments.
dockerd-entrypoint.sh dockerd \
    --host=unix:///var/run/docker.sock \
    --storage-driver=fuse-overlayfs \
    >/var/log/dockerd.log 2>&1 &
DOCKERD_PID=$!

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

# 2. Drop the install bundle on first boot. Skip if already installed (this
# is just an idempotent re-fetch of the release artifacts).
SCUTUM_DIR=/etc/scutum/install
if [ ! -d "$SCUTUM_DIR/scutum" ]; then
    log "first boot: running install.sh"
    mkdir -p "$SCUTUM_DIR"
    cd "$SCUTUM_DIR"
    # Pull the release artifacts off scutum.dev (same source customers use).
    SCUTUM_VERSION=${SCUTUM_VERSION:-0.1.0}
    curl -fsSL "https://scutum.dev/install.sh" | sh -s -- || {
        log "install.sh failed"; exit 1;
    }
fi
cd "$SCUTUM_DIR/scutum"

# 3. Bring up the stack. `--no-recreate` so an existing healthy container
# isn't churned on every machine wake-up.
log "bringing up the Scutum stack via scutum CLI"
./scutum up || true

# Wait until admin-ui responds — that's the primary user-facing surface.
log "waiting for admin-ui to come online..."
for i in $(seq 1 120); do
    if curl -fsS -o /dev/null --max-time 2 http://localhost:5173/ 2>/dev/null; then
        log "admin-ui ready after ${i}s"
        break
    fi
    sleep 1
done

# 4. Start the front-of-house nginx that maps :80 inbound to the right
# internal service.
log "starting front-of-house nginx on :80"
nginx -g 'daemon off;' &
NGINX_PID=$!

# 5. Tail the combined Scutum logs as the foreground process so Fly's log
# stream picks up everything.
log "tailing stack logs..."
docker compose --env-file config/.env logs -f --tail=20 &
TAIL_PID=$!

# Forward SIGTERM/SIGINT to children for graceful shutdown.
trap 'kill -TERM $NGINX_PID $TAIL_PID $DOCKERD_PID 2>/dev/null; wait' SIGTERM SIGINT

wait $TAIL_PID
