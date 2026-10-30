#!/usr/bin/env bash
set -eu
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/runtime-v2-webots}"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED epoch_ns=%s pid=%s ppid=%s args=' "$(date +%s%N)" "$BASHPID" "$PPID" >> "$artifact_dir/browser-launch.log"
printf '%q ' "$@" >> "$artifact_dir/browser-launch.log"
printf '\n' >> "$artifact_dir/browser-launch.log"
# Passive diagnosis only: do not change Chromium launch arguments or profile.
{
  printf 'LAUNCH_SNAPSHOT epoch_ns=%s pid=%s ppid=%s\n' "$(date +%s%N)" "$BASHPID" "$PPID"
  if [ -L /tmp/webeeblocks-ci-persistent-robot-window/SingletonLock ]; then
    printf 'SINGLETON_LOCK=%s\n' "$(readlink /tmp/webeeblocks-ci-persistent-robot-window/SingletonLock)"
  else
    printf 'SINGLETON_LOCK=absent\n'
  fi
  ps -eo pid,ppid,stat,etime,args | grep -E '[g]oogle-chrome|[c]hrome --' | head -n 40 || true
} >> "$artifact_dir/browser-process-snapshots.log" 2>&1
# CI-only controlled fault: same CDP remedy as guard_negative_browser.sh.
# The default classroom/native launcher path below remains byte-for-byte
# equivalent unless WEBEEBLOCKS_CI_CHROME_HANDOFF_MODE=cdp_rescue.
if [ "${WEBEEBLOCKS_CI_CHROME_HANDOFF_MODE:-}" = cdp_rescue ]; then
  counter="$artifact_dir/browser-launch-count"
  n=0; if [ -f "$counter" ]; then n=$(cat "$counter"); fi
  n=$((n+1)); printf '%s\n' "$n" > "$counter"
  if [ "$n" -eq 2 ]; then
    profile=/tmp/webeeblocks-ci-persistent-robot-window
    lock_target=""
    if [ -L "$profile/SingletonLock" ]; then lock_target=$(readlink "$profile/SingletonLock"); fi
    old_pid="${lock_target##*-}"
    if ! [[ "$old_pid" =~ ^[0-9]+$ ]] || ! kill -0 "$old_pid" 2>/dev/null; then
      echo 'FAULT_PRECONDITION_MISSING' >> "$artifact_dir/browser-handoff.log"
      exit 69
    fi
    printf 'STOP_OLD_CHROME epoch_ns=%s pid=%s\n' "$(date +%s%N)" "$old_pid" >> "$artifact_dir/browser-handoff.log"
    kill -STOP "$old_pid"
    (sleep 7; kill -CONT "$old_pid" 2>/dev/null || true;
      printf 'CONT_OLD_CHROME epoch_ns=%s pid=%s\n' "$(date +%s%N)" "$old_pid" >> "$artifact_dir/browser-handoff.log") &
    python3 /workspace/tools/ci/probe_browser_document.py "$artifact_dir/browser-document-probe.jsonl" &
  fi
  # Same one Chrome invocation and profile as original, except CDP experiment.
  set +e
  /usr/bin/google-chrome --headless=new --no-sandbox --disable-gpu \
    --disable-dev-shm-usage --disable-background-networking --no-first-run \
    --no-default-browser-check \
    --user-data-dir=/tmp/webeeblocks-ci-persistent-robot-window \
    --remote-debugging-port=9222 --enable-logging=stderr --v=1 \
    "$@" 2>> "$artifact_dir/chrome-stderr.log"
  code=$?
  printf 'CHROME_LAUNCH_RETURNED count=%s exit=%s epoch_ns=%s\n' "$n" "$code" "$(date +%s%N)" >> "$artifact_dir/browser-handoff.log"
  if [ "$n" -eq 2 ] && [ "$code" -eq 21 ]; then
    python3 /workspace/tools/ci/cdp_reopen_once.py "$artifact_dir/cdp-rescue.jsonl" "$1" >> "$artifact_dir/browser-handoff.log" 2>&1
    exit "$?"
  fi
  exit "$code"
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
  --user-data-dir=/tmp/webeeblocks-ci-persistent-robot-window \
  --enable-logging=stderr \
  --v=1 \
  "$@" 2>> "$artifact_dir/chrome-stderr.log"
