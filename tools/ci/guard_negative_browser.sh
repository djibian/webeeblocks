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
exec /usr/bin/google-chrome --headless=new --no-sandbox --disable-gpu \
  --disable-dev-shm-usage --disable-background-networking --no-first-run \
  --no-default-browser-check --user-data-dir="$profile" "$@" 2>> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/chrome-stderr.log"
