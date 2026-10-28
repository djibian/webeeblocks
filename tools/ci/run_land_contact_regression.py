#!/usr/bin/env python3
"""Native #637 regression in addition to the full unchanged browser missions.

The qualification shell preserves R2025a actuation, collision and inertia.
Only request transport and scene readiness are injected. This is not a
replacement for full scene, browser, mission or independent deadline proofs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--xvfb", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--step", type=int, choices=(8, 32), default=32)
    parser.add_argument("--case", choices=("land", "airborne-idle"), default="land")
    parser.add_argument("--runtime-source", type=Path,
                        help="explicit diagnostic source; CI uses current shared source")
    args = parser.parse_args()
    home, out = args.home.resolve(), args.out.resolve()
    if (home / "resources/version.txt").read_text().strip() != "R2025a":
        raise RuntimeError("R2025a required")
    out.mkdir(parents=True, exist_ok=False)
    source_path = args.runtime_source or ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c"
    source = source_path.read_text()
    # Keep the controller/sensor period at 32 ms even in the 8 ms physics case.
    edits = (
        ("const int step = (int)wb_robot_get_basic_time_step();", "const int step = 32;"),
        ("wb_robot_wwi_receive_text()", "land_receive()"),
        ("wb_robot_wwi_send_text(text)", "land_send(text)"),
        ("wb_robot_step(step)", "land_step(step)"),
    )
    for before, after in edits:
        expected = 2 if before == "wb_robot_step(step)" else 1
        if source.count(before) != expected:
            raise ValueError("native replay anchor changed: " + before)
        source = source.replace(before, after)
    prefix = ("#include <webots/robot.h>\nint land_step(int);\n"
              "const char *land_receive(void);\nvoid land_send(const char*);\n")
    (out / "runtime.c").write_text(prefix + source)
    (out / "runtime-original.c").write_bytes(source_path.read_bytes())
    driver = HERE / "fixtures" / ("land_contact_driver.c" if args.case == "land" else "airborne_idle_failsafe_driver.c")
    shutil.copyfile(driver, out / "driver.c")
    shutil.copyfile(Path(__file__), out / "runner.py")
    proto = ROOT / "worlds/protos/QualificationCrazyflieR2025a.proto"
    shutil.copyfile(proto, out / proto.name)
    env = {key: value for key, value in os.environ.items()
           if not key.lower().endswith("_proxy")}
    env.update(WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE="true",
               LP_NUM_THREADS="1", WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE="true")
    env["LD_LIBRARY_PATH"] = (str(home / "lib/controller") + ":" +
                             str(home / "lib/webots") + ":" + env.get("LD_LIBRARY_PATH", ""))
    command = [
        "gcc", "-std=c11", "-I" + str(home / "include/controller/c"),
        "-I" + str(ROOT / "controllers/crazyflie_runtime_v2"),
        "-I" + str(ROOT / "controllers/crazyflie_square"),
        str(out / "runtime.c"), str(out / "driver.c"),
        str(ROOT / "controllers/crazyflie_square/pid_controller.c"),
        "-L" + str(home / "lib/controller"), "-lController", "-lm",
        "-o", str(out / "probe"),
    ]
    provenance = {
        "schema": 1, "case": args.case, "physics_step_ms": args.step, "control_step_ms": 32,
        "runtime_source": str(source_path), "runtime_sha256": sha(source_path),
        "pid_sha256": sha(ROOT / "controllers/crazyflie_square/pid_controller.c"),
        "proto_sha256": sha(proto), "webots_bin_sha256": sha(home / "bin/webots-bin"),
        "compile_argv": command,
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    with (out / "build.log").open("w") as log:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=90)
    (out / "world.wbt").write_text(f'''#VRML_SIM R2025a utf8
EXTERNPROTO "{out / proto.name}"
WorldInfo {{ basicTimeStep {args.step} randomSeed 1 optimalThreadCount 1 }}
Viewpoint {{ position 0 -1 1 orientation 1 0 0 0.8 }}
Solid {{ boundingObject Plane {{ size 4 4 }} }}
QualificationCrazyflieR2025a {{
 name "land-body" controller "<extern>" window "<none>" supervisor TRUE
 extensionSlot [
  LED {{ name "color_led" }}
  DistanceSensor {{ name "range_up" rotation 0 1 0 -1.57079632679
   lookupTable [0 0 0, 2 2000 0] }}
 ]
}}
''')
    display_port = free_port()
    if display_port <= 6000:
        raise RuntimeError("invalid X display port")
    env["DISPLAY"] = "127.0.0.1:" + str(display_port - 6000)
    controller_code = webots_code = None
    try:
        with (out / "xvfb.log").open("w") as xlog:
            xvfb = subprocess.Popen(
                [args.xvfb, ":" + str(display_port - 6000), "-ac", "-nolisten", "unix",
                 "-nolisten", "local", "-listen", "tcp", "-screen", "0", "1280x1024x24"],
                env=env, stdout=xlog, stderr=subprocess.STDOUT)
            try:
                limit = time.monotonic() + 10
                while True:
                    try:
                        with socket.create_connection(("127.0.0.1", display_port), timeout=.2):
                            break
                    except OSError:
                        if xvfb.poll() is not None or time.monotonic() > limit:
                            raise RuntimeError("Xvfb readiness absent; inspect retained log")
                        time.sleep(.1)
                port = free_port()
                with (out / "webots.log").open("w") as log:
                    webots = subprocess.Popen(
                        [str(home / "webots"), "--batch", "--minimize", "--no-rendering",
                         "--mode=fast", "--stdout", "--stderr", "--port=" + str(port),
                         str(out / "world.wbt")], env=env, stdout=log, stderr=subprocess.STDOUT)
                    try:
                        limit = time.monotonic() + 45
                        while "Waiting for local or remote connection" not in (out / "webots.log").read_text():
                            if webots.poll() is not None or time.monotonic() > limit:
                                raise RuntimeError("native extern readiness absent")
                            time.sleep(.1)
                        with (out / "controller.log").open("w") as clog:
                            controller = subprocess.run(
                                [str(home / "webots-controller"), "--protocol=tcp",
                                 "--ip-address=127.0.0.1", "--port=" + str(port),
                                 "--robot-name=land-body", str(out / "probe")],
                                env=env, stdout=clog, stderr=subprocess.STDOUT, timeout=90)
                        controller_code = controller.returncode
                        webots_code = webots.wait(timeout=15)
                    finally:
                        if webots.poll() is None:
                            webots.terminate()
                            try:
                                webots.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                webots.kill()
                                webots.wait()
            finally:
                xvfb.terminate()
                try:
                    xvfb.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    xvfb.kill()
                    xvfb.wait()
    finally:
        # Every log is closed and every direct producer stopped before sealing.
        (out / "exit.json").write_text(json.dumps({
            "controller": controller_code, "webots": webots_code}) + "\n")
        manifest = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*"))
                    if p.is_file() and p.name != "sha256.json"}
        (out / "sha256.json").write_text(json.dumps(manifest, indent=2) + "\n")
    text = (out / "controller.log").read_text()
    if args.case == "airborne-idle":
        if (webots_code != 0 or controller_code != 0 or
                text.count("AIRBORNE_IDLE_TILT_INJECTED ") != 1 or
                text.count("FATAL unsafe airborne idle attitude") != 1 or
                text.count("AIRBORNE_IDLE_FAILSAFE_END completed=1 failed=0 ") != 1 or
                text.count("WEBEEBLOCKS_RUNTIME_V2 TRACE RESET ") != 1 or
                text.count("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK") != 1 or
                text.count("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 ERR RESET_REQUIRED") != 1 or
                text.count("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK") != 1 or
                "WEBEEBLOCKS_RUNTIME_V2 RESPONSE -1" in text):
            raise RuntimeError("native airborne idle attitude guard/refreshed RESET failed; inspect " + str(out))
        print("PASS native R2025a airborne idle unsafe attitude stops motors, rejects action, and RESET restores fresh access; " + str(out))
    else:
        if (webots_code != 0 or controller_code != 0 or
                text.count("LAND_REGRESSION_END completed=1 failed=0 ") != 1):
            raise RuntimeError("historical LAND independent pose regression failed; inspect " + str(out))
        print("PASS native R2025a historical LAND with independent post-ACK pose/stability; " + str(out))


if __name__ == "__main__":
    main()
