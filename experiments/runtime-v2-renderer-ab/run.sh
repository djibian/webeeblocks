#!/usr/bin/env bash
set -euo pipefail
ROOT=/workspace
OUT="$ROOT/ci-artifacts/runtime-v2-renderer-ab"
FIXTURE="$ROOT/controllers/Blockly_Programs/CrazyflieReactiveV2.xml"
mkdir -p "$OUT" /root/.config/Cyberbotics

apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates python3-websocket >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x "$ROOT/experiments/runtime-v2-renderer-ab/browser.sh"
printf '%s\n' \
  '[RobotWindow]' \
  'browser=/workspace/experiments/runtime-v2-renderer-ab/browser.sh' \
  'newBrowserWindow=false' \
  > /root/.config/Cyberbotics/Webots-R2025a.conf

current_webots_pid=""
cleanup_current() {
  if [[ -n "$current_webots_pid" ]]; then
    kill "$current_webots_pid" 2>/dev/null || true
    wait "$current_webots_pid" 2>/dev/null || true
    current_webots_pid=""
  fi
}
trap cleanup_current EXIT

run_variant() {
  renderer="$1"
  dir="$OUT/$renderer"
  mkdir -p "$dir"
  export WEBEEBLOCKS_RENDERER="$renderer"
  export WEBEEBLOCKS_CI_ARTIFACT_DIR="$dir"

  xvfb-run -a webots --stdout --stderr --batch --mode=realtime "$ROOT/worlds/crazyflie_runtime_v2.wbt" \
    > "$dir/webots.log" 2>&1 &
  current_webots_pid=$!

  python3 "$ROOT/experiments/runtime-v2-renderer-ab/probe.py" \
    --renderer "$renderer" \
    --fixture "$FIXTURE" \
    --output "$dir/metrics.json" \
    --screenshot "$dir/workspace-1366x768.png"

  cleanup_current
}

run_variant thrasos
run_variant zelos
