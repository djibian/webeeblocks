#!/usr/bin/env bash
set -eu
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/runtime-v2-student-ui}"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED args=' >> "$artifact_dir/browser-launch.log"
for arg in "$@"; do printf '%q ' "$arg" >> "$artifact_dir/browser-launch.log"; done
printf '\n' >> "$artifact_dir/browser-launch.log"
exec /usr/bin/google-chrome \
  --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --disable-background-networking --no-first-run --no-default-browser-check \
  --window-size=1366,768 --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 --remote-allow-origins='*' "$@"
