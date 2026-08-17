#!/usr/bin/env bash
set -eu

mkdir -p /workspace/ci-artifacts
printf 'BROWSER_LAUNCHED args=' >> /workspace/ci-artifacts/browser-launch.log
printf '%q ' "$@" >> /workspace/ci-artifacts/browser-launch.log
printf '\n' >> /workspace/ci-artifacts/browser-launch.log

exec /usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  "$@"
