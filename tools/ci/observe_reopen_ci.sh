#!/usr/bin/env bash
# CI-only bounded native process observer. NEVER replaces physical acceptance.
# The unmodified downstream Python native oracle must verify every event.
set -euo pipefail
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:?}"
mkdir -p "$artifact_dir"
events="$artifact_dir/browser-events.jsonl"
native_log="$artifact_dir/native-session.log"
timeout -k 5s 420s xvfb-run -a webots --stdout --stderr --batch --mode=realtime \
  /workspace/worlds/crazyflie_runtime_v2.wbt > "$native_log" 2>&1 &
sim_pid=$!
last_count=0
second_launch_at=0
finished=""
for _ in $(seq 1 1000); do
  if ! kill -0 "$sim_pid" 2>/dev/null; then
    finished=process_exited
    break
  fi
  if [ -s "$events" ] && grep -q '"event": "WORLD_RECOVERY_RERUN"' "$events"; then
    finished=native_rerun_observed
    break
  fi
  count=0
  if [ -f "$artifact_dir/browser-launch.log" ]; then
    count=$(grep -c '^BROWSER_LAUNCHED' "$artifact_dir/browser-launch.log" || true)
  fi
  if [ "$count" -ge 2 ] && [ "$last_count" -lt 2 ]; then
    second_launch_at=$(date +%s)
    printf 'REOPEN_OBSERVER second launch at epoch=%s\n' "$second_launch_at"
  fi
  last_count="$count"
  if [ "$second_launch_at" -gt 0 ] && [ "$(( $(date +%s) - second_launch_at ))" -gt 75 ]; then
    # Not an implicit success or a change to production timeouts.
    # This is a diagnostic fail after native relaunch, not proof of open.
    finished=second_document_absent_or_not_ready_within_diagnostic_budget
    break
  fi
  sleep 0.25
done
if [ -z "$finished" ]; then finished=observer_budget_exhausted; fi
printf 'REOPEN_OBSERVER outcome=%s\n' "$finished"
if [ "$finished" != process_exited ]; then
  # Capture process information *before* stopping the disposable test Webots.
  ps -eo pid,ppid,stat,etime,args | grep -E '[g]oogle-chrome|[c]hrome --|[w]ebots' \
    > "$artifact_dir/process-final-snapshot.log" || true
  kill -TERM "$sim_pid" 2>/dev/null || true
fi
set +e
wait "$sim_pid"
native_exit=$?
set -e
printf '%s\n' "$native_exit" > "$artifact_dir/native-process-exit.txt"
cat "$native_log"
if [ "$finished" = native_rerun_observed ]; then
  # This stops the *CI harness* after completion; the independent Python
  # assertions below still decide whether all physical and project oracles pass.
  exit 0
fi
echo "REOPEN_OBSERVER_FAIL=$finished native_exit=$native_exit" >&2
exit 124
