#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
TOOLS_DIR="${WEBEEBLOCKS_TLA_TOOLS_DIR:-$ROOT/.build/tools}"
JAR="${TLA2TOOLS_JAR:-$TOOLS_DIR/tla2tools.jar}"

TLA_VERSION="1.7.4"
TLA_URL="https://github.com/tlaplus/tlaplus/releases/download/v${TLA_VERSION}/tla2tools.jar"
TLA_SHA256="936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"

if [[ ! -f "$JAR" ]]; then
  mkdir -p "$(dirname "$JAR")"
  curl --fail --location --silent --show-error "$TLA_URL" --output "$JAR"
fi

printf '%s  %s\n' "$TLA_SHA256" "$JAR" | sha256sum --check -

if git -C "$ROOT" rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "Repository HEAD: $(git -C "$ROOT" rev-parse HEAD)"
fi

cd "$HERE"

java -cp "$JAR" tla2sany.SANY WebeeBlocksV5.tla WebeeBlocksV5_MC.tla

default_configs=(
  WebeeBlocksV5_Ordering.cfg
  WebeeBlocksV5_EpochTerminal.cfg
  WebeeBlocksV5_EpochRepair.cfg
  WebeeBlocksV5_Duplicate.cfg
  WebeeBlocksV5_PendingHead.cfg
  WebeeBlocksV5_SharedHead.cfg
  WebeeBlocksV5_LateRefutation.cfg
  WebeeBlocksV5_Checkpoint.cfg
  WebeeBlocksV5_Migration.cfg
)

if (( "$#" > 0 )); then
  configs=("$@")
else
  configs=("${default_configs[@]}")
fi

for cfg in "${configs[@]}"; do
  echo
  echo "=== TLC: $cfg ==="
  java -cp "$JAR" tlc2.TLC -workers 1 -config "$cfg" WebeeBlocksV5_MC.tla
done
