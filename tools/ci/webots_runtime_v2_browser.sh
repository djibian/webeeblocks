#!/usr/bin/env bash
set -eu
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/runtime-v2-webots}"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED args=' >> "$artifact_dir/browser-launch.log"
printf '%q ' "$@" >> "$artifact_dir/browser-launch.log"
printf '\n' >> "$artifact_dir/browser-launch.log"
# One isolated CI browser profile reused by new Robot Windows after world reload.
exec /usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir=/tmp/webeeblocks-ci-persistent-robot-window \
  --enable-logging=stderr \
  --v=1 \
  "$@"
