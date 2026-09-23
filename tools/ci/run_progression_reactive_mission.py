#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "ci-artifacts" / "progression-reactive-mission"
WEBOTS_IMAGE = "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
TEMP_WORLD = ROOT / "worlds" / "ci_progression_reactive.wbt"
TEMP_PROJECT = ROOT / "worlds" / ".ci_progression_reactive.wbproj"


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def fail(message: str, detail: str | None = None) -> int:
    print(f"FAIL reactive mission evidence: {message}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    return 1


def cleanup() -> None:
    for path in (TEMP_WORLD, TEMP_PROJECT):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    if shutil.which("docker") is None:
        return fail("docker is unavailable")
    cleanup()
    shutil.rmtree(ARTIFACT_ROOT, ignore_errors=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    checks = [
        ["node", "tools/ci/test_progression_reactive_contract.js"],
        ["node", "--check", "plugins/robot_windows/reactive_probe/reactive_probe.js"],
    ]
    for command in checks:
        checked = run(command, capture=True)
        if checked.returncode:
            return fail("static Activity 5 contract failed", checked.stdout)

    source_world = (ROOT / "worlds" / "crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    for marker in (
        "WEBEEBLOCKS_REACTIVE_MISSION_V1_BEGIN",
        "WEBEEBLOCKS_REACTIVE_ROW_CHECKPOINTS_V1_BEGIN",
        "WEBEEBLOCKS_REACTIVE_EVALUATOR_V1_BEGIN",
        "DEF ACTIVITY5_BARRIER_1 Solid",
        "DEF ACTIVITY5_BARRIER_2 Solid",
        "DEF ACTIVITY5_BARRIER_3 Solid",
        'name "Crazyflie WebeeBlocks"',
        'name "Progression reactive evaluator"',
        '"reactive-evaluator-v1"',
    ):
        if marker not in source_world:
            return fail(f"missing Activity 5 world marker: {marker}")
    TEMP_WORLD.write_text(source_world.replace('window "blockly_v2"', 'window "reactive_probe"', 1), encoding="utf-8")
    TEMP_PROJECT.write_text("Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n", encoding="utf-8")

    try:
        pull = run(["docker", "pull", WEBOTS_IMAGE], capture=True)
        if pull.returncode:
            return fail("pinned Webots image could not be prepared", pull.stdout)
        built = run([
            "docker", "run", "--rm", "-v", f"{ROOT}:/workspace",
            "-w", "/workspace/controllers/crazyflie_runtime_v2", WEBOTS_IMAGE,
            "bash", "-lc", "make clean && make",
        ], capture=True)
        (ARTIFACT_ROOT / "build.log").write_text(built.stdout or "", encoding="utf-8")
        if built.returncode:
            return fail("Runtime v2/Activity 5 evaluator build failed", (built.stdout or "")[-6000:])

        inner = r'''
set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
mkdir -p /workspace/ci-artifacts/progression-reactive-mission /root/.config/Cyberbotics
printf "%s\n" \
  "[RobotWindow]" \
  "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
  "newBrowserWindow=false" \
  > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py \
  --output /workspace/ci-artifacts/progression-reactive-mission/browser-events.jsonl &
server=$!
trap "kill $server 2>/dev/null || true" EXIT
sleep 0.5
timeout -k 5s 360s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_progression_reactive.wbt
'''.strip()
        result = subprocess.run([
            "docker", "run", "--rm",
            "-e", "LIBGL_ALWAYS_SOFTWARE=true",
            "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
            "-e", "WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/progression-reactive-mission",
            "-v", f"{ROOT}:/workspace", "-w", "/workspace", WEBOTS_IMAGE,
            "bash", "-lc", inner,
        ], cwd=ROOT, env=os.environ.copy(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        webots_log = result.stdout or ""
        (ARTIFACT_ROOT / "webots.log").write_text(webots_log, encoding="utf-8")
        (ARTIFACT_ROOT / "exit-code.txt").write_text(str(result.returncode) + "\n", encoding="utf-8")
        if result.returncode not in (0, 124):
            return fail(f"Webots Activity 5 mission exited with {result.returncode}", webots_log[-16000:])

        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing browser Activity 5 evidence", webots_log[-16000:])
        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid browser Activity 5 evidence: {exc}")
        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            return fail("Activity 5 browser probe reported an error", json.dumps(errors[0], ensure_ascii=False) + "\n" + webots_log[-16000:])

        required = (
            "REACTIVE_PROBE_READY",
            "REACTIVE_BOB_ACHIEVED", "REACTIVE_BOB_RESET_FRESH",
            "REACTIVE_OBO_ACHIEVED", "REACTIVE_OBO_RESET_FRESH",
            "REACTIVE_ONE_MEASUREMENT_NOT_ACHIEVED", "REACTIVE_ONE_MEASUREMENT_RESET_FRESH",
            "REACTIVE_FIXED_FORWARD_NOT_ACHIEVED", "REACTIVE_FIXED_FORWARD_RESET_FRESH",
            "REACTIVE_FIXED_LEFT_NOT_ACHIEVED", "REACTIVE_FIXED_LEFT_RESET_FRESH",
            "REACTIVE_UNROLLED_OBO_ACHIEVED", "REACTIVE_UNROLLED_OBO_RESET_FRESH",
            "REACTIVE_UNROLLED_BOB_ACHIEVED", "REACTIVE_UNROLLED_BOB_RESET_FRESH",
            "REACTIVE_MISSION_TEST_COMPLETE",
        )
        names = [event.get("event") for event in events]
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing causal Activity 5 events: {missing}", json.dumps(names))
        details = {name: next(event["detail"] for event in events if event.get("event") == name) for name in required}
        for name in ("REACTIVE_BOB_ACHIEVED", "REACTIVE_OBO_ACHIEVED", "REACTIVE_UNROLLED_OBO_ACHIEVED", "REACTIVE_UNROLLED_BOB_ACHIEVED"):
            if details[name] != {"status":"achieved"}:
                return fail(f"unexpected achieved event {name}: {details[name]}")
        for name in ("REACTIVE_ONE_MEASUREMENT_NOT_ACHIEVED", "REACTIVE_FIXED_FORWARD_NOT_ACHIEVED", "REACTIVE_FIXED_LEFT_NOT_ACHIEVED"):
            if details[name] != {"status":"not-achieved", "runtime_code":"UNSAFE_OR_TIMEOUT"}:
                return fail(f"unexpected negative event {name}: {details[name]}")
        for name in required:
            if name.endswith("RESET_FRESH") and details[name] != {"code":"OUTCOME_UNAVAILABLE"}:
                return fail(f"outcome survived reset at {name}: {details[name]}")
        if details["REACTIVE_MISSION_TEST_COMPLETE"] != {
            "repeated_bob":"achieved", "repeated_obo":"achieved", "one_measurement":"not-achieved",
            "fixed_forward":"not-achieved", "fixed_left":"not-achieved",
            "unrolled_obo":"achieved", "unrolled_bob":"achieved"
        }:
            return fail(f"unexpected Activity 5 summary: {details['REACTIVE_MISSION_TEST_COMPLETE']}")

        for marker in (
            "WEBEEBLOCKS_REACTIVE_CONFIG attempt=1 pattern=BOB",
            "WEBEEBLOCKS_REACTIVE_RESULT attempt=1 status=achieved",
            "WEBEEBLOCKS_REACTIVE_CONFIG attempt=2 pattern=OBO",
            "WEBEEBLOCKS_REACTIVE_RESULT attempt=2 status=achieved",
            "WEBEEBLOCKS_REACTIVE_RESULT attempt=3 status=not-achieved",
            "WEBEEBLOCKS_REACTIVE_RESULT attempt=4 status=not-achieved",
            "WEBEEBLOCKS_REACTIVE_RESULT attempt=5 status=not-achieved",
            "WEBEEBLOCKS_REACTIVE_RESULT attempt=6 status=achieved",
            "WEBEEBLOCKS_REACTIVE_RESULT attempt=7 status=achieved",
        ):
            if marker not in webots_log:
                return fail(f"missing Webots Activity 5 marker: {marker}", webots_log[-16000:])
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-16000:])

        print("PASS Activity 5 warehouse rows: one repeated fresh-sensing program succeeds across B-O-B/O-B-O patterns, one-measurement and fixed routes fail, equivalent unrolled fresh sensing succeeds, and reset freshness holds in real R2025a")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
