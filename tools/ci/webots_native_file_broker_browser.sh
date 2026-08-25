#!/usr/bin/env bash
set -eu
mkdir -p /workspace/ci-artifacts/runtime-v2-native-file-broker
printf 'BROWSER_LAUNCHED args=' >> /workspace/ci-artifacts/runtime-v2-native-file-broker/browser-launch.log
printf '%q ' "$@" >> /workspace/ci-artifacts/runtime-v2-native-file-broker/browser-launch.log
printf '\n' >> /workspace/ci-artifacts/runtime-v2-native-file-broker/browser-launch.log
exec /usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  "$@"
