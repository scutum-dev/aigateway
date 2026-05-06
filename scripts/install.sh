#!/bin/sh
# =============================================================================
# Scutum installer
# =============================================================================
# Usage:
#   curl -fsSL https://scutum.dev/install.sh | sh
#   curl -fsSL https://scutum.dev/install.sh | sh -s -- --version 0.1.0 --dir ./scutum
#
# What this does:
#   1. Verifies prerequisites (docker + compose plugin, OR podman + podman-compose)
#   2. Creates an install directory (default: ./scutum) with config/, data/
#   3. Downloads docker-compose.release.yaml and the env template from the
#      tagged GitHub release
#   4. Bundles the Scutum license public key (for offline JWT verification)
#   5. Drops a `scutum` CLI wrapper for day-to-day operation
#   6. If config/.env doesn't exist yet, creates one from the template and
#      generates fresh random secrets (so the customer doesn't ship default
#      keys to production by accident)
#
# What this does NOT do:
#   - Pull images. Run `./scutum up` after editing config/.env to do that.
#   - Touch any existing config/.env (idempotent on re-run).
#
# Required env vars: none.
# Optional env vars: SCUTUM_VERSION, INSTALL_DIR, REPO (override for forks).
# =============================================================================

set -eu

SCUTUM_VERSION="${SCUTUM_VERSION:-0.1.0}"
INSTALL_DIR="${INSTALL_DIR:-${PWD}/scutum}"
# Release artifacts (install.sh, scutum CLI, compose, env template, license
# public key) are hosted on scutum.dev — NOT GitHub raw — because the source
# repo is private. Override BASE_URL to point at a fork/mirror.
BASE_URL="${BASE_URL:-https://scutum.dev/release/v${SCUTUM_VERSION}}"

# ----- argument parsing (when piped via `sh -s -- --flag value`) -------------
while [ $# -gt 0 ]; do
    case "$1" in
        --version) SCUTUM_VERSION="$2"; BASE_URL="https://scutum.dev/release/v${SCUTUM_VERSION}"; shift 2 ;;
        --dir)     INSTALL_DIR="$2"; shift 2 ;;
        --base)    BASE_URL="$2"; shift 2 ;;
        --help|-h) sed -n '2,30p' "$0" 2>/dev/null || head -30 < /dev/null; exit 0 ;;
        *) echo "unknown flag: $1 (use --help)" >&2; exit 1 ;;
    esac
done

# ----- helpers ---------------------------------------------------------------
say()  { printf '\033[1;36m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# ----- 1. prerequisites ------------------------------------------------------
say "Checking prerequisites"

COMPOSE_CMD=""
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    ok "found: $(docker --version | cut -d, -f1)"
elif command -v podman >/dev/null 2>&1 && command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
    ok "found: $(podman --version)"
else
    die "Need either Docker Engine 20.10+ with the compose plugin, or Podman 4.4+ with podman-compose. Install one and re-run."
fi

if ! command -v curl >/dev/null 2>&1; then
    die "curl is required to download release artifacts."
fi

# ----- 2. install dir --------------------------------------------------------
say "Installing into $INSTALL_DIR"
mkdir -p "$INSTALL_DIR/config"
cd "$INSTALL_DIR"

# ----- 3-4. fetch release artifacts ------------------------------------------
fetch() {
    out="$1"; src="$2"
    if [ -f "$out" ]; then
        # Don't overwrite local edits — installer is idempotent on re-run.
        ok "kept existing $out"
        return 0
    fi
    if curl -fsSL "$src" -o "$out"; then
        ok "fetched $out"
    else
        die "could not fetch $src — is v${SCUTUM_VERSION} a published Scutum release? See https://scutum.dev/ for current versions."
    fi
}

say "Fetching release artifacts (v${SCUTUM_VERSION})"
fetch docker-compose.yaml          "$BASE_URL/docker-compose.yaml"
fetch config/license-public.pem    "$BASE_URL/license-public.pem"
fetch config/.env.example          "$BASE_URL/.env.example"
fetch scutum                       "$BASE_URL/scutum"
chmod +x scutum

# ----- 5. .env initialization with generated secrets -------------------------
randhex() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex "${1:-32}"
    else
        # Last-resort fallback for minimal containers.
        head -c "${1:-32}" /dev/urandom | od -An -tx1 | tr -d ' \n'
    fi
}

if [ ! -f config/.env ]; then
    say "Creating config/.env with fresh random secrets"
    cp config/.env.example config/.env

    # Replace each CHANGE-ME-... placeholder with a fresh random value so the
    # customer never accidentally runs production with the example secrets.
    # If a value is already in the shell environment (e.g. trial-monolith
    # passes SCUTUM_API_KEY, JWT_SECRET_KEY etc. via Fly machine env vars
    # so the trial-provisioner can hand the user a working credential),
    # honour the pre-set value instead of randomising.
    SCUTUM_KEY="${SCUTUM_API_KEY:-sk-$(randhex 32)}"
    JWT_KEY="${JWT_SECRET_KEY:-$(randhex 32)}"
    INTERNAL_KEY="${INTERNAL_SERVICE_KEY:-$(randhex 32)}"
    PG_PASS="${POSTGRES_PASSWORD:-$(randhex 16)}"

    # POSIX-portable in-place edit (sed -i differs between BSD and GNU)
    tmpfile="$(mktemp)"
    sed \
        -e "s|sk-CHANGE-ME-openssl-rand-hex-32|${SCUTUM_KEY}|" \
        -e "s|^JWT_SECRET_KEY=CHANGE-ME-openssl-rand-hex-32|JWT_SECRET_KEY=${JWT_KEY}|" \
        -e "s|^INTERNAL_SERVICE_KEY=CHANGE-ME-openssl-rand-hex-32|INTERNAL_SERVICE_KEY=${INTERNAL_KEY}|" \
        -e "s|^POSTGRES_PASSWORD=CHANGE-ME-openssl-rand-hex-16|POSTGRES_PASSWORD=${PG_PASS}|" \
        config/.env > "$tmpfile" && mv "$tmpfile" config/.env
    chmod 600 config/.env
    ok "config/.env created (LICENSE_KEY and provider API keys are still empty — fill those in)"
else
    ok "config/.env already exists, leaving untouched"
fi

# ----- final guidance --------------------------------------------------------
echo
ok "Scutum v${SCUTUM_VERSION} installed in $INSTALL_DIR"
echo
say "Next steps:"
printf '  1. cd %s\n' "$INSTALL_DIR"
printf '  2. Edit config/.env — paste your LICENSE_KEY and at least one provider API key\n'
printf '  3. ./scutum up                # pulls images, starts the platform\n'
printf '  4. open http://localhost:5173 # admin console\n'
echo
say "Useful commands:"
printf '  ./scutum logs admin-api   ./scutum ps   ./scutum upgrade   ./scutum backup\n'
echo
