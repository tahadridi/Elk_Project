#!/usr/bin/env bash
set -euo pipefail

KIBANA=${KIBANA_URL:-http://localhost:5601}
EXPORT="$(dirname "$0")/../infra/kibana/exports/security-overview.ndjson"

echo "Waiting for Kibana at $KIBANA ..."
for _ in $(seq 1 90); do
  if curl -fsS "$KIBANA/api/status" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS "$KIBANA/api/status" >/dev/null 2>&1; then
  echo "ERROR: Kibana is not reachable at $KIBANA" >&2
  exit 1
fi

if [ ! -f "$EXPORT" ]; then
  echo "ERROR: saved objects export not found: $EXPORT" >&2
  exit 1
fi

echo "Importing Kibana saved objects from $EXPORT ..."
curl -fsS -X POST "$KIBANA/api/saved_objects/_import?overwrite=true" \
  -H 'kbn-xsrf: true' \
  --form file=@"$EXPORT"

echo
echo "Done. Open $KIBANA and go to Dashboards -> Security Overview."
