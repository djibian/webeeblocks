#!/usr/bin/env bash
set -eu
mkdir -p /workspace/ci-artifacts/crazyflie-runtime-wwi
printf 'BROWSER_LAUNCHED args=' >> /workspace/ci-artifacts/crazyflie-runtime-wwi/browser-launch.log
printf '%q ' "$@" >> /workspace/ci-artifacts/crazyflie-runtime-wwi/browser-launch.log
printf '\n' >> /workspace/ci-artifacts/crazyflie-runtime-wwi/browser-launch.log
exec /usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  --enable-logging=stderr \
  --v=1 \
  "$@"
