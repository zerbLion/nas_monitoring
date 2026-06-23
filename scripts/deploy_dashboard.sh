#!/bin/bash
# Deploy the live dashboard + updated collector to the NAS.
# Run this from a machine that has the `ssh nas` alias configured (key auth).
#
#   bash scripts/deploy_dashboard.sh
#
# It is idempotent: re-run any time after `git pull`.
set -euo pipefail

SSH_HOST="${SSH_HOST:-nas}"                                   # override: SSH_HOST=user@100.105.65.9
NAS_DIR="/volume1/docker/nas_monitoring"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> repo:   $REPO_DIR"
echo "==> target: $SSH_HOST:$NAS_DIR"

echo "==> 1/3 copying dashboard + collector"
scp "$REPO_DIR/web/index.html"           "$SSH_HOST:$NAS_DIR/web/index.html"
scp "$REPO_DIR/scripts/collect_temps.py" "$SSH_HOST:$NAS_DIR/scripts/collect_temps.py"

echo "==> 2/3 re-collecting once (writes temps.json with the new model field)"
ssh "$SSH_HOST" "python3 $NAS_DIR/scripts/collect_temps.py > $NAS_DIR/web/temps.json"

echo "==> 3/3 cross-checking values"
ssh "$SSH_HOST" "python3 $NAS_DIR/scripts/verify.py" || echo "(verify reported a mismatch — review above)"

echo
echo "Done. Open the dashboard:"
echo "  LAN:       http://192.168.1.100:8787/"
echo "  Tailscale: http://100.105.65.9:8787/"
echo "nginx is a read-only mount — no container restart needed, just refresh."
