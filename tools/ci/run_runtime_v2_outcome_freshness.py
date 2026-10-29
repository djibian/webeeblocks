#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from observe_outcome_startup import validate_capture
from runtime_v2_outcome_assets import prepare as prepare_assets

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "ci-artifacts" / "runtime-v2-outcome-provider"
WEBOTS_IMAGE = "ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca"


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
    print(f"FAIL real R2025a outcome-provider freshness proof: {message}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    return 1


def main() -> int:
    if shutil.which("docker") is None:
        return fail("docker is unavailable")

    shutil.rmtree(ARTIFACT_ROOT, ignore_errors=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    checks = [
        [sys.executable, "tools/ci/test_runtime_v2_outcome_assets.py"],
        [sys.executable, "tools/ci/test_outcome_startup_observer.py"],
        ["node", "--check", "plugins/robot_windows/outcome_probe/outcome_probe.js"],
        [sys.executable, "-m", "py_compile", "controllers/runtime_v2_outcome_probe/runtime_v2_outcome_probe.py"],
    ]
    for command in checks:
        result = run(command, capture=True)
        if result.returncode:
            return fail("probe source validation failed", result.stdout)

    world = (ROOT / "worlds" / "runtime_v2_outcome_probe.wbt").read_text(encoding="utf-8")
    project = (ROOT / "worlds" / ".runtime_v2_outcome_probe.wbproj").read_text(encoding="utf-8")
    for marker in (
        'DEF OUTCOME_CRAZYFLIE Crazyflie',
        'window "outcome_probe"',
        'controller "runtime_v2_outcome_probe"',
    ):
        if marker not in world:
            return fail(f"missing world marker: {marker}")
    if "robotWindow: Crazyflie WebeeBlocks" not in project:
        return fail("probe project does not open the Crazyflie Robot Window")

    pull = run(["docker", "pull", WEBOTS_IMAGE], capture=True)
    if pull.returncode:
        return fail("pinned Webots image could not be prepared", pull.stdout)

    build_log = ARTIFACT_ROOT / "build.log"
    build = run([
        "docker", "run", "--rm",
        "-v", f"{ROOT}:/workspace",
        "-w", "/workspace/controllers/crazyflie_runtime_v2",
        WEBOTS_IMAGE,
        "bash", "-lc", "make clean && make",
    ], capture=True)
    build_log.write_text(build.stdout or "", encoding="utf-8")
    if build.returncode:
        return fail("Runtime v2 controller build failed", (build.stdout or "")[-6000:])

    inner = r'''
set -e
# Fail closed with the failing phase named. wget -q otherwise hides HTTP errors
# and a pre-Webots exit can be mistaken for an outcome freshness failure.
phase=apt_index
trap 'rc=$?; printf "WEBEEBLOCKS_OUTCOME_PROBE_STEP_FAILED phase=%s exit=%d\n" "$phase" "$rc" >&2; exit "$rc"' ERR
python3 /workspace/tools/test_prepare_webots_apt.py
python3 /workspace/tools/prepare_webots_apt.py
apt-get update >/dev/null
phase=apt_packages
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
phase=chrome_download
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
phase=chrome_install
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
phase=webots_setup
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
mkdir -p /workspace/ci-artifacts/runtime-v2-outcome-provider /root/.config/Cyberbotics
printf "%s\n" \
  "[RobotWindow]" \
  "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
  "newBrowserWindow=false" \
  > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py \
  --output /workspace/ci-artifacts/runtime-v2-outcome-provider/browser-events.jsonl &
server=$!
trap "kill $server 2>/dev/null || true" EXIT
sleep 0.5
phase=webots_execution
# Observation only: original timeout, world, oracle and stdout remain unchanged.
# The process monitor is killed on every script exit, including timeout=124.
python3 -u /workspace/tools/ci/observe_outcome_startup.py \
  --output /workspace/ci-artifacts/runtime-v2-outcome-provider/native-startup-processes.jsonl \
  --interval 0.5 --max-samples 84 \
  2>/workspace/ci-artifacts/runtime-v2-outcome-provider/native-startup-observer.err &
startup_observer=$!
trap "kill $startup_observer $server 2>/dev/null || true" EXIT
timeout -k 5s 35s xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/runtime_v2_outcome_probe.wbt
'''.strip()

    env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="webeeblocks-outcome-assets-") as temporary:
        try:
            local_world, projects = prepare_assets(
                Path(temporary) / "assets", ROOT / "worlds/runtime_v2_outcome_probe.wbt",
                ARTIFACT_ROOT / "prepared-assets.json",
            )
        except Exception as exc:
            return fail(f"CI environment preparation / Webots assets (no native launch): {exc}")
        run_result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-e", "LIBGL_ALWAYS_SOFTWARE=true",
                "-e", "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true",
                "-e", "WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/runtime-v2-outcome-provider",
                "-v", f"{ROOT}:/workspace",
                "-v", f"{projects}:/usr/local/webots/projects:ro",
                "-v", f"{local_world}:/workspace/worlds/runtime_v2_outcome_probe.wbt:ro",
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
        return fail(f"Webots probe exited with {run_result.returncode}", webots_log[-6000:])

    event_path = ARTIFACT_ROOT / "browser-events.jsonl"
    if not event_path.exists() or event_path.stat().st_size == 0:
        return fail("missing browser outcome evidence", webots_log[-6000:])
    try:
        events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        return fail(f"invalid browser outcome evidence: {exc}")

    errors = [event for event in events if event.get("event") in ("ERROR", "WINDOW_ERROR", "UNHANDLED_REJECTION")]
    if errors:
        return fail("browser probe reported an error", json.dumps(errors[0], ensure_ascii=False))
    names = [event.get("event") for event in events]
    required = (
        "PROBE_READY",
        "ATTEMPT_A",
        "RESET_OK",
        "NO_STALE_AFTER_RESET",
        "ATTEMPT_B",
        "OUTCOME_PROVIDER_TEST_COMPLETE",
    )
    missing = [name for name in required if name not in names]
    if missing:
        return fail(f"missing causal events: {missing}", json.dumps(names))

    first = next(event["detail"] for event in events if event.get("event") == "ATTEMPT_A")
    stale = next(event["detail"] for event in events if event.get("event") == "NO_STALE_AFTER_RESET")
    second = next(event["detail"] for event in events if event.get("event") == "ATTEMPT_B")
    if first != {"status": "achieved"}:
        return fail(f"unexpected attempt A outcome: {first}")
    if stale != {"code": "OUTCOME_UNAVAILABLE"}:
        return fail(f"stale attempt survived reset: {stale}")
    if second != {"status": "not-achieved"}:
        return fail(f"unexpected attempt B outcome: {second}")
    if "WEBEEBLOCKS_OUTCOME_PROBE publish attempt=1 status=achieved" not in webots_log:
        return fail("attempt A publication is absent from Webots evidence")
    if "WEBEEBLOCKS_OUTCOME_PROBE publish attempt=2 status=not-achieved" not in webots_log:
        return fail("attempt B publication is absent from Webots evidence")
    if "ERROR:" in webots_log:
        return fail("Webots emitted an ERROR line", webots_log[-6000:])

    # The native outcome oracle must remain unchanged, but a successful outcome
    # is not a successful *diagnostic* if the background monitor silently died.
    try:
        validate_capture(ARTIFACT_ROOT / "native-startup-processes.jsonl")
    except ValueError as exc:
        error_path = ARTIFACT_ROOT / "native-startup-observer.err"
        detail = error_path.read_text(encoding="utf-8", errors="replace")[-3000:] if error_path.exists() else None
        return fail(f"startup observer evidence UNPROVEN: {exc}", detail)

    print("PASS real R2025a outcome provider: attempt A terminal -> reset -> no stale terminal -> attempt B terminal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
