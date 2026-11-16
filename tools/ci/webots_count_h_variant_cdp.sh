#!/usr/bin/env bash
# CI-only CDP Chrome browser, never installed in the student Windows product.
set -euo pipefail
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/progression-count-h-real-variant}"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED args=' >> "$artifact_dir/browser-launch.log"
printf '%q ' "$@" >> "$artifact_dir/browser-launch.log"
printf '\n' >> "$artifact_dir/browser-launch.log"
exec /usr/bin/google-chrome \
  --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --disable-background-networking --no-first-run --no-default-browser-check \
  --remote-debugging-port=9222 --remote-allow-origins='*' \
  --user-data-dir=/tmp/webeeblocks-a6-cdp-variant \
  --enable-logging=stderr --v=1 "$@"
