#!/usr/bin/env bash
set -eu
: "${WEBEEBLOCKS_GUARD_FAULT_MODE:?}"
: "${WEBEEBLOCKS_CI_ARTIFACT_DIR:=/workspace/ci-artifacts/guard-negative}"
mkdir -p "$WEBEEBLOCKS_CI_ARTIFACT_DIR"
count_file="$WEBEEBLOCKS_CI_ARTIFACT_DIR/browser-launch-count"
count=0
if [ -f "$count_file" ]; then count=$(cat "$count_file"); fi
count=$((count + 1))
printf '%s\n' "$count" > "$count_file"
profile="/tmp/webeeblocks-native-guard-profile"
if [ "$WEBEEBLOCKS_GUARD_FAULT_MODE" = lost_profile ] && [ "$count" -gt 1 ]; then
  profile="/tmp/webeeblocks-native-guard-new-profile-$count"
fi
printf 'NATIVE_GUARD_BROWSER_LAUNCH mode=%s count=%s profile=%s args=' "$WEBEEBLOCKS_GUARD_FAULT_MODE" "$count" "$profile" >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/browser-launch.log"
printf '%q ' "$@" >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/browser-launch.log"
printf '\n' >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/browser-launch.log"
# Passive process/profile evidence for intermittent Robot Window non-reopen.
{
  printf 'LAUNCH_SNAPSHOT epoch_ns=%s pid=%s ppid=%s mode=%s count=%s\n' "$(date +%s%N)" "$BASHPID" "$PPID" "$WEBEEBLOCKS_GUARD_FAULT_MODE" "$count"
  if [ -L "$profile/SingletonLock" ]; then
    printf 'SINGLETON_LOCK=%s\n' "$(readlink "$profile/SingletonLock")"
  else
    printf 'SINGLETON_LOCK=absent\n'
  fi
  ps -eo pid,ppid,stat,etime,args | grep -E '[g]oogle-chrome|[c]hrome --' | head -n 40 || true
} >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/browser-process-snapshots.log" 2>&1
# Research-only reproducible ProcessSingleton teardown race. The original
# negative modes continue to use the unmodified launch path.
if [ "${WEBEEBLOCKS_CI_CHROME_HANDOFF_MODE:-}" != "" ] && [ "$count" -eq 2 ]; then
  lock_target=""
  if [ -L "$profile/SingletonLock" ]; then
    lock_target=$(readlink "$profile/SingletonLock")
  fi
  old_pid="${lock_target##*-}"
  if ! [[ "$old_pid" =~ ^[0-9]+$ ]] || ! kill -0 "$old_pid" 2>/dev/null; then
    echo "FAULT_PRECONDITION_MISSING old_pid=$old_pid lock=$lock_target" >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/handshake.log"
    exit 69
  fi
  printf 'OLD_CHROME_PID=%s lock=%s mode=%s epoch_ns=%s\n' "$old_pid" "$lock_target" "$WEBEEBLOCKS_CI_CHROME_HANDOFF_MODE" "$(date +%s%N)" >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/handshake.log"
  # Freeze the old process exactly at the already-observed overlap.
  # A guaranteed bounded SIGCONT is scheduled before testing a new launch;
  # never send SIGTERM/SIGKILL and never unlink a profile file.
  kill -STOP "$old_pid"
  (sleep 7; kill -CONT "$old_pid" 2>/dev/null || true;
    printf 'OLD_CHROME_RESUMED epoch_ns=%s\n' "$(date +%s%N)" >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/handshake.log") &
  if [ "$WEBEEBLOCKS_CI_CHROME_HANDOFF_MODE" = after_exit ]; then
    # Instead of forwarding to an owner that cannot accept a notification,
    # require observable termination (bounded, fail closed on uncertainty).
    settled=0
    for i in $(seq 1 150); do
      state=$(ps -p "$old_pid" -o stat= 2>/dev/null || true)
      if [ -z "$state" ] || [[ "$state" = Z* ]]; then
        settled=1
        printf 'OLD_CHROME_EXIT_OBSERVED epoch_ns=%s iteration=%s\n' "$(date +%s%N)" "$i" >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/handshake.log"
        break
      fi
      sleep .1
    done
    if [ "$settled" != 1 ]; then
      echo 'OLD_CHROME_STILL_LIVE_AFTER_BOUNDED_WAIT' >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/handshake.log"
      exit 70
    fi
  fi
fi
# CDP is research-only and allows independent document-target confirmation.
chrome_args=()
if [ -n "${WEBEEBLOCKS_CI_CHROME_HANDOFF_MODE:-}" ]; then
  chrome_args=(--remote-debugging-port=9222)
  if [ "$count" -eq 2 ]; then
    python3 /workspace/tools/ci/probe_browser_document.py \
      "$WEBEEBLOCKS_CI_ARTIFACT_DIR/browser-document-probe.jsonl" &
  fi
fi
set +e
/usr/bin/google-chrome --headless=new --no-sandbox --disable-gpu \
  "${chrome_args[@]}" \
  --disable-dev-shm-usage --disable-background-networking --no-first-run \
  --no-default-browser-check --user-data-dir="$profile" "$@" 2>> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/chrome-stderr.log"
exit_code=$?
printf 'CHROME_LAUNCH_RETURNED epoch_ns=%s count=%s exit=%s\n' "$(date +%s%N)" "$count" "$exit_code" >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/handshake.log"
if [ "$count" -eq 2 ] && [ "${WEBEEBLOCKS_CI_CHROME_HANDOFF_MODE:-}" = cdp_rescue ] && [ "$exit_code" -eq 21 ]; then
  # Explicitly open a document in the SAME incumbent Chromium profile.
  # This is a single conditional attempt: no re-launch and no profile purge.
  python3 /workspace/tools/ci/cdp_reopen_once.py \
    "$WEBEEBLOCKS_CI_ARTIFACT_DIR/cdp-rescue.jsonl" "$1"
  exit "$?"
fi
exit "$exit_code"
