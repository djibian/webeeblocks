#!/usr/bin/env bash
set -euo pipefail
ROOT=/workspace
OUT="$ROOT/ci-artifacts/runtime-v2-student-ui"
FIXTURE="$ROOT/controllers/Blockly_Programs/CrazyflieReactiveV2.xml"
EXPECTED_AST="$ROOT/experiments/runtime-v2-student-ui/expected_ast.json"
mkdir -p "$OUT" /root/.config/Cyberbotics
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates python3-websocket >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x "$ROOT/experiments/runtime-v2-student-ui/browser.sh"
printf '%s\n' '[RobotWindow]' 'browser=/workspace/experiments/runtime-v2-student-ui/browser.sh' 'newBrowserWindow=false' > /root/.config/Cyberbotics/Webots-R2025a.conf
export WEBEEBLOCKS_CI_ARTIFACT_DIR="$OUT"
xvfb-run -a webots --stdout --stderr --batch --mode=realtime "$ROOT/worlds/crazyflie_runtime_v2.wbt" > "$OUT/webots.log" 2>&1 &
wpid=$!
trap 'kill "$wpid" 2>/dev/null || true; wait "$wpid" 2>/dev/null || true' EXIT
set +e
python3 "$ROOT/experiments/runtime-v2-student-ui/diagnostic_probe.py" --fixture "$FIXTURE" --expected-ast "$EXPECTED_AST" --output "$OUT/metrics.json" --screenshot "$OUT/workspace-1366x768.png"
probe_status=$?
set -e
if [[ -s "$OUT/tooltip-hover-diagnostic.json" ]]; then
  echo 'WEBEEBLOCKS_TOOLTIP_DIAGNOSTIC_BEGIN'
  cat "$OUT/tooltip-hover-diagnostic.json"
  echo 'WEBEEBLOCKS_TOOLTIP_DIAGNOSTIC_END'
else
  echo 'WEBEEBLOCKS_TOOLTIP_DIAGNOSTIC_MISSING'
fi
exit "$probe_status"
