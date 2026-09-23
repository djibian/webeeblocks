#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "ci-artifacts" / "progression-sequence-mission"
WEBOTS_IMAGE = "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
TEMP_WORLD = ROOT / "worlds" / "ci_progression_sequence.wbt"
TEMP_PROJECT = ROOT / "worlds" / ".ci_progression_sequence.wbproj"


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def fail(message: str, detail: str | None = None) -> int:
    print(f"FAIL progression mission evidence: {message}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    return 1


def cleanup_temp_world() -> None:
    for path in (TEMP_WORLD, TEMP_PROJECT):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    if shutil.which("docker") is None:
        return fail("docker is unavailable")
    cleanup_temp_world()
    shutil.rmtree(ARTIFACT_ROOT, ignore_errors=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    checks = [
        ["node", "tools/ci/test_progression_sequence_contract.js"],
        ["node", "--check", "plugins/robot_windows/sequence_probe/sequence_probe.js"],
    ]
    for command in checks:
        result = run(command, capture=True)
        if result.returncode:
            return fail("progression mission source validation failed", result.stdout)

    source_world = (ROOT / "worlds" / "crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    for marker in (
        "WEBEEBLOCKS_SEQUENCE_MISSION_V1_BEGIN",
        "WEBEEBLOCKS_PRECISE_MOVEMENT_MISSION_V1_BEGIN",
        'name "Crazyflie WebeeBlocks"',
        'name "Progression sequence evaluator"',
        '"sequence-evaluator-v1"',
        'name "Progression precise movement evaluator"',
        '"precise-evaluator-v1"',
    ):
        if marker not in source_world:
            return fail(f"missing progression world marker: {marker}")
    TEMP_WORLD.write_text(source_world.replace('window "blockly_v2"', 'window "sequence_probe"', 1), encoding="utf-8")
    TEMP_PROJECT.write_text(
        "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n",
        encoding="utf-8",
    )

    try:
        pull = run(["docker", "pull", WEBOTS_IMAGE], capture=True)
        if pull.returncode:
            return fail("pinned Webots image could not be prepared", pull.stdout)

        built = run([
            "docker", "run", "--rm",
            "-v", f"{ROOT}:/workspace",
            "-w", "/workspace/controllers/crazyflie_runtime_v2",
            WEBOTS_IMAGE,
            "bash", "-lc", "make clean && make",
        ], capture=True)
        (ARTIFACT_ROOT / "build.log").write_text(built.stdout or "", encoding="utf-8")
        if built.returncode:
            return fail("Runtime v2/progression evaluators build failed", (built.stdout or "")[-6000:])

        inner = r'''
set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
mkdir -p /workspace/ci-artifacts/progression-sequence-mission /root/.config/Cyberbotics
printf "%s\n" \
  "[RobotWindow]" \
  "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
  "newBrowserWindow=false" \
  > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py \
  --output /workspace/ci-artifacts/progression-sequence-mission/browser-events.jsonl &
server=$!
trap "kill $server 2>/dev/null || true" EXIT
sleep 0.5
timeout -k 5s 260s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_progression_sequence.wbt
'''.strip()

        env = os.environ.copy()
        run_result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-e", "LIBGL_ALWAYS_SOFTWARE=true",
                "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
                "-e", "WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/progression-sequence-mission",
                "-v", f"{ROOT}:/workspace",
                "-w", "/workspace",
                WEBOTS_IMAGE,
                "bash", "-lc", inner,
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        webots_log = run_result.stdout or ""
        (ARTIFACT_ROOT / "webots.log").write_text(webots_log, encoding="utf-8")
        (ARTIFACT_ROOT / "exit-code.txt").write_text(str(run_result.returncode) + "\n", encoding="utf-8")
        if run_result.returncode not in (0, 124):
            return fail(f"Webots progression mission exited with {run_result.returncode}", webots_log[-14000:])

        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing browser progression evidence", webots_log[-14000:])
        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid browser progression evidence: {exc}")

        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            detail = json.dumps(errors[0], ensure_ascii=False) + "\n--- Webots tail ---\n" + webots_log[-14000:]
            return fail("browser progression probe reported an error", detail)
        names = [event.get("event") for event in events]
        required = (
            "SEQUENCE_PROBE_READY",
            "SEQUENCE_ACHIEVED",
            "SEQUENCE_RESET_FRESH",
            "SEQUENCE_REPEAT_ACHIEVED",
            "SEQUENCE_REPEAT_RESET_FRESH",
            "SEQUENCE_NOT_ACHIEVED",
            "SEQUENCE_SECOND_RESET_FRESH",
            "SEQUENCE_ALTERNATIVE_ACHIEVED",
            "SEQUENCE_MISSION_TEST_COMPLETE",
            "PRECISE_INITIAL_RESET_FRESH",
            "PRECISE_ACHIEVED",
            "PRECISE_RESET_FRESH",
            "PRECISE_UNDERSHOOT_NOT_ACHIEVED",
            "PRECISE_UNDERSHOOT_RESET_FRESH",
            "PRECISE_OVERSHOOT_NOT_ACHIEVED",
            "PRECISE_OVERSHOOT_RESET_FRESH",
            "PRECISE_LATERAL_NOT_ACHIEVED",
            "PRECISE_LATERAL_RESET_FRESH",
            "PRECISE_COLLISION_NOT_ACHIEVED",
            "PRECISE_COLLISION_RESET_FRESH",
            "PRECISE_ALTERNATIVE_ACHIEVED",
            "PRECISE_MISSION_TEST_COMPLETE",
        )
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing causal progression events: {missing}", json.dumps(names))

        details = {name: next(event["detail"] for event in events if event.get("event") == name) for name in required}
        for name in ("SEQUENCE_ACHIEVED", "SEQUENCE_REPEAT_ACHIEVED", "SEQUENCE_ALTERNATIVE_ACHIEVED",
                     "PRECISE_ACHIEVED", "PRECISE_ALTERNATIVE_ACHIEVED"):
            if details[name] != {"status": "achieved"}:
                return fail(f"unexpected achieved event {name}: {details[name]}")
        for name in ("SEQUENCE_NOT_ACHIEVED", "PRECISE_UNDERSHOOT_NOT_ACHIEVED",
                     "PRECISE_OVERSHOOT_NOT_ACHIEVED", "PRECISE_LATERAL_NOT_ACHIEVED"):
            if details[name] != {"status": "not-achieved"}:
                return fail(f"unexpected negative event {name}: {details[name]}")
        if details["PRECISE_COLLISION_NOT_ACHIEVED"] != {
            "status":"not-achieved", "runtime_code":"UNSAFE_OR_TIMEOUT", "completion_preserved":True
        }:
            return fail(f"unexpected collision event: {details['PRECISE_COLLISION_NOT_ACHIEVED']}")
        for name in ("SEQUENCE_RESET_FRESH", "SEQUENCE_REPEAT_RESET_FRESH", "SEQUENCE_SECOND_RESET_FRESH",
                     "PRECISE_INITIAL_RESET_FRESH", "PRECISE_RESET_FRESH", "PRECISE_UNDERSHOOT_RESET_FRESH",
                     "PRECISE_OVERSHOOT_RESET_FRESH", "PRECISE_LATERAL_RESET_FRESH", "PRECISE_COLLISION_RESET_FRESH"):
            if details[name] != {"code": "OUTCOME_UNAVAILABLE"}:
                return fail(f"outcome survived reset at {name}: {details[name]}")
        if details["SEQUENCE_MISSION_TEST_COMPLETE"] != {
            "canonical": "achieved", "repeat": "achieved", "negative": "not-achieved", "alternative": "achieved"
        }:
            return fail(f"unexpected sequence mission summary: {details['SEQUENCE_MISSION_TEST_COMPLETE']}")
        if details["PRECISE_MISSION_TEST_COMPLETE"] != {
            "canonical": "achieved", "undershoot": "not-achieved", "overshoot": "not-achieved",
            "lateral": "not-achieved", "collision": "not-achieved", "alternative": "achieved"
        }:
            return fail(f"unexpected precise mission summary: {details['PRECISE_MISSION_TEST_COMPLETE']}")

        for marker in (
            "WEBEEBLOCKS_SEQUENCE_RESULT attempt=1 status=achieved",
            "WEBEEBLOCKS_SEQUENCE_RESULT attempt=2 status=achieved",
            "WEBEEBLOCKS_SEQUENCE_RESULT attempt=3 status=not-achieved",
            "WEBEEBLOCKS_SEQUENCE_RESULT attempt=4 status=achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=5 status=achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=6 status=not-achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=7 status=not-achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=8 status=not-achieved",
            "WEBEEBLOCKS_PRECISE_COLLISION attempt=9",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=9 status=not-achieved",
            "WEBEEBLOCKS_PRECISE_RESULT attempt=10 status=achieved",
        ):
            if marker not in webots_log:
                return fail(f"missing Webots progression marker: {marker}", webots_log[-14000:])
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-14000:])

        print("PASS progression missions: Activity 1 sequencing plus Activity 2 whole-craft precision, undershoot, overshoot, lateral miss, collision fail-safe, alternative decomposition and reset freshness in real R2025a")
        return 0
    finally:
        cleanup_temp_world()


if __name__ == "__main__":
    raise SystemExit(main())
