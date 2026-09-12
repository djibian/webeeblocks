#!/usr/bin/env python3
"""Exercise Firefox project files through the real Webots Qt/WWI broker path."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "plugins/robot_windows/blockly_v2/blockly_v2.html"
ARTIFACT = ROOT / "ci-artifacts/runtime-v2-project-files/firefox"
FIREFOX_URL = "https://ftp.mozilla.org/pub/firefox/releases/155.0/linux-x86_64/en-US/firefox-155.0.tar.xz"
FIREFOX_SHA256 = "fd9ec3f5f113d0825ca0bd1ab3c0756fbc40241034eefce6743be953bcca7473"


def docker_script() -> str:
    return f'''set -euo pipefail
artifact=/workspace/ci-artifacts/runtime-v2-project-files/firefox
mkdir -p "$artifact" /root/.config/Cyberbotics
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
  wget ca-certificates xz-utils libgtk-3-0 libdbus-glib-1-2 libasound2 libxtst6 >/dev/null
wget -q -O /tmp/firefox.tar.xz {FIREFOX_URL}
echo "{FIREFOX_SHA256}  /tmp/firefox.tar.xz" | sha256sum -c -
tar -xJf /tmp/firefox.tar.xz -C /tmp
/tmp/firefox/firefox --version | tee "$artifact/firefox-version.txt"
chmod +x /workspace/tools/ci/webots_runtime_v2_firefox.sh
printf "%s\\n" \\
  "[RobotWindow]" \\
  "browser=/workspace/tools/ci/webots_runtime_v2_firefox.sh" \\
  "newBrowserWindow=false" \\
  > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py --output "$artifact/browser-events.jsonl" &
server=$!
trap 'kill "$server" 2>/dev/null || true' EXIT
sleep 0.5
xvfb-run -a bash -lc '\''
  set -euo pipefail
  artifact=/workspace/ci-artifacts/runtime-v2-project-files/firefox
  python3 /workspace/tools/ci/firefox_project_dialog_driver.py --root "$artifact" --timeout 80 \\
    > "$artifact/dialog-driver.log" 2>&1 &
  driver=$!
  webots --stdout --stderr --batch --mode=realtime /workspace/worlds/crazyflie_runtime_v2.wbt \\
    > "$artifact/webots.log" 2>&1 &
  webots_pid=$!
  driver_done=0
  driver_code=0
  complete=0
  for _ in $(seq 1 900); do
    if [ "$driver_done" -eq 0 ] && ! kill -0 "$driver" 2>/dev/null; then
      set +e
      wait "$driver"
      driver_code=$?
      set -e
      driver_done=1
      if [ "$driver_code" -ne 0 ]; then
        cat "$artifact/dialog-driver.log" >&2
        kill "$webots_pid" 2>/dev/null || true
        wait "$webots_pid" 2>/dev/null || true
        exit "$driver_code"
      fi
    fi
    if grep -q "FIREFOX_PROJECT_FILES_TEST_COMPLETE" "$artifact/browser-events.jsonl" 2>/dev/null; then
      complete=1
      break
    fi
    if ! kill -0 "$webots_pid" 2>/dev/null; then
      set +e
      wait "$webots_pid"
      code=$?
      set -e
      echo "Webots exited before Firefox completion: $code" >&2
      exit 1
    fi
    sleep 0.1
  done
  if [ "$complete" -ne 1 ]; then
    echo "Firefox project-file scenario timed out" >&2
    kill "$webots_pid" 2>/dev/null || true
    wait "$webots_pid" 2>/dev/null || true
    exit 1
  fi
  if [ "$driver_done" -eq 0 ]; then
    wait "$driver"
  fi
  kill "$webots_pid" 2>/dev/null || true
  wait "$webots_pid" 2>/dev/null || true
'\''
'''


def run_scenario() -> None:
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    for path in ARTIFACT.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    original = HTML.read_bytes()
    try:
        subprocess.run([sys.executable, str(ROOT / "tools/ci/prepare_runtime_v2_firefox_project_files.py")], check=True)
        subprocess.run([
            "docker", "run", "--rm",
            "-e", "LIBGL_ALWAYS_SOFTWARE=true",
            "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
            "-e", "WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/runtime-v2-project-files/firefox",
            "-e", "WEBEEBLOCKS_FIREFOX_BIN=/tmp/firefox/firefox",
            "-v", f"{ROOT}:/workspace",
            "-w", "/workspace",
            "cyberbotics/webots:R2025a-ubuntu22.04",
            "bash", "-lc", docker_script(),
        ], check=True)
    finally:
        HTML.write_bytes(original)


def validate() -> None:
    version = (ARTIFACT / "firefox-version.txt").read_text(encoding="utf-8", errors="replace")
    if "Mozilla Firefox 155.0" not in version:
        raise AssertionError(f"unexpected Firefox version: {version!r}")
    events = [json.loads(line) for line in (ARTIFACT / "browser-events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    errors = [e for e in events if e.get("event") in {"ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION"}]
    if errors:
        raise AssertionError(errors[0])
    names = [e.get("event") for e in events]
    required = (
        "FIREFOX_BROKER_READY", "FIREFOX_SAVE_AS_OK", "FIREFOX_SAVE_AS_CANCEL_OK",
        "FIREFOX_OPEN_CANCEL_OK", "FIREFOX_OPEN_OK", "FIREFOX_SAME_FILE_SAVE_OK",
        "FIREFOX_TARGET_PRESERVED_OK", "FIREFOX_PROJECT_FILES_TEST_COMPLETE",
    )
    for name in required:
        if name not in names:
            raise AssertionError((name, names))
    rejected = [e for e in events if e.get("event") == "INVALID_OPEN_REJECTED"]
    labels = [e.get("detail", {}).get("label") for e in rejected]
    if labels != ["malformed", "unsupported-version", "unknown-activity"]:
        raise AssertionError(labels)
    ready = next(e["detail"] for e in events if e.get("event") == "FIREFOX_BROKER_READY")
    if ready.get("mode") != "wwi-native" or "Firefox/155.0" not in ready.get("userAgent", ""):
        raise AssertionError(ready)
    final = next(e["detail"] for e in events if e.get("event") == "FIREFOX_TARGET_PRESERVED_OK")
    if final.get("name") != "roundtrip.wbb":
        raise AssertionError(final)
    driver = (ARTIFACT / "dialog-driver.log").read_text(encoding="utf-8", errors="replace")
    if driver.count("DIALOG_STEP_OK") != 7 or "FIREFOX_DIALOG_PLAN_COMPLETE" not in driver:
        raise AssertionError(driver)
    project_path = ARTIFACT / "roundtrip.wbb"
    project = json.loads(project_path.read_text(encoding="utf-8"))
    if project.get("format") != "webeeblocks-project" or project.get("version") != 1:
        raise AssertionError(project)
    extras = sorted(path.name for path in ARTIFACT.glob("roundtrip*.wbb") if path.name != "roundtrip.wbb")
    if extras:
        raise AssertionError(f"unexpected duplicate Save files: {extras}")
    print("PASS: Firefox 155 -> real Webots Robot Window -> Qt/WWI Open/Save As/same-file Save/cancellation/fail-closed invalid Open")


def main() -> int:
    run_scenario()
    validate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
