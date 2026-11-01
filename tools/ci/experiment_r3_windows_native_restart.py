#!/usr/bin/env python3
"""Experiment only: genuine Windows Webots process restart, not Robot Window GUI acceptance.

Exact #778 product bytes are unchanged. Failure to observe a real native ready
or normal GUI shutdown is NOT silently reclassified as a successful test.
No Chromium/WebSocket/Blockly/authorization claim is made by this probe.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

EXPECTED_BASE = "f243b2b597a2a6bd6af38e895787d9dd4bdfef5e"
WM_CLOSE = 0x0010


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gui_windows(pid):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    matches = []
    cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @cb_type
    def each(hwnd, ignored):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            length = user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, length + 1)
            matches.append({"hwnd": int(hwnd), "title": buf.value})
        return True

    user32.EnumWindows(each, 0)
    return matches


def launch_once(exe, world, directory, state_dir, index):
    output = directory / f"webots-{index}.stdout.log"
    errors = directory / f"webots-{index}.stderr.log"
    env = os.environ.copy()
    home = exe.parents[3]  # WEBOTS_HOME/msys64/mingw64/bin/webots.exe
    env["WEBOTS_HOME"] = str(home)
    env["WEBEEBLOCKS_RECOVERY_STATE_DIR"] = str(state_dir)
    env["PATH"] = os.pathsep.join([str(home / "msys64/mingw64/bin"),
                                   str(home / "msys64/usr/bin"), env.get("PATH", "")])
    env.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
    args = [str(exe), "--stdout", "--stderr", "--mode=realtime", str(world)]
    record = {"run": index, "command": args, "state_dir": str(state_dir),
              "world": str(world), "start_utc": time.time(), "native_ready": False,
              "gui_window_observed": False, "normal_shutdown": False}
    with output.open("wb") as out, errors.open("wb") as err:
        process = subprocess.Popen(args, cwd=world.parent, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        record["pid"] = process.pid
        def pump(src, dest):
            with src:
                while True:
                    chunk = src.read(8192)
                    if not chunk:
                        break
                    dest.write(chunk)
                    dest.flush()
        jobs = [threading.Thread(target=pump, args=(process.stdout, out), daemon=True),
                threading.Thread(target=pump, args=(process.stderr, err), daemon=True)]
        for job in jobs:
            job.start()
        try:
            deadline = time.monotonic() + 85
            window = []
            while time.monotonic() < deadline and process.poll() is None:
                data = output.read_text(encoding="utf-8", errors="replace")
                if "WEBEEBLOCKS_RUNTIME_V2 READY" in data:
                    record["native_ready"] = True
                if not window:
                    window = gui_windows(process.pid)
                if window and record["native_ready"]:
                    break
                time.sleep(0.25)
            record["windows"] = window
            record["gui_window_observed"] = bool(window)
            if not record["native_ready"]:
                raise RuntimeError("No real native C READY from installed Windows Webots")
            if not window:
                raise RuntimeError("No OS-observable Webots GUI window for graceful shutdown")
            # Native Webots GUI: exercise ordinary window closure, no sentinel unlink.
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            if not user32.PostMessageW(ctypes.c_void_p(window[0]["hwnd"]), WM_CLOSE, 0, 0):
                raise RuntimeError("WM_CLOSE could not be posted to genuine Webots GUI")
            try:
                code = process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                raise RuntimeError("Webots ignored WM_CLOSE; no normal-close proof")
            record["exit_code"] = code
            record["normal_shutdown"] = code == 0
            if not record["normal_shutdown"]:
                raise RuntimeError(f"Webots normal shutdown exit={code}")
        finally:
            if process.poll() is None:
                record["forced_cleanup_after_failure"] = True
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False, timeout=20)
            process.wait(timeout=20)
            for job in jobs:
                job.join(timeout=20)
            record["end_utc"] = time.time()
            record["exit_code"] = process.returncode
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--webots-home", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Windows native only")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {"kind": "R3_WINDOWS_NATIVE_NOT_GUI_ACCEPTANCE",
              "product_base": EXPECTED_BASE, "sessions": [], "result": "UNPROVEN",
              "window_name_test": "NOT_RUN",
              "browser_profile_test": "NOT_RUN",
              "wwi_authority_test": "NOT_RUN",
              "blockly_test": "NOT_RUN"}
    try:
        home = args.webots_home.resolve()
        package = args.package.resolve()
        exe = home / "msys64/mingw64/bin/webots.exe"
        controller = package / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.exe"
        world = package / "worlds/crazyflie_runtime_v2.wbt"
        if not (exe.is_file() and controller.is_file() and world.is_file()):
            raise RuntimeError("Missing installed Windows Webots, PE controller or classroom world")
        if controller.read_bytes()[:2] != b"MZ":
            raise RuntimeError("Controller is not a Windows PE binary")
        report["webots_exe_sha256"] = digest(exe)
        report["controller_pe_sha256"] = digest(controller)
        report["world_sha256_before"] = digest(world)
        report["world_path"] = str(world)
        state = out / "persistent-state"
        state.mkdir(exist_ok=True)
        for index in (1, 2):
            result = launch_once(exe, world, out, state, index)
            report["sessions"].append(result)
        report["world_sha256_after"] = digest(world)
        if report["world_sha256_before"] != report["world_sha256_after"]:
            raise RuntimeError("World bytes changed across Windows launches")
        report["result"] = "PASS_TWO_NATIVE_WINDOWS_LAUNCHES_ONLY"
    except Exception:
        report["error"] = traceback.format_exc()
        print(report["error"], file=sys.stderr)
    finally:
        (out / "native-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("R3_WINDOWS_NATIVE_REPORT=" + str(out / "native-report.json"), flush=True)
    return 0 if report["result"] == "PASS_TWO_NATIVE_WINDOWS_LAUNCHES_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
