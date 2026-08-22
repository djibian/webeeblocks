#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
artifact_dir="$repo_root/ci-artifacts/modern-blockly-wwi"
mkdir -p "$artifact_dir"

docker run --rm -i \
  -e LIBGL_ALWAYS_SOFTWARE=true \
  -e WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true \
  -v "$repo_root:/workspace" \
  -w /workspace \
  cyberbotics/webots:R2025a-ubuntu22.04 \
  bash -s <<'CONTAINER'
set -euo pipefail
artifact_dir=/workspace/ci-artifacts/modern-blockly-wwi
plugin=/workspace/plugins/robot_windows/modern_blockly_v2_experiment
world=/workspace/worlds/modern_blockly_v2_experiment.wbt
wrapper=/workspace/experiments/modern-blockly/webots_browser.sh
close_chrome=/workspace/experiments/modern-blockly/close_chrome_cdp.py
oracle=/workspace/experiments/modern-blockly/netlog_oracle.py
mkdir -p "$artifact_dir"

apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null

cp /workspace/experiments/modern-blockly/wwi_robot_window.html "$plugin/modern_blockly_v2_experiment.html"
cp /workspace/experiments/modern-blockly/wwi_robot_window.js "$plugin/main.js"
# The R2025a Docker image does not ship resources/web/wwi. Provision the exact
# upstream R2025a modules during the online CI setup phase, then verify their
# immutable Git blob identities before the offline Robot Window runtime starts.
wwi_source_base=https://raw.githubusercontent.com/cyberbotics/webots/R2025a/resources/web/wwi
wget -q -O "$plugin/RobotWindow.js" "$wwi_source_base/RobotWindow.js"
wget -q -O "$plugin/request_methods.js" "$wwi_source_base/request_methods.js"
python3 - <<'PY'
from hashlib import sha1
from pathlib import Path

expected = {
    'RobotWindow.js': 'e8e92bb35663160b16a7c25ab2338a6f06ade62a',
    'request_methods.js': '9b13416f4004b85570fa74fbefd68f386fa6cc72',
}
root = Path('/workspace/plugins/robot_windows/modern_blockly_v2_experiment')
for name, blob_sha in expected.items():
    data = (root / name).read_bytes()
    actual = sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
    if actual != blob_sha:
        raise SystemExit(f'{name}: unexpected R2025a Git blob {actual}, expected {blob_sha}')
print('WEBOTS_R2025A_WWI_MODULES=PASS')
PY
chmod +x "$wrapper" "$close_chrome" "$oracle"
mkdir -p /root/.config/Cyberbotics
printf '%s\n' '[RobotWindow]' 'browser=/workspace/experiments/modern-blockly/webots_browser.sh' 'newBrowserWindow=false' > /root/.config/Cyberbotics/Webots-R2025a.conf

stop_chrome() {
  local pid_file=$1
  if [[ ! -s "$pid_file" ]]; then
    echo '::error::Chrome PID missing'
    return 1
  fi
  local chrome_pid
  chrome_pid=$(cat "$pid_file")

  # Match the already-proven #58 shutdown contract: request Browser.close over
  # DevTools so --log-net-log can finish writing valid JSON. Signals are cleanup
  # fallback only and never count as a successful WWI oracle run.
  if ! python3 "$close_chrome"; then
    echo '::error::Could not request graceful Chrome Browser.close'
    kill -TERM "$chrome_pid" 2>/dev/null || true
    return 1
  fi

  for _ in $(seq 1 100); do
    kill -0 "$chrome_pid" 2>/dev/null || break
    sleep 0.1
  done
  if kill -0 "$chrome_pid" 2>/dev/null; then
    echo '::error::Chrome did not exit after Browser.close'
    kill -TERM "$chrome_pid" 2>/dev/null || true
    return 1
  fi
  echo 'CHROME_GRACEFUL_SHUTDOWN_WWI=PASS'
}

rm -f "$artifact_dir"/* /workspace/ci-artifacts/modern-blockly/browser-launch.log /workspace/ci-artifacts/modern-blockly/chrome.pid /workspace/ci-artifacts/modern-blockly/chrome-netlog.json
python3 /workspace/tools/ci/runtime_wwi_event_server.py --output "$artifact_dir/browser-events.jsonl" >"$artifact_dir/event-server.log" 2>&1 &
event_server_pid=$!
sleep 0.5

xvfb-run -a webots --stdout --stderr --batch --mode=realtime "$world" >"$artifact_dir/webots.log" 2>&1 &
webots_pid=$!
deadline=$((SECONDS + 75))
done_seen=0
while kill -0 "$webots_pid" 2>/dev/null; do
  if [[ -s "$artifact_dir/browser-events.jsonl" ]] && grep -Fq '"event":"RUN_DONE"' "$artifact_dir/browser-events.jsonl"; then
    done_seen=1
    break
  fi
  if grep -Fq '"event":"ERROR"' "$artifact_dir/browser-events.jsonl" 2>/dev/null; then
    break
  fi
  if (( SECONDS >= deadline )); then
    break
  fi
  sleep 0.25
done

if (( done_seen == 0 )); then
  echo '::error::modern Blockly WWI run did not reach RUN_DONE'
  cat "$artifact_dir/browser-events.jsonl" 2>/dev/null || true
  cat "$artifact_dir/webots.log" || true
  kill -TERM "$webots_pid" 2>/dev/null || true
  kill "$event_server_pid" 2>/dev/null || true
  exit 1
fi

stop_chrome /workspace/ci-artifacts/modern-blockly/chrome.pid

python3 - <<'PY'
import json
from pathlib import Path
p = Path('/workspace/ci-artifacts/modern-blockly/chrome-netlog.json')
with p.open('r', encoding='utf-8') as f: json.load(f)
print('MODERN_BLOCKLY_WWI_NETLOG_COMPLETE=PASS')
PY
cp /workspace/ci-artifacts/modern-blockly/chrome-netlog.json "$artifact_dir/chrome-netlog.json"
python3 "$oracle" "$artifact_dir/chrome-netlog.json"

kill -TERM "$webots_pid" 2>/dev/null || true
wait "$webots_pid" 2>/dev/null || true
kill "$event_server_pid" 2>/dev/null || true
wait "$event_server_pid" 2>/dev/null || true

python3 - <<'PY'
import json
from pathlib import Path
root = Path('/workspace/ci-artifacts/modern-blockly-wwi')
events_path = root / 'browser-events.jsonl'
webots_path = root / 'webots.log'
assert events_path.is_file() and events_path.stat().st_size > 0, events_path
assert webots_path.is_file() and webots_path.stat().st_size > 0, webots_path
events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
assert events and not any(e.get('event') == 'ERROR' for e in events), events
names = [e['event'] for e in events]
required = ['PAGE_LOADED','BLOCKLY_INITIALIZED','PROFILE_APPLIED','AST_EQUIVALENT','WWI_BOUND','RUN_STARTED','RUN_DONE']
pos = [names.index(x) for x in required]
assert pos == sorted(pos), (names, pos)
rx = [e['detail']['message'] for e in events if e.get('event') == 'WWI_RX']
tx = [e['detail']['message'] for e in events if e.get('event') == 'WWI_TX']
assert any(' REQUEST ' in m and ' TAKEOFF ' in m for m in tx), tx
assert sum(' RANGE front' in m for m in tx) == 3, tx
assert any(' MOVE left ' in m for m in tx), tx
assert any(' MOVE forward ' in m for m in tx), tx
assert any(m.endswith(' LAND') for m in tx), tx
assert any(' RESPONSE ' in m and ' OK' in m for m in rx), rx
assert sum(' RESPONSE ' in m and ' VALUE ' in m for m in rx) == 3, rx
log = webots_path.read_text(errors='replace')
for marker in ['TRACE TAKEOFF', 'TRACE RANGE front', 'TRACE MOVE left', 'TRACE MOVE forward', 'TRACE LAND']:
    assert marker in log, marker
assert 'FATAL' not in log and 'UNSAFE_OR_TIMEOUT' not in log, log
print('MODERN_BLOCKLY_WWI_CAUSAL_CHAIN=PASS')
PY
CONTAINER
