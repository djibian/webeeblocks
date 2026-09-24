#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "ci-artifacts" / "progression-combined-decisions-mission"
WEBOTS_IMAGE = "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
TEMP_WORLD = ROOT / "worlds" / "ci_progression_combined_decisions.wbt"
TEMP_PROJECT = ROOT / "worlds" / ".ci_progression_combined_decisions.wbproj"


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def fail(message: str, detail: str | None = None) -> int:
    print(f"FAIL combined-decisions mission evidence: {message}", file=sys.stderr)
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
        ["node", "tools/ci/test_progression_combined_decisions_contract.js"],
        ["node", "--check", "plugins/robot_windows/combined_decisions_probe/combined_decisions_probe.js"],
    ]
    for command in checks:
        checked = run(command, capture=True)
        if checked.returncode:
            return fail("static Activity 6 contract failed", checked.stdout)

    source_world = (ROOT / "worlds" / "crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    for marker in (
        "WEBEEBLOCKS_COMBINED_DECISIONS_MISSION_V1_BEGIN",
        "WEBEEBLOCKS_COMBINED_DECISIONS_ROUTES_V1_BEGIN",
        "WEBEEBLOCKS_COMBINED_DECISIONS_EVALUATOR_V1_BEGIN",
        "DEF ACTIVITY6_FRONT_BARRIER Solid",
        "DEF ACTIVITY6_LEFT_BARRIER Solid",
        "DEF ACTIVITY6_RIGHT_BARRIER Solid",
        'name "Crazyflie WebeeBlocks"',
        'name "Progression combined decisions evaluator"',
        '"combined-decisions-evaluator-v1"',
    ):
        if marker not in source_world:
            return fail(f"missing Activity 6 world marker: {marker}")
    TEMP_WORLD.write_text(
        source_world.replace('window "blockly_v2"', 'window "combined_decisions_probe"', 1),
        encoding="utf-8",
    )
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
            return fail("Runtime v2/Activity 6 evaluator build failed", (built.stdout or "")[-6000:])

        inner = r'''
set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
artifact_dir=/workspace/ci-artifacts/progression-combined-decisions-mission
events="$artifact_dir/browser-events.jsonl"
mkdir -p "$artifact_dir" /root/.config/Cyberbotics
printf "%s\n" \
  "[RobotWindow]" \
  "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
  "newBrowserWindow=false" \
  > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py \
  --output "$events" &
server=$!
trap "kill $server 2>/dev/null || true" EXIT
sleep 0.5
timeout -k 5s 540s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_progression_combined_decisions.wbt &
webots_runner=$!
while kill -0 "$webots_runner" 2>/dev/null; do
  if grep -Fq 'COMBINED_MISSION_TEST_COMPLETE' "$events" 2>/dev/null; then
    kill "$webots_runner" 2>/dev/null || true
    set +e
    wait "$webots_runner"
    set -e
    exit 0
  fi
  sleep 0.25
done
set +e
wait "$webots_runner"
runner_rc=$?
set -e
exit "$runner_rc"
'''.strip()
        result = subprocess.run([
            "docker", "run", "--rm",
            "-e", "LIBGL_ALWAYS_SOFTWARE=true",
            "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
            "-e", "WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/progression-combined-decisions-mission",
            "-v", f"{ROOT}:/workspace", "-w", "/workspace", WEBOTS_IMAGE,
            "bash", "-lc", inner,
        ], cwd=ROOT, env=os.environ.copy(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        webots_log = result.stdout or ""
        (ARTIFACT_ROOT / "webots.log").write_text(webots_log, encoding="utf-8")
        (ARTIFACT_ROOT / "exit-code.txt").write_text(str(result.returncode) + "\n", encoding="utf-8")
        if result.returncode == 124:
            return fail("Webots Activity 6 mission exceeded the 540s proof budget before mission-complete evidence", webots_log[-16000:])
        if result.returncode != 0:
            return fail(f"Webots Activity 6 mission exited with {result.returncode}", webots_log[-16000:])

        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing browser Activity 6 evidence", webots_log[-16000:])
        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid browser Activity 6 evidence: {exc}")
        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            return fail("Activity 6 browser probe reported an error", json.dumps(errors[0], ensure_ascii=False) + "\n" + webots_log[-16000:])

        required = (
            "COMBINED_PROBE_READY",
            "COMBINED_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE",
            "COMBINED_MULTI_OBB_ACHIEVED", "COMBINED_MULTI_OBB_RESET_FRESH",
            "COMBINED_MULTI_BOB_ACHIEVED", "COMBINED_MULTI_BOB_RESET_FRESH",
            "COMBINED_MULTI_BBO_ACHIEVED",
            "COMBINED_SKIP_TO_OBB_FRESH", "COMBINED_SKIP_TO_BOB_FRESH", "COMBINED_FRONT_ONLY_BBO_FRESH",
            "COMBINED_FRONT_ONLY_BBO_NOT_ACHIEVED",
            "COMBINED_FRONT_LEFT_SKIP_OBB_FRESH", "COMBINED_FRONT_LEFT_SKIP_BOB_FRESH", "COMBINED_FRONT_LEFT_BBO_FRESH",
            "COMBINED_FRONT_LEFT_BBO_NOT_ACHIEVED",
            "COMBINED_ALT_OBB_FRESH", "COMBINED_ALT_OBB_ACHIEVED", "COMBINED_ALT_OBB_RESET_FRESH",
            "COMBINED_ALT_BOB_ACHIEVED", "COMBINED_ALT_BOB_RESET_FRESH",
            "COMBINED_ALT_BBO_ACHIEVED", "COMBINED_FINAL_RESET_FRESH",
            "COMBINED_MISSION_TEST_COMPLETE",
        )
        names = [event.get("event") for event in events]
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing causal Activity 6 events: {missing}", json.dumps(names))
        details = {name: next(event["detail"] for event in events if event.get("event") == name) for name in required}
        if details["COMBINED_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE"] != {"code":"OUTCOME_UNAVAILABLE"}:
            return fail(
                "failure probe without irreversible Activity 6 failure synthesized an outcome: "
                + str(details["COMBINED_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE"])
            )
        for name in (
            "COMBINED_MULTI_OBB_ACHIEVED", "COMBINED_MULTI_BOB_ACHIEVED", "COMBINED_MULTI_BBO_ACHIEVED",
            "COMBINED_ALT_OBB_ACHIEVED", "COMBINED_ALT_BOB_ACHIEVED", "COMBINED_ALT_BBO_ACHIEVED",
        ):
            if details[name] != {"status":"achieved"}:
                return fail(f"unexpected achieved event {name}: {details[name]}")
        for name in ("COMBINED_FRONT_ONLY_BBO_NOT_ACHIEVED", "COMBINED_FRONT_LEFT_BBO_NOT_ACHIEVED"):
            if details[name] not in (
                {"status":"not-achieved"},
                {"status":"not-achieved", "runtime_code":"UNSAFE_OR_TIMEOUT"},
            ):
                return fail(f"unexpected negative event {name}: {details[name]}")
        for name in required:
            if (name.endswith("RESET_FRESH") or name.endswith("_FRESH")) and details[name] != {"code":"OUTCOME_UNAVAILABLE"}:
                return fail(f"outcome survived reset at {name}: {details[name]}")
        if details["COMBINED_MISSION_TEST_COMPLETE"] != {
            "multi_obb":"achieved", "multi_bob":"achieved", "multi_bbo":"achieved",
            "front_only_bbo":"not-achieved", "front_left_bbo":"not-achieved",
            "alternate_obb":"achieved", "alternate_bob":"achieved", "alternate_bbo":"achieved",
        }:
            return fail(f"unexpected Activity 6 summary: {details['COMBINED_MISSION_TEST_COMPLETE']}")

        for marker in (
            "WEBEEBLOCKS_COMBINED_CONFIG attempt=1 pattern=OBB-forward",
            "WEBEEBLOCKS_COMBINED_RESULT attempt=1 status=achieved",
            "WEBEEBLOCKS_COMBINED_CONFIG attempt=2 pattern=BOB-left",
            "WEBEEBLOCKS_COMBINED_RESULT attempt=2 status=achieved",
            "WEBEEBLOCKS_COMBINED_CONFIG attempt=3 pattern=BBO-right",
            "WEBEEBLOCKS_COMBINED_RESULT attempt=3 status=achieved",
            "WEBEEBLOCKS_COMBINED_CONFIG attempt=6 pattern=BBO-right",
            "WEBEEBLOCKS_COMBINED_RESULT attempt=6 status=not-achieved",
            "WEBEEBLOCKS_COMBINED_CONFIG attempt=9 pattern=BBO-right",
            "WEBEEBLOCKS_COMBINED_RESULT attempt=9 status=not-achieved",
            "WEBEEBLOCKS_COMBINED_CONFIG attempt=10 pattern=OBB-forward",
            "WEBEEBLOCKS_COMBINED_RESULT attempt=10 status=achieved",
            "WEBEEBLOCKS_COMBINED_CONFIG attempt=11 pattern=BOB-left",
            "WEBEEBLOCKS_COMBINED_RESULT attempt=11 status=achieved",
            "WEBEEBLOCKS_COMBINED_CONFIG attempt=12 pattern=BBO-right",
            "WEBEEBLOCKS_COMBINED_RESULT attempt=12 status=achieved",
        ):
            if marker not in webots_log:
                return fail(f"missing Webots Activity 6 marker: {marker}", webots_log[-16000:])
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-16000:])

        print("PASS Activity 6 warehouse junction: one behavior-only multi-perception strategy succeeds across front/left/right corridor configurations, front-only and front+left shortcuts are refuted on the retained right-corridor case, an equivalent right-first decision structure succeeds, failure probing stays causal, and reset freshness holds in real R2025a")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
