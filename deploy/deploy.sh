#!/usr/bin/env bash
# Rebuild the image and swap the container. Assumes the tree is already
# up to date at $ROOT (rsync/tar/scp/git — this script does not care how
# it got there). Fails loud on any step.
set -euo pipefail

ROOT="${PAPERTRAIL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

echo "==> building image"
docker compose build

echo "==> restarting container"
docker compose up -d --remove-orphans

echo "==> waiting for health"
for i in $(seq 1 60); do
  hz=$(curl -fsS http://127.0.0.1:8790/healthz 2>/dev/null || true)
  st=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8790/api/state 2>/dev/null || true)
  if [ -n "$hz" ] && [ "$st" = "200" ]; then
    echo "  /healthz    $hz"
    echo "  /api/state  $st"
    exit 0
  fi
  sleep 1
done
echo "container never went healthy — logs:"
docker compose logs --tail=40 papertrail
exit 1
