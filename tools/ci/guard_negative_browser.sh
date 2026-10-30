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
  # A renewed *old* tab still has its original profile. Merely changing the
  # second Chrome CLI --user-data-dir no longer injects actual data loss.
  # For this disposable native negative ONLY, first terminate the EXACT
  # Chrome profile owner of the CI fixture; do not touch any unrelated browser.
  lock="/tmp/webeeblocks-native-guard-profile/SingletonLock"
  if [ -L "$lock" ]; then
    target=$(readlink "$lock")
    pid="${target##*-}"
    if ! [[ "$pid" =~ ^[0-9]+$ ]]; then exit 65; fi
    args=$(ps -p "$pid" -o args= 2>/dev/null || true)
    case "$args" in
      *"/tmp/webeeblocks-native-guard-profile"*)
        printf 'NEGATIVE_DESTROY_OLD_BROWSER owner_pid=%s\n' "$pid" >> "$WEBEEBLOCKS_CI_ARTIFACT_DIR/profile-fault.log"
        kill -TERM "$pid" 2>/dev/null || true
        ;;
      *) echo "Unsafe/unverified Chrome owner: $pid" >&2; exit 66 ;;
    esac
    exited=0
    for i in $(seq 1 40); do
      state=$(ps -p "$pid" -o stat= 2>/dev/null || true)
      if [ -z "$state" ] || [[ "$state" = Z* ]]; then exited=1; break; fi
      sleep .1
    done
    if [ "$exited" -ne 1 ]; then
      echo "Original profile owner did not exit: $pid" >&2
      exit 67
    fi
  fi
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
