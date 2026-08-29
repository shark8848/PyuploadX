#!/usr/bin/env bash
# Build and start the full stack, provisioning a portal API token.
#
# - Set PORTAL_API_TOKEN for a static token; otherwise a random token is
#   generated on every start ("dynamic token").
# - The token is injected by the portal nginx as X-API-Key and registered in
#   UPLOAD_API_KEYS so the API accepts it; the browser never sees it.
# - Extra compose files can be appended, e.g.:
#     scripts/start-stack.sh -f /tmp/pg-proxy.yml
set -euo pipefail

cd "$(dirname "$0")/.."

TOKEN="${PORTAL_API_TOKEN:-}"
if [ -z "$TOKEN" ]; then
  TOKEN="$(openssl rand -hex 24 2>/dev/null || head -c 48 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi
export PORTAL_API_TOKEN="$TOKEN"

export UPLOAD_API_KEYS="$(
  TOKEN="$TOKEN" KEYS="${UPLOAD_API_KEYS:-[\"dev-key\"]}" python3 - <<'PY'
import json
import os

data = json.loads(os.environ["KEYS"])
token = os.environ["TOKEN"]
if isinstance(data, dict):
    data.setdefault("portal/portal", [])
    if token not in data["portal/portal"]:
        data["portal/portal"].append(token)
else:
    if token not in data:
        data.append(token)
print(json.dumps(data))
PY
)"

echo "portal token: ${TOKEN:0:8}… (set PORTAL_API_TOKEN for a static token)" >&2
exec docker compose -f docker-compose.yml "$@" up -d --build
