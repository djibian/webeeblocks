#!/usr/bin/env bash
set -eu
renderer="${WEBEEBLOCKS_RENDERER:?WEBEEBLOCKS_RENDERER must be thrasos or zelos}"
case "$renderer" in
  thrasos|zelos) ;;
  *) echo "invalid renderer: $renderer" >&2; exit 2 ;;
esac
artifact_dir="${WEBEEBLOCKS_CI_ARTIFACT_DIR:-/workspace/ci-artifacts/runtime-v2-renderer-ab/$renderer}"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED renderer=%s args=' "$renderer" >> "$artifact_dir/browser-launch.log"

args=()
for arg in "$@"; do
  if [[ "$arg" == http://* || "$arg" == https://* ]]; then
    if [[ "$arg" == *\?* ]]; then
      arg="${arg}&renderer=${renderer}"
    else
      arg="${arg}?renderer=${renderer}"
    fi
  fi
  printf '%q ' "$arg" >> "$artifact_dir/browser-launch.log"
  args+=("$arg")
done
printf '\n' >> "$artifact_dir/browser-launch.log"

exec /usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  --window-size=1366,768 \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --remote-allow-origins='*' \
  "${args[@]}"
