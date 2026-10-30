#!/usr/bin/env bash
set -eu
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/runtime-v2-webots}"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED epoch_ns=%s pid=%s ppid=%s args=' "$(date +%s%N)" "$BASHPID" "$PPID" >> "$artifact_dir/browser-launch.log"
printf '%q ' "$@" >> "$artifact_dir/browser-launch.log"
printf '\n' >> "$artifact_dir/browser-launch.log"
# Passive diagnosis only: do not change Chromium launch arguments or profile.
{
  printf 'LAUNCH_SNAPSHOT epoch_ns=%s pid=%s ppid=%s\\n' "$(date +%s%N)" "$BASHPID" "$PPID"
  if [ -L /tmp/webeeblocks-ci-persistent-robot-window/SingletonLock ]; then
    printf 'SINGLETON_LOCK=%s\\n' "$(readlink /tmp/webeeblocks-ci-persistent-robot-window/SingletonLock)"
  else
    printf 'SINGLETON_LOCK=absent\\n'
  fi
  ps -eo pid,ppid,stat,etime,args | grep -E '[g]oogle-chrome|[c]hrome --' | head -n 40 || true
} >> "$artifact_dir/browser-process-snapshots.log" 2>&1
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
  "$@" 2>> "$artifact_dir/chrome-stderr.log"
