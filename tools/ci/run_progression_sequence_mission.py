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
    print(f"FAIL first progression sequence mission: {message}", file=sys.stderr)
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
            return fail("sequence mission source validation failed", result.stdout)

    source_world = (ROOT / "worlds" / "crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if source_world.count('window "blockly_v2"') != 1:
        return fail("Runtime v2 world Robot Window identity is ambiguous")
    for marker in (
        "WEBEEBLOCKS_SEQUENCE_MISSION_V1_BEGIN",
        "DEF CRAZYFLIE Crazyflie",
        'controller "progression_sequence_evaluator"',
    ):
        if marker not in source_world:
            return fail(f"missing sequence world marker: {marker}")
    TEMP_WORLD.write_text(source_world.replace('window "blockly_v2"', 'window "sequence_probe"', 1), encoding="utf-8")
    TEMP_PROJECT.write_text(
        "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n",
        encoding="utf-8",
    )

    try:
        pull = run(["docker", "pull", WEBOTS_IMAGE], capture=True)
        if pull.returncode:
            return fail("pinned Webots image could not be prepared", pull.stdout)

        build_logs = []
        for controller in ("crazyflie_runtime_v2", "progression_sequence_evaluator"):
            built = run([
                "docker", "run", "--rm",
                "-v", f"{ROOT}:/workspace",
                "-w", f"/workspace/controllers/{controller}",
                WEBOTS_IMAGE,
                "bash", "-lc", "make clean && make",
            ], capture=True)
            build_logs.append(f"===== {controller} =====\n{built.stdout or ''}")
            if built.returncode:
                (ARTIFACT_ROOT / "build.log").write_text("\n".join(build_logs), encoding="utf-8")
                return fail(f"{controller} build failed", (built.stdout or "")[-6000:])
        (ARTIFACT_ROOT / "build.log").write_text("\n".join(build_logs), encoding="utf-8")

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
timeout -k 5s 50s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_progression_sequence.wbt
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
            return fail(f"Webots sequence mission exited with {run_result.returncode}", webots_log[-6000:])

        event_path = ARTIFACT_ROOT / "browser-events.jsonl"
        if not event_path.exists() or event_path.stat().st_size == 0:
            return fail("missing browser sequence evidence", webots_log[-6000:])
        try:
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as exc:
            return fail(f"invalid browser sequence evidence: {exc}")

        errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
        if errors:
            return fail("browser sequence probe reported an error", json.dumps(errors[0], ensure_ascii=False))
        names = [event.get("event") for event in events]
        required = (
            "SEQUENCE_PROBE_READY",
            "SEQUENCE_ACHIEVED",
            "SEQUENCE_RESET_FRESH",
            "SEQUENCE_NOT_ACHIEVED",
            "SEQUENCE_MISSION_TEST_COMPLETE",
        )
        missing = [name for name in required if name not in names]
        if missing:
            return fail(f"missing causal sequence events: {missing}", json.dumps(names))

        achieved = next(event["detail"] for event in events if event.get("event") == "SEQUENCE_ACHIEVED")
        fresh = next(event["detail"] for event in events if event.get("event") == "SEQUENCE_RESET_FRESH")
        not_achieved = next(event["detail"] for event in events if event.get("event") == "SEQUENCE_NOT_ACHIEVED")
        if achieved != {"status": "achieved"}:
            return fail(f"unexpected target-zone outcome: {achieved}")
        if fresh != {"code": "OUTCOME_UNAVAILABLE"}:
            return fail(f"sequence outcome survived reset: {fresh}")
        if not_achieved != {"status": "not-achieved"}:
            return fail(f"unexpected start-zone landing outcome: {not_achieved}")
        if "WEBEEBLOCKS_SEQUENCE_RESULT attempt=1 status=achieved" not in webots_log:
            return fail("target-zone achievement publication is absent from Webots evidence")
        if "WEBEEBLOCKS_SEQUENCE_RESULT attempt=2 status=not-achieved" not in webots_log:
            return fail("off-target terminal publication is absent from Webots evidence")
        if "ERROR:" in webots_log:
            return fail("Webots emitted an ERROR line", webots_log[-6000:])

        print("PASS first progression sequence mission: observable target-zone success, off-target failure, and reset-fresh outcome in real R2025a")
        return 0
    finally:
        cleanup_temp_world()


if __name__ == "__main__":
    raise SystemExit(main())
