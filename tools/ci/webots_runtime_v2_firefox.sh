#!/usr/bin/env bash
set -eu
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/runtime-v2-firefox-project-files}"
firefox_bin="${WEBEEBLOCKS_FIREFOX_BIN:-/tmp/firefox/firefox}"
profile_dir="${WEBEEBLOCKS_FIREFOX_PROFILE:-/tmp/webeeblocks-firefox-profile}"
mkdir -p "$artifact_dir" "$profile_dir"
printf 'FIREFOX_LAUNCHED args=' >> "$artifact_dir/firefox-launch.log"
printf '%q ' "$@" >> "$artifact_dir/firefox-launch.log"
printf '\n' >> "$artifact_dir/firefox-launch.log"
exec "$firefox_bin" \
  --headless \
  --no-remote \
  --profile "$profile_dir" \
  "$@"
