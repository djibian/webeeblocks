#!/usr/bin/env python3
"""Prove the packaged Runtime v2 controller enters the Webots R2025a runtime.

This is a no-hardware oracle.  It launches only the simulation world/controller
from an exact physical-qualification bundle, with the Robot Window browser
suppressed.  It never starts the physical host, opens Crazyradio, prepares a
student program or creates execution authority.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time


class PackagedControllerRuntimeError(RuntimeError):
    """The exact packaged controller did not establish a stable R2025a runtime."""


def _copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise PackagedControllerRuntimeError(f"required packaged directory missing: {source}")
    shutil.copytree(source, target, symlinks=False)


def _copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise PackagedControllerRuntimeError(f"required packaged file missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _controller_pid(expected_executable: Path) -> int | None:
    expected = expected_executable.resolve()
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        raise PackagedControllerRuntimeError("Linux /proc is required for controller runtime proof")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            executable = Path(os.readlink(entry / "exe")).resolve()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if executable == expected:
            return int(entry.name)
    return None


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5.0)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=5.0)


def _log_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "<Webots log unavailable>"


def verify_runtime(
    bundle: Path,
    *,
    webots_executable: str,
    startup_timeout: float,
    stability_seconds: float,
) -> None:
    bundle = bundle.resolve()
    if not bundle.is_dir():
        raise PackagedControllerRuntimeError(f"qualification bundle missing: {bundle}")
    if startup_timeout <= 0 or stability_seconds <= 0:
        raise PackagedControllerRuntimeError("runtime proof timeouts must be positive")

    webots = shutil.which(webots_executable)
    if webots is None:
        candidate = Path(webots_executable)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            webots = str(candidate.resolve())
        else:
            raise PackagedControllerRuntimeError("Webots executable unavailable")
    xvfb = shutil.which("xvfb-run")
    if xvfb is None:
        raise PackagedControllerRuntimeError("xvfb-run is required for deterministic R2025a smoke")

    version = subprocess.run(
        [xvfb, "-a", webots, "--version"],
        text=True,
        capture_output=True,
        timeout=15.0,
    )
    version_text = (version.stdout + version.stderr).strip()
    if version.returncode != 0 or "R2025a" not in version_text:
        raise PackagedControllerRuntimeError(
            "exact Webots R2025a required, observed: " + (version_text or "<no version>")
        )

    required_file = (
        bundle / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2",
        bundle / "controllers/crazyflie_runtime_v2/runtime.ini",
        bundle / "worlds/crazyflie_runtime_v2.wbt",
        bundle / "tools/physical/qualification_crazyflie_r2025a.proto",
    )
    for path in required_file:
        if not path.is_file():
            raise PackagedControllerRuntimeError(f"required packaged runtime file missing: {path}")

    with tempfile.TemporaryDirectory(prefix="webeeblocks-packaged-runtime-") as temp_text:
        temp = Path(temp_text)
        project = temp / "qualification"
        project.mkdir()
        _copy_tree(bundle / "controllers", project / "controllers")
        _copy_tree(bundle / "plugins", project / "plugins")
        _copy_tree(bundle / "worlds", project / "worlds")
        _copy_file(
            bundle / "tools/physical/qualification_crazyflie_r2025a.proto",
            project / "tools/physical/qualification_crazyflie_r2025a.proto",
        )

        expected_controller = project / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2"
        expected_controller.chmod(expected_controller.stat().st_mode | 0o100)

        home = temp / "home"
        config = home / ".config/Cyberbotics/Webots-R2025a.conf"
        config.parent.mkdir(parents=True)
        config.write_text(
            "[RobotWindow]\n"
            "browser=/bin/true\n"
            "newBrowserWindow=false\n",
            encoding="utf-8",
        )
        log_path = temp / "webots.log"
        env = os.environ.copy()
        env["HOME"] = str(home)

        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [
                    xvfb,
                    "-a",
                    webots,
                    "--stdout",
                    "--stderr",
                    "--batch",
                    "--mode=realtime",
                    str(project / "worlds/crazyflie_runtime_v2.wbt"),
                ],
                cwd=project,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            deadline = time.monotonic() + startup_timeout
            controller_pid: int | None = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise PackagedControllerRuntimeError(
                        "Webots exited before packaged controller startup\n" + _log_text(log_path)
                    )
                controller_pid = _controller_pid(expected_controller)
                if controller_pid is not None:
                    break
                time.sleep(0.1)
            if controller_pid is None:
                raise PackagedControllerRuntimeError(
                    "packaged crazyflie_runtime_v2 never entered R2025a controller runtime\n"
                    + _log_text(log_path)
                )

            stable_until = time.monotonic() + stability_seconds
            while time.monotonic() < stable_until:
                if process.poll() is not None:
                    raise PackagedControllerRuntimeError(
                        "Webots exited during packaged controller stability window\n"
                        + _log_text(log_path)
                    )
                if _controller_pid(expected_controller) != controller_pid:
                    raise PackagedControllerRuntimeError(
                        "packaged crazyflie_runtime_v2 did not remain alive in R2025a runtime\n"
                        + _log_text(log_path)
                    )
                time.sleep(0.1)
        finally:
            _terminate_process_group(process)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="No-hardware smoke for the exact packaged Runtime v2 controller"
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--webots", default="webots")
    parser.add_argument("--startup-timeout", type=float, default=15.0)
    parser.add_argument("--stability-seconds", type=float, default=2.0)
    args = parser.parse_args(argv)
    try:
        verify_runtime(
            args.bundle,
            webots_executable=args.webots,
            startup_timeout=args.startup_timeout,
            stability_seconds=args.stability_seconds,
        )
    except (PackagedControllerRuntimeError, OSError, subprocess.SubprocessError) as exc:
        print("FAIL: packaged R2025a controller runtime: " + str(exc), file=os.sys.stderr)
        return 1
    print("PASS: exact packaged crazyflie_runtime_v2 entered stable Webots R2025a controller runtime without hardware")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
