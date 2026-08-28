#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BLOCKLY_DIR="$ROOT_DIR/plugins/robot_windows/blockly_v2"

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: Node.js >= 22 is required to prepare Runtime v2 Blockly assets." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm is required to prepare Runtime v2 Blockly assets." >&2
  exit 1
fi

node_major="$(node -p 'Number(process.versions.node.split(".")[0])')"
if [ "$node_major" -lt 22 ]; then
  echo "ERROR: Node.js >= 22 is required; found $(node --version)." >&2
  exit 1
fi

cd "$BLOCKLY_DIR"
npm install --ignore-scripts --no-audit --no-fund
npm run prepare:blockly

test "$(cat vendor/VERSION)" = "13.2.1"
test -s vendor/blockly_compressed.js
test -s vendor/blocks_compressed.js
test -s vendor/msg/fr.js
test -d vendor/media

echo "Runtime v2 Blockly assets ready: blockly@13.2.1"
