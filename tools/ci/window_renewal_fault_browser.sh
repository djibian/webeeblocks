#!/usr/bin/env bash
# Disposable native R2025a test only. No Chromium flag changes in the product.
# Deterministically recreate the ProcessSingleton failure on the second
# Webots browser invocation while the original browser owns Blockly storage.
set -euo pipefail
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:?}"
mkdir -p "$artifact_dir"
profile=/tmp/webeeblocks-ci-persistent-robot-window
counter="$artifact_dir/browser-launch-count"
count=0
if [ -f "$counter" ]; then count=$(cat "$counter"); fi
count=$((count+1))
printf '%s\n' "$count" > "$counter"
printf 'BROWSER_LAUNCHED epoch_ns=%s pid=%s count=%s args=' "$(date +%s%N)" "$BASHPID" "$count" >> "$artifact_dir/browser-launch.log"
printf '%q ' "$@" >> "$artifact_dir/browser-launch.log"
printf '\n' >> "$artifact_dir/browser-launch.log"
if [ "$count" -eq 2 ]; then
  lock_target=""
  if [ -L "$profile/SingletonLock" ]; then lock_target=$(readlink "$profile/SingletonLock"); fi
  owner_pid="${lock_target##*-}"
  if ! [[ "$owner_pid" =~ ^[0-9]+$ ]] || ! kill -0 "$owner_pid" 2>/dev/null; then
    printf 'FAULT_PRECONDITION_MISSING lock=%s owner_pid=%s\n' "$lock_target" "$owner_pid" >> "$artifact_dir/browser-handoff.log"
    exit 69
  fi
  printf 'FAULT_FREEZE epoch_ns=%s owner_pid=%s\n' "$(date +%s%N)" "$owner_pid" >> "$artifact_dir/browser-handoff.log"
  kill -STOP "$owner_pid"
  (sleep 7; kill -CONT "$owner_pid" 2>/dev/null || true;
    printf 'FAULT_RESUME epoch_ns=%s owner_pid=%s\n' "$(date +%s%N)" "$owner_pid" >> "$artifact_dir/browser-handoff.log") &
fi
set +e
/usr/bin/google-chrome --headless=new --no-sandbox --disable-gpu \
  --disable-dev-shm-usage --disable-background-networking --no-first-run \
  --no-default-browser-check --user-data-dir="$profile" \
  --enable-logging=stderr --v=1 "$@" 2>> "$artifact_dir/chrome-stderr.log"
code=$?
set -e
printf 'CHROME_EXIT epoch_ns=%s count=%s code=%s\n' "$(date +%s%N)" "$count" "$code" >> "$artifact_dir/browser-handoff.log"
exit "$code"
