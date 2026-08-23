#!/usr/bin/env bash
set -eu
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/runtime-v2-keyboard-a11y}"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED args=' >> "$artifact_dir/browser-launch.log"
printf '%q ' "$@" >> "$artifact_dir/browser-launch.log"
printf '\n' >> "$artifact_dir/browser-launch.log"
exec /usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --remote-allow-origins='*' \
  --enable-logging=stderr \
  --v=1 \
  "$@"
