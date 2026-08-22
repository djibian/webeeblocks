#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/ci-artifacts/modern-blockly
printf 'BROWSER_LAUNCHED args=' >> /workspace/ci-artifacts/modern-blockly/browser-launch.log
printf '%q ' "$@" >> /workspace/ci-artifacts/modern-blockly/browser-launch.log
printf '\n' >> /workspace/ci-artifacts/modern-blockly/browser-launch.log

exec /usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  --no-proxy-server \
  --host-resolver-rules='MAP * 0.0.0.0, EXCLUDE localhost, EXCLUDE 127.0.0.1' \
  --enable-logging=stderr \
  --v=1 \
  "$@"
