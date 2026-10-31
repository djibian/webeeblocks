#!/usr/bin/env bash
# CI-ONLY real native A/B: refuse an early READY-only submission, then
# authorize the identical Blockly program after actual RECOVERY_STATUS NONE.
# All physical tests and machine-code oracles remain unchanged.
set -euo pipefail
repo=$(git rev-parse --show-toplevel)
cd "$repo"
out=ci-artifacts/observability-unsafe
mkdir -p "$out"
git show HEAD:plugins/robot_windows/blockly_v2/blockly_v2.html > plugins/robot_windows/blockly_v2/blockly_v2.html
python3 tools/ci/prepare_runtime_v2_observability.py --mode unsafe
set +e
docker run --rm \
  -e LIBGL_ALWAYS_SOFTWARE=true \
  -e WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true \
  -e WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/observability-unsafe \
  -v "$repo:/workspace" -w /workspace \
  cyberbotics/webots:R2025a-ubuntu22.04 \
  bash -lc '
    set -e
    apt-get update >/dev/null
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
    wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
    chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
    mkdir -p /workspace/ci-artifacts/observability-unsafe /root/.config/Cyberbotics
    printf "%s\n" \
      "[RobotWindow]" \
      "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
      "newBrowserWindow=false" \
      > /root/.config/Cyberbotics/Webots-R2025a.conf
    python3 /workspace/tools/ci/runtime_wwi_event_server.py \
      --output /workspace/ci-artifacts/observability-unsafe/browser-events.jsonl &
    server=$!
    trap "kill $server 2>/dev/null || true" EXIT
    sleep 0.5
    timeout -k 5s 190s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/crazyflie_runtime_v2.wbt
  ' 2>&1 | tee "$out/webots.log"
code=${PIPESTATUS[0]}
set -e
printf '%s\n' "$code" > "$out/exit-code.txt"
if [ "$code" -ne 0 ] && [ "$code" -ne 124 ]; then exit "$code"; fi
python3 - <<'PY'
from pathlib import Path
import json
base = Path('ci-artifacts/observability-unsafe')
events = [json.loads(line) for line in (base/'browser-events.jsonl').read_text().splitlines() if line.strip()]
names = [e['event'] for e in events]
assert not [e for e in events if e['event'] in ('ERROR', 'WINDOW_ERROR', 'UNHANDLED_REJECTION')], events
required = ['NATIVE_STATUS_RECEIVED', 'PREAUTH_CONTROL_REFUSED', 'AUTHORIZED_FOR_EXECUTION',
            'UNSAFE_ACTUAL_TAKEOFF', 'UNSAFE_SCENARIO_DONE']
assert all(names.count(e) == 1 for e in required), names
assert [names.index(e) for e in required] == sorted(names.index(e) for e in required), names
held = next(e['detail'] for e in events if e['event'] == 'PREAUTH_CONTROL_REFUSED')
authorized = next(e['detail'] for e in events if e['event'] == 'AUTHORIZED_FOR_EXECUTION')
assert held['backendReady'] and held['nativeState'] == 'NONE'
assert held['recoveryPending'] and held['terminal'] and held['submitDisabled']
assert held['wwiRequests'] == 0 and held['nextId'] == 2, held
assert authorized['ready'] and authorized['state'] == 'PRÊT' and authorized['submitDisabled'] is False, authorized
assert authorized['nextId'] == held['nextId'] and authorized['ast'] == held['ast'], (held, authorized)
tx = [e['detail'] for e in events if e['event'] == 'WWI_TX']
assert any(' TAKEOFF ' in x for x in tx), tx
assert not any(e['event'] == 'WWI_TX' for e in events[:names.index('AUTHORIZED_FOR_EXECUTION')])
done = next(e['detail'] for e in events if e['event'] == 'UNSAFE_SCENARIO_DONE')
assert done['ast'] == held['ast'], done
assert done['diagnostic']['machineCode'] == 'UNSAFE_OR_TIMEOUT', done
assert done['diagnostic']['studentState'] == 'ARRÊTÉ', done
assert done['snapshot']['state'] == 'ARRÊTÉ', done
assert done['snapshot']['detail'] == 'L’action n’a pas pu être terminée', done
assert 'UNSAFE_OR_TIMEOUT' not in done['snapshot']['detail'], done
log = (base/'webots.log').read_text(errors='replace')
assert 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 RECOVERY_STATUS' in log and ' NONE' in log
assert 'ERR UNSAFE_OR_TIMEOUT' in log, 'missing native controller error'
assert 'FATAL unsafe attitude or action timeout' in log, 'missing native fail-safe'
print('PASS: READY-only refused, real NONE consumed, WWI TAKEOFF and native UNSAFE_OR_TIMEOUT, student ARRÊTÉ.')
PY
