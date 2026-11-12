#!/usr/bin/env bash
set -euo pipefail

: "${MAXMIND_LICENSE_KEY:?Set MAXMIND_LICENSE_KEY first}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/infra/geoip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DEST"

echo "Downloading GeoLite2-Country ..."
curl -fsSL \
  "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz" \
  -o "$TMP/GeoLite2-Country.tar.gz"

tar -xzf "$TMP/GeoLite2-Country.tar.gz" -C "$TMP"
cp "$TMP"/GeoLite2-Country_*/GeoLite2-Country.mmdb "$DEST/GeoLite2-Country.mmdb"

echo "Installed $DEST/GeoLite2-Country.mmdb"
