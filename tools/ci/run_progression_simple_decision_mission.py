#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "ci-artifacts" / "progression-simple-decision-mission"
WEBOTS_IMAGE = "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
TEMP_WORLD = ROOT / "worlds" / "ci_progression_simple_decision.wbt"
TEMP_PROJECT = ROOT / "worlds" / ".ci_progression_simple_decision.wbproj"


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def fail(message: str, detail: str | None = None) -> int:
    print(f"FAIL simple-decision mission evidence: {message}", file=sys.stderr)
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
        ["node", "tools/ci/test_progression_simple_decision_contract.js"],
        ["node", "--check", "plugins/robot_windows/simple_decision_probe/simple_decision_probe.js"],
    ]
    for command in checks:
        checked = run(command, capture=True)
        if checked.returncode:
            return fail("static Activity 4 contract failed", checked.stdout)

    source_world = (ROOT / "worlds" / "crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    for marker in (
        "WEBEEBLOCKS_SIMPLE_DECISION_MISSION_V1_BEGIN",
        "WEBEEBLOCKS_SIMPLE_DECISION_PASSAGES_V1_BEGIN",
        "WEBEEBLOCKS_SIMPLE_DECISION_EVALUATOR_V1_BEGIN",
        "DEF ACTIVITY4_BARRIER Solid",
        'name "Crazyflie WebeeBlocks"',
        'name "Progression simple decision evaluator"',
        '"simple-decision-evaluator-v1"',
    ):
        if marker not in source_world:
            return fail(f"missing Activity 4 world marker: {marker}")
    TEMP_WORLD.write_text(source_world.replace('window "blockly_v2"', 'window "simple_decision_probe"', 1), encoding="utf-8")
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
            return fail("Runtime v2/Activity 4 evaluator build failed", (built.stdout or "")[-6000:])

        inner = r'''
set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
mkdir -p /workspace/ci-artifacts/progression-simple-decision-mission /root/.config/Cyberbotics
printf "%s\n" \
  "[RobotWindow]" \
  "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
  "newBrowserWindow=false" \
  > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py \
  --output /workspace/ci-artifacts/progression-simple-decision-mission/browser-events.jsonl &
server=$!
trap "kill $server 2>/dev/null || true" EXIT
sleep 0.5
timeout -k 5s 300s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_progression_simple_decision.wbt
'''.strip()
        result = subprocess.run([
            "docker", "run", "--rm",
            "-e", "LIBGL_ALWAYS_SOFTWARE=true",
            "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
            "-e", "WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/progression-simple-decision-mission",
            "-v", f"{ROOT}:/workspace", "-w", "/workspace", WEBOTS_IMAGE,
            "bash", "-lc", inner,
        ], cwd=ROOT, env=os.environ.copy(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        webots_log = result.stdout or ""
        (ARTIFACT_ROOT / "webots.log").write_text(webots_log, encoding="utf-8")
        (ARTIFACT_ROOT / "exit-code.txt").write_text(str(result.returncode) + "\n", encoding="utf-8")
        if result.returncode not in (0, 124):
            return fail(f"Webots Activity 4 mission exited with {result.returncode}", webots_log[-14000:])

        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing browser Activity 4 evidence", webots_log[-14000:])
        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid browser Activity 4 evidence: {exc}")
        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            return fail("Activity 4 browser probe reported an error", json.dumps(errors[0], ensure_ascii=False) + "\n" + webots_log[-14000:])

        required = (
            "DECISION_PROBE_READY",
            "DECISION_BLOCKED_ACHIEVED", "DECISION_BLOCKED_RESET_FRESH",
            "DECISION_OPEN_ACHIEVED", "DECISION_OPEN_RESET_FRESH",
            "DECISION_HARDCODED_FORWARD_NOT_ACHIEVED", "DECISION_FORWARD_RESET_FRESH",
            "DECISION_HARDCODED_LEFT_NOT_ACHIEVED", "DECISION_LEFT_RESET_FRESH",
            "DECISION_ALTERNATIVE_BLOCKED_ACHIEVED", "DECISION_ALT_BLOCKED_RESET_FRESH",
            "DECISION_ALTERNATIVE_OPEN_ACHIEVED", "DECISION_ALT_OPEN_RESET_FRESH",
            "DECISION_WRONG_DECISION_NOT_ACHIEVED", "DECISION_WRONG_RESET_FRESH",
            "DECISION_BYPASS_NOT_ACHIEVED",
            "DECISION_MISSION_TEST_COMPLETE",
        )
        names = [event.get("event") for event in events]
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing causal Activity 4 events: {missing}", json.dumps(names))
        details = {name: next(event["detail"] for event in events if event.get("event") == name) for name in required}
        for name in (
            "DECISION_BLOCKED_ACHIEVED", "DECISION_OPEN_ACHIEVED",
            "DECISION_ALTERNATIVE_BLOCKED_ACHIEVED", "DECISION_ALTERNATIVE_OPEN_ACHIEVED",
        ):
            if details[name] != {"status":"achieved"}:
                return fail(f"unexpected achieved event {name}: {details[name]}")
        for name in (
            "DECISION_HARDCODED_FORWARD_NOT_ACHIEVED",
            "DECISION_HARDCODED_LEFT_NOT_ACHIEVED",
            "DECISION_WRONG_DECISION_NOT_ACHIEVED",
        ):
            if details[name] != {"status":"not-achieved", "runtime_code":"UNSAFE_OR_TIMEOUT"}:
                return fail(f"unexpected negative event {name}: {details[name]}")
        if details["DECISION_BYPASS_NOT_ACHIEVED"] != {"status":"not-achieved"}:
            return fail(f"explicit-passage bypass was not rejected by mission state: {details['DECISION_BYPASS_NOT_ACHIEVED']}")
        for name in (
            "DECISION_BLOCKED_RESET_FRESH", "DECISION_OPEN_RESET_FRESH", "DECISION_FORWARD_RESET_FRESH",
            "DECISION_LEFT_RESET_FRESH", "DECISION_ALT_BLOCKED_RESET_FRESH", "DECISION_ALT_OPEN_RESET_FRESH",
            "DECISION_WRONG_RESET_FRESH",
        ):
            if details[name] != {"code":"OUTCOME_UNAVAILABLE"}:
                return fail(f"outcome survived reset at {name}: {details[name]}")
        if details["DECISION_MISSION_TEST_COMPLETE"] != {
            "blocked":"achieved", "open":"achieved", "hard_forward":"not-achieved",
            "hard_left":"not-achieved", "alternative_blocked":"achieved",
            "alternative_open":"achieved", "wrong_decision":"not-achieved",
            "bypass":"not-achieved"
        }:
            return fail(f"unexpected Activity 4 summary: {details['DECISION_MISSION_TEST_COMPLETE']}")

        for marker in (
            "WEBEEBLOCKS_DECISION_CONFIG attempt=1 state=forward-blocked",
            "WEBEEBLOCKS_DECISION_RESULT attempt=1 status=achieved",
            "WEBEEBLOCKS_DECISION_CONFIG attempt=2 state=forward-open",
            "WEBEEBLOCKS_DECISION_RESULT attempt=2 status=achieved",
            "WEBEEBLOCKS_DECISION_RESULT attempt=3 status=not-achieved",
            "WEBEEBLOCKS_DECISION_RESULT attempt=4 status=not-achieved",
            "WEBEEBLOCKS_DECISION_RESULT attempt=5 status=achieved",
            "WEBEEBLOCKS_DECISION_RESULT attempt=6 status=achieved",
            "WEBEEBLOCKS_DECISION_RESULT attempt=7 status=not-achieved",
            "WEBEEBLOCKS_DECISION_RESULT attempt=8 status=not-achieved",
        ):
            if marker not in webots_log:
                return fail(f"missing Webots Activity 4 marker: {marker}", webots_log[-14000:])
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-14000:])

        print("PASS Activity 4 mobile door: one shared sensing/decision program succeeds in both deterministic configurations, fixed/wrong decisions and an explicit-passage bypass fail, alternative behavior succeeds, and reset freshness holds in real R2025a")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
