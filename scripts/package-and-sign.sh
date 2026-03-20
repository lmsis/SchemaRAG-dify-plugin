#!/usr/bin/env bash
# Package this plugin and sign the .difypkg (local release / same flow as CI).
#
# 1) Download the CLI for your OS (use a recent release, e.g. 0.5.x — old 0.0.6 has no `signature`):
#    https://github.com/langgenius/dify-plugin-daemon/releases
# 2) Generate keys once:  $DIFY_PLUGIN_CLI signature generate -f mykeys
#
# Usage:
#   export DIFY_PLUGIN_CLI=/path/to/dify-plugin-darwin-arm64   # or linux-amd64
#   ./scripts/package-and-sign.sh /path/to/mykeys.private.pem
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

KEY="${1:?Usage: $0 /path/to/private.pem}"

if [ ! -f "$KEY" ]; then
  echo "error: private key not found: $KEY" >&2
  exit 1
fi

CLI="${DIFY_PLUGIN_CLI:-}"
if [ -z "$CLI" ]; then
  echo "error: set DIFY_PLUGIN_CLI to the full path of the dify-plugin binary" >&2
  echo "  e.g. export DIFY_PLUGIN_CLI=\$HOME/bin/dify-plugin-darwin-arm64" >&2
  exit 1
fi
if [ ! -f "$CLI" ] || [ ! -x "$CLI" ]; then
  echo "error: DIFY_PLUGIN_CLI must be an executable file: $CLI" >&2
  exit 1
fi

PLUGIN_NAME="$(grep '^name:' manifest.yaml | head -1 | awk '{print $2}')"
VERSION="$(grep '^version:' manifest.yaml | head -1 | awk '{print $2}')"
PKG="${PLUGIN_NAME}-${VERSION}.difypkg"

echo "==> package -> $PKG"
"$CLI" plugin package . -o "$PKG"

echo "==> sign"
"$CLI" signature sign "$PKG" -p "$KEY"
SIGNED="${PKG%.difypkg}.signed.difypkg"
mv -f "$SIGNED" "$PKG"
echo "==> done: $PKG (signed)"
