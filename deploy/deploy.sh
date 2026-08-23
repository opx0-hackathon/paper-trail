#!/usr/bin/env bash
# Redeploy Paper Trail. Pulls, rebuilds the image, restarts the container.
# Idempotent. Fails loud on any step.
set -euo pipefail

ROOT="${PAPERTRAIL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
BRANCH="${PAPERTRAIL_BRANCH:-main}"

cd "$ROOT"

echo "==> pulling $BRANCH"
git fetch --prune origin
git reset --hard "origin/$BRANCH"

echo "==> building image"
docker compose build

echo "==> restarting container"
docker compose up -d --remove-orphans

echo "==> waiting for health"
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8790/healthz >/dev/null 2>&1; then
    curl -fsS http://127.0.0.1:8790/healthz && echo
    curl -fsS -o /dev/null -w "==> /api/state %{http_code}\n" http://127.0.0.1:8790/api/state
    exit 0
  fi
  sleep 1
done
echo "container never went healthy — logs:"
docker compose logs --tail=40 papertrail
exit 1
