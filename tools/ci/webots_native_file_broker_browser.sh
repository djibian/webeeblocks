#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$ROOT/ci-artifacts/runtime-v2-desktop-sdk-file-broker"
printf 'BROWSER_LAUNCHED args=' >> "$ROOT/ci-artifacts/runtime-v2-desktop-sdk-file-broker/browser-launch.log"
printf '%q ' "$@" >> "$ROOT/ci-artifacts/runtime-v2-desktop-sdk-file-broker/browser-launch.log"
printf '\n' >> "$ROOT/ci-artifacts/runtime-v2-desktop-sdk-file-broker/browser-launch.log"
CHROME="$(command -v google-chrome || command -v google-chrome-stable || true)"
test -n "$CHROME"
exec "$CHROME" --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage   --disable-background-networking --no-first-run --no-default-browser-check "$@"
