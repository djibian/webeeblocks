#!/usr/bin/env bash
set -eu
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/runtime-v2-webots}"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED epoch_ns=%s pid=%s ppid=%s mode=%s args=' "$(date +%s%N)" "$" "$PPID" "${WEBEEBLOCKS_REOPEN_MODE:-new_window}" >> "$artifact_dir/browser-launch.log"
printf '%q ' "$@" >> "$artifact_dir/browser-launch.log"
printf '\n' >> "$artifact_dir/browser-launch.log"
{
  printf 'LAUNCH_SNAPSHOT epoch_ns=%s pid=%s mode=%s\n' "$(date +%s%N)" "$" "${WEBEEBLOCKS_REOPEN_MODE:-new_window}"
  if [ -L /tmp/webeeblocks-ci-persistent-robot-window/SingletonLock ]; then
    printf 'SINGLETON_LOCK=%s\n' "$(readlink /tmp/webeeblocks-ci-persistent-robot-window/SingletonLock)"
  else
    printf 'SINGLETON_LOCK=absent\n'
  fi
  ps -eo pid,ppid,stat,etime,args | grep -E '[g]oogle-chrome|[c]hrome --' | head -n 40 || true
} >> "$artifact_dir/browser-process-snapshots.log" 2>&1
# Webots R2025a may resend precisely the same URL after world_reload.
# Chrome's singleton may reactivate an old document instead of navigating.
# Preserve the profile (and Blockly checkpoint), but demand a NEW document.
# Control arm is limited to research CI; the candidate is the default.
chrome_window_args=(--new-window)
if [ "${WEBEEBLOCKS_REOPEN_MODE:-new_window}" = control ]; then chrome_window_args=(); fi
# One isolated CI browser profile reused by new Robot Windows after world reload.
exec /usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  "${chrome_window_args[@]}" \
  --user-data-dir=/tmp/webeeblocks-ci-persistent-robot-window \
  --enable-logging=stderr \
  --v=1 \
  "$@" 2>> "$artifact_dir/chrome-stderr.log"
