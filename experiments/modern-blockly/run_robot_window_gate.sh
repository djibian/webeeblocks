#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
artifact_dir="$repo_root/ci-artifacts/modern-blockly"
mkdir -p "$artifact_dir"

# Provisioning may use the network. The runtime below must not depend on it.
docker run --rm \
  -e LIBGL_ALWAYS_SOFTWARE=true \
  -e WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true \
  -v "$repo_root:/workspace" \
  -w /workspace \
  cyberbotics/webots:R2025a-ubuntu22.04 \
  bash -s <<'CONTAINER'
set -euo pipefail

artifact_dir=/workspace/ci-artifacts/modern-blockly
plugin_html=/workspace/plugins/robot_windows/modern_blockly_v2_experiment/modern_blockly_v2_experiment.html
sentinel_url=https://example.invalid/webeeblocks-required-blockly.js
wrapper=/workspace/experiments/modern-blockly/webots_browser.sh
oracle=/workspace/experiments/modern-blockly/netlog_oracle.py
world=/workspace/worlds/modern_blockly_v2_experiment.wbt
mkdir -p "$artifact_dir"

apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x "$wrapper" "$oracle"
mkdir -p /root/.config/Cyberbotics
printf '%s\n' \
  '[RobotWindow]' \
  'browser=/workspace/experiments/modern-blockly/webots_browser.sh' \
  'newBrowserWindow=false' \
  > /root/.config/Cyberbotics/Webots-R2025a.conf

stop_chrome() {
  local pid_file=$1
  if [[ ! -s "$pid_file" ]]; then
    echo "::error::Chrome PID was not recorded"
    return 1
  fi
  local chrome_pid
  chrome_pid=$(cat "$pid_file")
  kill -TERM "$chrome_pid" 2>/dev/null || true
  for _ in $(seq 1 50); do
    kill -0 "$chrome_pid" 2>/dev/null || break
    sleep 0.1
  done
  if kill -0 "$chrome_pid" 2>/dev/null; then
    echo "::error::Chrome did not stop gracefully"
    return 1
  fi
}

run_case() {
  local label=$1
  local expect_ast=$2
  local deadline_seconds=$3
  local events="$artifact_dir/browser-events-$label.jsonl"
  local webots_log="$artifact_dir/webots-$label.log"

  rm -f "$artifact_dir/browser-launch.log" "$artifact_dir/chrome.pid" "$artifact_dir/chrome-netlog.json" "$events" "$webots_log"

  python3 /workspace/tools/ci/runtime_wwi_event_server.py --output "$events" >"$artifact_dir/event-server-$label.log" 2>&1 &
  local event_server_pid=$!
  sleep 0.5

  xvfb-run -a webots --stdout --stderr --batch --mode=fast "$world" >"$webots_log" 2>&1 &
  local webots_pid=$!
  local deadline=$((SECONDS + deadline_seconds))
  local ast_seen=0
  local error_seen=0

  while kill -0 "$webots_pid" 2>/dev/null; do
    if [[ -s "$events" ]]; then
      grep -Fq '"event":"AST_EQUIVALENT"' "$events" && ast_seen=1 || true
      grep -Fq '"event":"ERROR"' "$events" && error_seen=1 || true
    fi
    if (( expect_ast == 1 && ast_seen == 1 )); then
      break
    fi
    if (( expect_ast == 0 && error_seen == 1 )); then
      break
    fi
    if (( SECONDS >= deadline )); then
      break
    fi
    sleep 0.25
  done

  if (( expect_ast == 1 && ast_seen == 0 )); then
    echo "::error::AST_EQUIVALENT was not observed in positive runtime case"
    cat "$webots_log" || true
    kill -TERM "$webots_pid" 2>/dev/null || true
    kill "$event_server_pid" 2>/dev/null || true
    return 1
  fi
  if (( expect_ast == 0 && ast_seen == 1 )); then
    echo "::error::Countertest unexpectedly reached AST_EQUIVALENT with required Blockly asset externalized"
    kill -TERM "$webots_pid" 2>/dev/null || true
    kill "$event_server_pid" 2>/dev/null || true
    return 1
  fi
  if (( expect_ast == 0 && error_seen == 0 )); then
    echo "::error::Countertest did not surface a browser error for the blocked required asset"
    cat "$webots_log" || true
    kill -TERM "$webots_pid" 2>/dev/null || true
    kill "$event_server_pid" 2>/dev/null || true
    return 1
  fi

  stop_chrome "$artifact_dir/chrome.pid"
  python3 - <<PY
import json
from pathlib import Path
with Path('$artifact_dir/chrome-netlog.json').open('r', encoding='utf-8') as handle:
    json.load(handle)
print('CHROME_NETLOG_COMPLETE_$label=PASS')
PY

  kill -TERM "$webots_pid" 2>/dev/null || true
  wait "$webots_pid" 2>/dev/null || true
  kill "$event_server_pid" 2>/dev/null || true
  wait "$event_server_pid" 2>/dev/null || true

  mv "$artifact_dir/browser-launch.log" "$artifact_dir/browser-launch-$label.log"
  mv "$artifact_dir/chrome.pid" "$artifact_dir/chrome-$label.pid"
  mv "$artifact_dir/chrome-netlog.json" "$artifact_dir/chrome-netlog-$label.json"
}

run_case positive 1 40
python3 "$oracle" "$artifact_dir/chrome-netlog-positive.json"

python3 - <<'PY'
import json
from pathlib import Path

events = [json.loads(line) for line in Path('/workspace/ci-artifacts/modern-blockly/browser-events-positive.jsonl').read_text().splitlines() if line.strip()]
assert events, 'no positive browser events'
assert not any(event.get('event') == 'ERROR' for event in events), events
names = [event.get('event') for event in events]
required = ['PAGE_LOADED', 'BLOCKLY_INITIALIZED', 'PROFILE_APPLIED', 'AST_EQUIVALENT']
positions = [names.index(name) for name in required]
assert positions == sorted(positions), (names, positions)
initialized = next(event for event in events if event.get('event') == 'BLOCKLY_INITIALIZED')
assert initialized['detail']['version'] == '13.2.1', initialized
profile = next(event for event in events if event.get('event') == 'PROFILE_APPLIED')
assert profile['detail']['profile'] == 'reactive-obstacle-v2', profile
equivalent = next(event for event in events if event.get('event') == 'AST_EQUIVALENT')
expected = json.loads(Path('/workspace/experiments/modern-blockly/expected_ast.json').read_text())
assert equivalent['detail']['ast'] == expected, (equivalent['detail']['ast'], expected)
print('MODERN_BLOCKLY_POSITIVE_CAUSAL_CHAIN=PASS')
PY

cp "$plugin_html" "$artifact_dir/modern-blockly-positive.html"
python3 - <<PY
from pathlib import Path
path = Path('$plugin_html')
text = path.read_text(encoding='utf-8')
old = 'src="vendor/blockly_compressed.js"'
new = 'src="$sentinel_url"'
if text.count(old) != 1:
    raise SystemExit(f'expected one required Blockly script reference, found {text.count(old)}')
path.write_text(text.replace(old, new), encoding='utf-8')
print('EXTERNAL_REQUIRED_ASSET_INJECTED=PASS')
PY

run_case negative 0 15
python3 "$oracle" "$artifact_dir/chrome-netlog-negative.json" --expect-blocked-url "$sentinel_url"
grep -Fq '"event":"ERROR"' "$artifact_dir/browser-events-negative.jsonl"
! grep -Fq '"event":"AST_EQUIVALENT"' "$artifact_dir/browser-events-negative.jsonl"

echo 'MODERN_BLOCKLY_OFFLINE_RUNTIME_ORACLE=PASS'
CONTAINER
