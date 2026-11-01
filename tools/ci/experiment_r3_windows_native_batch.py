#!/usr/bin/env python3
"""Bounded official Windows R2025a native C READY experiment, NOT GUI / R3 authority.

Uses the same installed engine_environment/captured_engine as the already
qualified Windows native Grand Prix tool. No browser, no fake WWI, no normal
shutdown assertion; cleanup is explicitly forced after proof acquisition.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
import subprocess
import threading
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.run_grand_prix_windows_native import engine_environment

@contextmanager
def captured_native_batch(command, cwd, env, stdout_path, stderr_path):
    # Unlike an ordinary Webots GUI shutdown, batch observation deliberately
    # terminates its disposable engine after C READY. Exit 1 / pipe errors on
    # that forced teardown are not claims about the native R3 protocol.
    errors = []
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        process = subprocess.Popen(command, cwd=cwd, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def drain(src, dest):
            try:
                with src:
                    while chunk := src.read1(65536):
                        dest.write(chunk)
                        dest.flush()
            except Exception as error:
                errors.append(str(error))
        threads = [threading.Thread(target=drain, args=(src, dest), daemon=True)
                   for src, dest in ((process.stdout, out), (process.stderr, err))]
        for thread in threads:
            thread.start()
        try:
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=15)
            else:
                process.wait(timeout=15)
            for thread in threads:
                thread.join(timeout=15)
            if any(thread.is_alive() for thread in threads) or errors:
                raise RuntimeError("Windows Webots native pipe drain failed: " + str(errors))



def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


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
    home = args.webots_home.resolve()
    package = args.package.resolve()
    exe = home / "msys64/mingw64/bin/webots.exe"
    controller = package / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.exe"
    world = package / "worlds/crazyflie_runtime_v2.wbt"
    report = {"status": "UNPROVEN", "scope": "NATIVE_WINDOWS_WEBOTS_C_READY_ONLY",
              "browser": "NOT_RUN", "authorization": "NOT_RUN",
              "gui_windows": "NOT_RUN", "world_reload": "NOT_RUN"}
    try:
        assert all(x.is_file() for x in (exe, controller, world))
        report["controller_pe_sha256"] = sha256(controller)
        report["world_sha256"] = sha256(world)
        env = engine_environment(home, os.environ.copy())
        env["WEBOTS_HOME"] = str(home)
        env["WEBEEBLOCKS_RECOVERY_STATE_DIR"] = str(out / "batch-state")
        (out / "batch-state").mkdir(exist_ok=True)
        command = [str(exe), "--stdout", "--stderr", "--batch", "--mode=fast", str(world)]
        report["command"] = command
        with captured_native_batch(command, package, env, out / "batch.stdout.log",
                             out / "batch.stderr.log") as process:
            report["pid"] = process.pid
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                stdout = (out / "batch.stdout.log").read_text(
                    encoding="utf-8", errors="replace")
                if "WEBEEBLOCKS_RUNTIME_V2 READY" in stdout:
                    report["native_ready"] = True
                    report["status"] = "PASS_NATIVE_WIN_C_READY_BATCH_ONLY"
                    break
                if process.poll() is not None:
                    report["process_exit_before_ready"] = process.returncode
                    break
                time.sleep(0.25)
            report["cleanup"] = "forced after bounded observation (NOT normal shutdown)"
        if report["status"] != "PASS_NATIVE_WIN_C_READY_BATCH_ONLY":
            raise RuntimeError("Official Windows Webots batch did not yield controller C READY")
    except Exception:
        report["status"] = "UNPROVEN"
        report["error"] = traceback.format_exc()
        print(report["error"], file=sys.stderr)
    finally:
        (out / "batch-native-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        print("WINDOWS_BATCH_NATIVE_RESULT=" + report["status"], flush=True)
    return 0 if report["status"] == "PASS_NATIVE_WIN_C_READY_BATCH_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
