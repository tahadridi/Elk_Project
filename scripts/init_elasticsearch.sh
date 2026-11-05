#!/usr/bin/env bash
set -euo pipefail

ES=${ES_URL:-http://localhost:9200}
DIR="$(cd "$(dirname "$0")/.." && pwd)/infra/elasticsearch"

echo "Waiting for Elasticsearch at $ES ..."
for _ in $(seq 1 60); do
  if curl -fsS "$ES/_cluster/health?wait_for_status=yellow&timeout=2s" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS "$ES/_cluster/health" >/dev/null 2>&1; then
  echo "ERROR: Elasticsearch is not reachable at $ES" >&2
  exit 1
fi

for template in logs-security logs-parse-errors; do
  echo "Installing index template $template ..."
  curl -fsS -X PUT "$ES/_index_template/$template" \
    -H 'Content-Type: application/json' \
    --data-binary @"$DIR/$template-template.json"
  echo
done

echo "Done."
