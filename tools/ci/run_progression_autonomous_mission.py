#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "ci-artifacts" / "progression-autonomous-mission"
WEBOTS_IMAGE = "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
TEMP_WORLD = ROOT / "worlds" / "ci_progression_autonomous.wbt"
TEMP_PROJECT = ROOT / "worlds" / ".ci_progression_autonomous.wbproj"


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def fail(message: str, detail: str | None = None) -> int:
    print(f"FAIL Activity 8 autonomous mission evidence: {message}", file=sys.stderr)
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

    checks = (
        ["node", "tools/ci/test_progression_autonomous_contract.js"],
        ["node", "--check", "plugins/robot_windows/autonomous_probe/autonomous_probe.js"],
    )
    for command in checks:
        checked = run(list(command), capture=True)
        if checked.returncode:
            return fail("static Activity 8 contract failed", checked.stdout)

    source_world = (ROOT / "worlds" / "crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    for marker in (
        'name "Crazyflie WebeeBlocks"',
        'name "Progression combined decisions evaluator"',
        '"combined-decisions-evaluator-v1"',
        'name "Progression autonomous strategy evaluator"',
        '"autonomous-evaluator-v1"',
    ):
        if marker not in source_world:
            return fail(f"missing Activity 8 evaluator world marker: {marker}")
    TEMP_WORLD.write_text(
        source_world.replace('window "blockly_v2"', 'window "autonomous_probe"', 1),
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
            return fail("Runtime v2/Activity 8 evaluator build failed", (built.stdout or "")[-6000:])

        inner = r'''
set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
artifact_dir=/workspace/ci-artifacts/progression-autonomous-mission
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
# Activity 8 proves simulated mission state, not wall-clock pacing. Fast mode
# preserves the same deterministic 32 ms steps while keeping the real rendered
# Robot Window/browser lifecycle that carries Runtime-v2 commands.
timeout -k 5s 1500s xvfb-run -a webots --stdout --stderr --batch --mode=fast /workspace/worlds/ci_progression_autonomous.wbt &
webots_runner=$!
while kill -0 "$webots_runner" 2>/dev/null; do
  if grep -Fq 'AUTONOMOUS_MISSION_TEST_COMPLETE' "$events" 2>/dev/null; then
    kill "$webots_runner" 2>/dev/null || true
    set +e
    wait "$webots_runner"
    set -e
    exit 0
  fi
  if grep -Eq '"event"[[:space:]]*:[[:space:]]*"(ERROR|WINDOW_ERROR|UNHANDLED_REJECTION)"' "$events" 2>/dev/null; then
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
            "-e", "WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/progression-autonomous-mission",
            "-v", f"{ROOT}:/workspace", "-w", "/workspace", WEBOTS_IMAGE,
            "bash", "-lc", inner,
        ], cwd=ROOT, env=os.environ.copy(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        webots_log = result.stdout or ""
        (ARTIFACT_ROOT / "webots.log").write_text(webots_log, encoding="utf-8")
        (ARTIFACT_ROOT / "exit-code.txt").write_text(str(result.returncode) + "\n", encoding="utf-8")
        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if result.returncode == 124:
            detail = webots_log[-16000:]
            if event_path.exists():
                detail += "\nBROWSER EVENTS AT TIMEOUT:\n" + event_path.read_text(encoding="utf-8")[-10000:]
            return fail("Webots Activity 8 proof exceeded the 1500s local budget", detail)
        if result.returncode != 0:
            return fail(f"Webots Activity 8 proof exited with {result.returncode}", webots_log[-16000:])
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing Activity 8 browser evidence", webots_log[-16000:])

        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid Activity 8 browser evidence: {exc}")
        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            return fail("Activity 8 browser probe reported an error", json.dumps(errors[0], ensure_ascii=False) + "\n" + webots_log[-16000:])

        required = (
            "AUTONOMOUS_PROBE_READY",
            "AUTONOMOUS_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE",
            "AUTONOMOUS_INTEGRATED_SMALL_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_SMALL_BE_FORWARD_RESET_FRESH",
            "AUTONOMOUS_INTEGRATED_LARGE_EB_LEFT_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_LARGE_EB_LEFT_RESET_FRESH",
            "AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_RESET_FRESH",
            "AUTONOMOUS_INTEGRATED_LARGE_EE_FORWARD_ACHIEVED",
            "AUTONOMOUS_FIXED_ROUTE_FRESH",
            "AUTONOMOUS_FIXED_ROUTE_NOT_ACHIEVED",
            "AUTONOMOUS_NO_MEMORY_FRESH",
            "AUTONOMOUS_NO_MEMORY_LARGE_NOT_ACHIEVED",
            "AUTONOMOUS_FRONT_ONLY_FRESH",
            "AUTONOMOUS_FRONT_ONLY_RIGHT_NOT_ACHIEVED",
            "AUTONOMOUS_INCOMPLETE_FRESH",
            "AUTONOMOUS_INCOMPLETE_NOT_ACHIEVED",
            "AUTONOMOUS_ALT_SMALL_BE_FORWARD_FRESH",
            "AUTONOMOUS_ALT_SMALL_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_ALT_LARGE_EB_LEFT_FRESH",
            "AUTONOMOUS_ALT_LARGE_EB_LEFT_ACHIEVED",
            "AUTONOMOUS_ALT_SMALL_BB_RIGHT_FRESH",
            "AUTONOMOUS_ALT_SMALL_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_ALT_LARGE_EE_FORWARD_FRESH",
            "AUTONOMOUS_ALT_LARGE_EE_FORWARD_ACHIEVED",
            "AUTONOMOUS_FINAL_RESET_FRESH",
            "AUTONOMOUS_MISSION_TEST_COMPLETE",
        )
        names = [event.get("event") for event in events]
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing Activity 8 causal events: {missing}", json.dumps(names))
        details = {name: next(event["detail"] for event in events if event.get("event") == name) for name in required}
        if details["AUTONOMOUS_PROBE_READY"] != {"ready": True}:
            return fail(f"Activity 8 probe did not become ready: {details['AUTONOMOUS_PROBE_READY']}")
        if details["AUTONOMOUS_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE"] != {"code":"OUTCOME_UNAVAILABLE"}:
            return fail("Activity 8 failure probe synthesized an outcome without irreversible failure")
        for fresh in (name for name in required if name.endswith("_FRESH")):
            if details[fresh] != {"code":"OUTCOME_UNAVAILABLE"}:
                return fail(f"outcome survived reset at {fresh}: {details[fresh]}")

        for achieved in (
            "AUTONOMOUS_INTEGRATED_SMALL_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_LARGE_EB_LEFT_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_SMALL_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_INTEGRATED_LARGE_EE_FORWARD_ACHIEVED",
            "AUTONOMOUS_ALT_SMALL_BE_FORWARD_ACHIEVED",
            "AUTONOMOUS_ALT_LARGE_EB_LEFT_ACHIEVED",
            "AUTONOMOUS_ALT_SMALL_BB_RIGHT_ACHIEVED",
            "AUTONOMOUS_ALT_LARGE_EE_FORWARD_ACHIEVED",
        ):
            if details[achieved] != {"status":"achieved"}:
                return fail(f"unexpected achieved Activity 8 event {achieved}: {details[achieved]}")
        for negative in (
            "AUTONOMOUS_FIXED_ROUTE_NOT_ACHIEVED",
            "AUTONOMOUS_FRONT_ONLY_RIGHT_NOT_ACHIEVED",
        ):
            if details[negative] not in (
                {"status":"not-achieved"},
                {"status":"not-achieved", "runtime_code":"UNSAFE_OR_TIMEOUT"},
            ):
                return fail(f"unexpected causal Activity 8 failure {negative}: {details[negative]}")
        for ordinary_negative in (
            "AUTONOMOUS_NO_MEMORY_LARGE_NOT_ACHIEVED",
            "AUTONOMOUS_INCOMPLETE_NOT_ACHIEVED",
        ):
            if details[ordinary_negative] != {"status":"not-achieved"}:
                return fail(f"unexpected completed Activity 8 failure {ordinary_negative}: {details[ordinary_negative]}")
        if details["AUTONOMOUS_MISSION_TEST_COMPLETE"] != {
            "integrated":["achieved", "achieved", "achieved", "achieved"],
            "fixed_route":"not-achieved",
            "no_memory":"not-achieved",
            "front_only":"not-achieved",
            "incomplete":"not-achieved",
            "alternate":["achieved", "achieved", "achieved", "achieved"],
        }:
            return fail(f"unexpected Activity 8 summary: {details['AUTONOMOUS_MISSION_TEST_COMPLETE']}")

        markers = (
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=1 pattern=small-BE-forward",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=1 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=2 pattern=large-EB-left",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=2 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=3 pattern=small-BB-right",
            "WEBEEBLOCKS_AUTONOMOUS_ROUTE attempt=3 route=right valid=1",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=3 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=4 pattern=large-EE-forward",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=4 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=5 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=6 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_ROUTE attempt=7 route=left valid=0",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=7 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_TIMEOUT attempt=8",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=8 status=not-achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=9 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=10 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=11 status=achieved",
            "WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=12 status=achieved",
        )
        for marker in markers:
            if marker not in webots_log:
                return fail(f"missing Activity 8 Webots marker: {marker}", webots_log[-16000:])
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-16000:])

        print("PASS Activity 8 autonomous synthesis: one integrated strategy succeeds across the four retained parcel/row/junction configurations, a structurally distinct stored-value strategy is also accepted, and fixed-route, no-memory, front-only and incomplete shortcuts fail from observable world state in real R2025a")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
