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
exec /usr/bin/google-chrome --headless=new --no-sandbox --disable-gpu \
  --disable-dev-shm-usage --disable-background-networking --no-first-run \
  --no-default-browser-check --user-data-dir="$profile" "$@"
