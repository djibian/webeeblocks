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
# Research candidate: avoid forwarding a URL to a Chromium process that is
# leaving its final Robot Window. The native Webots browser launcher is
# detached, so a successful QProcess start does NOT mean a live HTML document.
# This conditional barrier is bounded and does not delete a profile or signal
# the existing process. A continuously active profile remains reusable.
if [ "${WEBEEBLOCKS_REOPEN_MODE:-new_window}" = stable_exit ]; then
  lock=/tmp/webeeblocks-ci-persistent-robot-window/SingletonLock
  old_pid=""
  if [ -L "$lock" ]; then
    link=$(readlink "$lock" || true)
    old_pid="${link##*-}"
  fi
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    waited=0
    start_ns=$(date +%s%N)
    for _ in $(seq 1 150); do
      state=$(ps -p "$old_pid" -o stat= 2>/dev/null || true)
      if [ -z "$state" ] || [[ "$state" = Z* ]]; then break; fi
      sleep 0.1
      waited=$((waited + 1))
    done
    end_ns=$(date +%s%N)
    state=$(ps -p "$old_pid" -o stat= 2>/dev/null || true)
    printf 'BROWSER_EXIT_BARRIER old_pid=%s elapsed_ms=%s end_state=%s decision=%s\n' \
      "$old_pid" "$(( (end_ns - start_ns)/1000000 ))" "${state:-absent}" \
      "$([ -z "$state" ] || [[ "$state" = Z* ]] && echo replaced_after_exit || echo same_live_instance_new_window)" \
      >> "$artifact_dir/browser-launch.log"
  fi
fi
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
