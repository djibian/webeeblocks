#!/usr/bin/env bash
set -euo pipefail

artifact_dir=/workspace/ci-artifacts/modern-blockly
netlog="$artifact_dir/chrome-netlog.json"
pid_file="$artifact_dir/chrome.pid"
mkdir -p "$artifact_dir"
printf 'BROWSER_LAUNCHED args=' >> "$artifact_dir/browser-launch.log"
printf '%q ' "$@" >> "$artifact_dir/browser-launch.log"
printf '\n' >> "$artifact_dir/browser-launch.log"

chrome_pid=''
cleanup() {
  if [[ -n "$chrome_pid" ]] && kill -0 "$chrome_pid" 2>/dev/null; then
    kill -TERM "$chrome_pid" 2>/dev/null || true
    for _ in $(seq 1 50); do
      kill -0 "$chrome_pid" 2>/dev/null || break
      sleep 0.1
    done
  fi
  if [[ -n "$chrome_pid" ]]; then
    wait "$chrome_pid" 2>/dev/null || true
  fi
  chmod a+r "$netlog" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 143' TERM INT HUP

/usr/bin/google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-background-networking \
  --no-first-run \
  --no-default-browser-check \
  --no-proxy-server \
  --host-resolver-rules='MAP * 0.0.0.0, EXCLUDE localhost, EXCLUDE 127.0.0.1' \
  --log-net-log="$netlog" \
  --net-log-capture-mode=Everything \
  --enable-logging=stderr \
  --v=1 \
  "$@" &
chrome_pid=$!
printf '%s\n' "$chrome_pid" > "$pid_file"

set +e
wait "$chrome_pid"
status=$?
set -e
exit "$status"
