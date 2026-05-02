#!/bin/bash
# One-shot deploy: pushes code + .env to an OCI VM and brings the
# landing-only profile up. Idempotent — re-run any time after `git pull`.
#
# Usage:
#   ./scripts/deploy-oci.sh <public_ip> [ssh_user] [ssh_key]
#
# Defaults:
#   ssh_user=ubuntu
#   ssh_key=~/.ssh/id_ed25519_personal
#
# Example:
#   ./scripts/deploy-oci.sh 161.118.178.104 ubuntu ~/.ssh/id_ed25519_personal

set -euo pipefail

IP="${1:?Usage: $0 <ip> [user] [key]}"
USER="${2:-ubuntu}"
KEY="${3:-$HOME/.ssh/id_ed25519_personal}"
REMOTE="${USER}@${IP}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new"
SCP="scp -i $KEY -o StrictHostKeyChecking=accept-new"
RSYNC="rsync -az --delete -e 'ssh -i $KEY -o StrictHostKeyChecking=accept-new' \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='ui/admin/dist' \
  --exclude='ui/admin/coverage' \
  --exclude='ui/admin/node_modules' \
  --exclude='docs/site' \
  --exclude='terraform/.terraform' \
  --exclude='*.bak.*' \
  --exclude='config/.env'"

echo "▸ Pre-flight: confirm SSH works"
$SSH $REMOTE "echo connected as \$(whoami) on \$(hostname); uname -m"

echo
echo "▸ Step 1/6: install docker + compose v2 + git + make on the VM (idempotent)"
$SSH $REMOTE 'set -e
  if ! command -v docker >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      git make rsync curl ca-certificates iptables-persistent >/dev/null
    # Docker Engine + compose-plugin from Docker official install script
    # (ubuntu repos do not have docker-compose-plugin; only docker.io which is engine only)
    curl -fsSL https://get.docker.com | sudo sh >/dev/null
    sudo systemctl enable --now docker
    sudo usermod -aG docker $(whoami)
    echo "  installed: $(sudo docker --version)"
    echo "  installed: $(sudo docker compose version)"
  else
    echo "  already installed: $(docker --version)"
    if ! docker compose version >/dev/null 2>&1; then
      echo "  compose plugin missing — installing"
      curl -fsSL https://get.docker.com | sudo sh >/dev/null
    fi
  fi
'

echo
echo "▸ Step 2/6: open ports 80/443 on the OS firewall (OCI security list still needed in console)"
$SSH $REMOTE 'set -e
  for port in 80 443; do
    if ! sudo iptables -C INPUT -m state --state NEW -p tcp --dport $port -j ACCEPT 2>/dev/null; then
      sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport $port -j ACCEPT
      echo "  opened :$port"
    else
      echo "  :$port already open"
    fi
  done
  sudo netfilter-persistent save >/dev/null 2>&1 || sudo iptables-save | sudo tee /etc/iptables/rules.v4 >/dev/null
'

echo
echo "▸ Step 3/6: rsync code (excludes secrets, build artifacts, caches)"
$SSH $REMOTE 'mkdir -p ~/scutum'
eval "$RSYNC ./ $REMOTE:~/scutum/"

echo
echo "▸ Step 4/6: push config/.env (only file we treat as a secret)"
if [ ! -f config/.env ]; then
  echo "  ✗ config/.env not found — copy from .env.example and configure first"
  exit 1
fi
$SCP config/.env $REMOTE:~/scutum/config/.env
$SSH $REMOTE 'chmod 600 ~/scutum/config/.env'

echo
echo "▸ Step 5/6: build + start scutum.dev marketing stack (postgres, admin-api, landing-backend, landing-ui, docs-site)"
$SSH $REMOTE 'cd ~/scutum && \
  sudo -E docker compose --env-file config/.env up -d --build \
    postgres admin-api landing-backend landing-ui docs-site 2>&1 | tail -10'

echo
echo "▸ Step 6/6: health check"
sleep 8
echo
$SSH $REMOTE 'cd ~/scutum && sudo docker compose --env-file config/.env ps'
echo
$SSH $REMOTE 'curl -s http://localhost:9999/ -o /dev/null -w "  landing-ui:       HTTP %{http_code}\n"'
$SSH $REMOTE 'curl -s http://localhost:8086/health -o /dev/null -w "  admin-api:        HTTP %{http_code}\n"'
$SSH $REMOTE 'curl -s http://localhost:8093/health -o /dev/null -w "  landing-backend:  HTTP %{http_code}\n"'

echo
echo "▸ Done. Test from your laptop:"
echo "    curl http://${IP}/"
echo "  (won't work yet if OCI VCN security list still blocks :80 — open it in the console)"
echo
echo "  Once you add the Cloudflare A record for scutum.dev → ${IP} (orange-cloud proxy on),"
echo "  https://scutum.dev/ resolves through Cloudflare TLS."
