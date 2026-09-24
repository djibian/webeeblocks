#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "ci-artifacts" / "progression-memory-mission"
WEBOTS_IMAGE = "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
TEMP_WORLD = ROOT / "worlds" / "ci_progression_memory.wbt"
TEMP_PROJECT = ROOT / "worlds" / ".ci_progression_memory.wbproj"


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def fail(message: str, detail: str | None = None) -> int:
    print(f"FAIL memory mission evidence: {message}", file=sys.stderr)
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
        ["node", "tools/ci/test_progression_memory_contract.js"],
        ["node", "--check", "plugins/robot_windows/memory_probe/memory_probe.js"],
    ]
    for command in checks:
        checked = run(command, capture=True)
        if checked.returncode:
            return fail("static Activity 7 contract failed", checked.stdout)

    source_world = (ROOT / "worlds" / "crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    for marker in (
        'name "Crazyflie WebeeBlocks"',
        'name "Progression combined decisions evaluator"',
        '"combined-decisions-evaluator-v1"',
    ):
        if marker not in source_world:
            return fail(f"missing shared evaluator world marker: {marker}")
    TEMP_WORLD.write_text(
        source_world.replace('window "blockly_v2"', 'window "memory_probe"', 1),
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
            return fail("Runtime v2/Activity 7 evaluator build failed", (built.stdout or "")[-6000:])

        inner = r'''
set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
artifact_dir=/workspace/ci-artifacts/progression-memory-mission
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
timeout -k 5s 540s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_progression_memory.wbt &
webots_runner=$!
while kill -0 "$webots_runner" 2>/dev/null; do
  if grep -Fq 'MEMORY_MISSION_TEST_COMPLETE' "$events" 2>/dev/null; then
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
            "-e", "WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/progression-memory-mission",
            "-v", f"{ROOT}:/workspace", "-w", "/workspace", WEBOTS_IMAGE,
            "bash", "-lc", inner,
        ], cwd=ROOT, env=os.environ.copy(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        webots_log = result.stdout or ""
        (ARTIFACT_ROOT / "webots.log").write_text(webots_log, encoding="utf-8")
        (ARTIFACT_ROOT / "exit-code.txt").write_text(str(result.returncode) + "\n", encoding="utf-8")
        if result.returncode == 124:
            return fail("Webots Activity 7 mission exceeded the 540s proof budget before mission-complete evidence", webots_log[-16000:])
        if result.returncode != 0:
            return fail(f"Webots Activity 7 mission exited with {result.returncode}", webots_log[-16000:])

        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing browser Activity 7 evidence", webots_log[-16000:])
        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid browser Activity 7 evidence: {exc}")
        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            return fail("Activity 7 browser probe reported an error", json.dumps(errors[0], ensure_ascii=False) + "\n" + webots_log[-16000:])

        required = (
            "MEMORY_PROBE_READY",
            "MEMORY_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE",
            "MEMORY_STORED_SMALL_ACHIEVED", "MEMORY_STORED_SMALL_RESET_FRESH",
            "MEMORY_STORED_LARGE_ACHIEVED",
            "MEMORY_REREAD_SMALL_FRESH", "MEMORY_REREAD_SMALL_ACHIEVED",
            "MEMORY_REREAD_LARGE_FRESH", "MEMORY_REREAD_LARGE_NOT_ACHIEVED",
            "MEMORY_ALT_SMALL_FRESH", "MEMORY_ALT_SMALL_ACHIEVED", "MEMORY_ALT_SMALL_RESET_FRESH",
            "MEMORY_ALT_LARGE_ACHIEVED", "MEMORY_FINAL_RESET_FRESH",
            "MEMORY_MISSION_TEST_COMPLETE",
        )
        names = [event.get("event") for event in events]
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing causal Activity 7 events: {missing}", json.dumps(names))
        details = {name: next(event["detail"] for event in events if event.get("event") == name) for name in required}
        if details["MEMORY_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE"] != {"code":"OUTCOME_UNAVAILABLE"}:
            return fail(
                "failure probe without irreversible Activity 7 failure synthesized an outcome: "
                + str(details["MEMORY_FAILURE_PROBE_WITHOUT_FAILURE_UNAVAILABLE"])
            )
        for name in (
            "MEMORY_STORED_SMALL_ACHIEVED", "MEMORY_STORED_LARGE_ACHIEVED",
            "MEMORY_REREAD_SMALL_ACHIEVED",
            "MEMORY_ALT_SMALL_ACHIEVED", "MEMORY_ALT_LARGE_ACHIEVED",
        ):
            if details[name] != {"status":"achieved"}:
                return fail(f"unexpected achieved event {name}: {details[name]}")
        if details["MEMORY_REREAD_LARGE_NOT_ACHIEVED"] not in (
            {"status":"not-achieved"},
            {"status":"not-achieved", "runtime_code":"UNSAFE_OR_TIMEOUT"},
        ):
            return fail(f"unexpected negative reread event: {details['MEMORY_REREAD_LARGE_NOT_ACHIEVED']}")
        for name in required:
            if (name.endswith("RESET_FRESH") or name.endswith("_FRESH")) and details[name] != {"code":"OUTCOME_UNAVAILABLE"}:
                return fail(f"outcome survived reset at {name}: {details[name]}")
        if details["MEMORY_MISSION_TEST_COMPLETE"] != {
            "stored_small":"achieved",
            "stored_large":"achieved",
            "reread_small":"achieved",
            "reread_large":"not-achieved",
            "alternate_small":"achieved",
            "alternate_large":"achieved",
        }:
            return fail(f"unexpected Activity 7 summary: {details['MEMORY_MISSION_TEST_COMPLETE']}")

        for marker in (
            "WEBEEBLOCKS_MEMORY_CONFIG attempt=1 pattern=small-far",
            "WEBEEBLOCKS_MEMORY_REFERENCE_UNAVAILABLE attempt=1",
            "WEBEEBLOCKS_MEMORY_RESULT attempt=1 status=achieved",
            "WEBEEBLOCKS_MEMORY_CONFIG attempt=2 pattern=large-near",
            "WEBEEBLOCKS_MEMORY_RESULT attempt=2 status=achieved",
            "WEBEEBLOCKS_MEMORY_CONFIG attempt=3 pattern=small-far",
            "WEBEEBLOCKS_MEMORY_RESULT attempt=3 status=achieved",
            "WEBEEBLOCKS_MEMORY_CONFIG attempt=4 pattern=large-near",
            "WEBEEBLOCKS_MEMORY_RESULT attempt=4 status=not-achieved",
            "WEBEEBLOCKS_MEMORY_CONFIG attempt=5 pattern=small-far",
            "WEBEEBLOCKS_MEMORY_RESULT attempt=5 status=achieved",
            "WEBEEBLOCKS_MEMORY_CONFIG attempt=6 pattern=large-near",
            "WEBEEBLOCKS_MEMORY_RESULT attempt=6 status=achieved",
        ):
            if marker not in webots_log:
                return fail(f"missing Webots Activity 7 marker: {marker}", webots_log[-16000:])
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-16000:])

        print("PASS Activity 7 parcel memory: stored departure range succeeds across small/large parcel configurations and both downstream sorting choices, immediate downstream rereading fails to generalize once the reference is gone, an equivalent stored comparison succeeds, failure probing stays causal, and reset freshness holds in real R2025a")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
