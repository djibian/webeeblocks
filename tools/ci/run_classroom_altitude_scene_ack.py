#!/usr/bin/env python3
"""Witness real R2025a altitude/orientation SCENE/SCENE_OK without pupil flight.

Runs only inside the already prepared/pinned Webots CI container. Browser
messages are a test-only source; the classroom C++ scene selector remains the
single native authority. The evaluator READY must arise from Webots import,
not from a preloaded world or a mocked JavaScript backend.
"""
from __future__ import annotations

import http.server
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import prepare_classroom_altitude_scene_ack as world_probe

ARTIFACT = world_probe.ROOT / "ci-artifacts/progression-sequence-mission/altitude-scene-ack"
EVENTS = []
REQUIRED = (
    "CLASSROOM_WINDOW_HTML_LOADED",
    "CLASSROOM_PROBE_JS_STARTED",
    "CLASSROOM_BRIDGE_CONSTRUCTED",
    "CLASSROOM_RUNTIME_READY",
    "TAKEOFF_BEFORE_SCENE_REFUSED",
    "UNKNOWN_SCENE_REFUSED",
    "ALTITUDE_SCENE_ACK",
    "LEGACY_SCENE_RESTORED",
    "ALTITUDE_SCENE_REATTACHED",
    "ORIENTATION_SCENE_ACK",
    "LEGACY_AFTER_ORIENTATION_RESTORED",
    "ORIENTATION_SCENE_REATTACHED",
    "NATIVE_SCENE_ACK_TEST_COMPLETE",
)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path != "/event":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 8192:
                raise ValueError("event length out of bounds")
            event = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                raise ValueError("invalid browser event")
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(400)
            return
        EVENTS.append(event)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def run() -> int:
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT / "webots.log"
    observed = ARTIFACT / "events.json"
    server = None
    process = None
    log = None
    try:
        # No cleanup of an unknown preexisting world is authorized.
        world_probe.prepare()
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = dict(os.environ)
        env["WEBOTS_WEB_BROWSER"] = "/workspace/tools/ci/webots_runtime_v2_browser.sh"
        log = output.open("w", encoding="utf-8")
        process = subprocess.Popen(
            ["timeout", "-k", "5s", "115s", "xvfb-run", "-a", "webots",
             "--stdout", "--stderr", "--batch", "--mode=realtime", str(world_probe.WORLD)],
            cwd=str(world_probe.ROOT), stdout=log, stderr=subprocess.STDOUT,
            env=env, start_new_session=True,
        )
        deadline = time.monotonic() + 110
        ready_marker = (
            "WEBEEBLOCKS_ALTITUDE_READY scene=altitude-v1 "
            "oracle=progression-altitude-3d-v1"
        )
        orientation_ready_marker = (
            "WEBEEBLOCKS_ORIENTATION_3D_READY scene=orientation-v1 "
            "oracle=progression-orientation-3d-v1"
        )
        while time.monotonic() < deadline:
            complete = any(e["event"] == "NATIVE_SCENE_ACK_TEST_COMPLETE" for e in EVENTS)
            # A scene ACK can precede the corresponding Webots evaluator
            # startup. Both independently imported evaluators must each start
            # twice, including after legacy restoration, before teardown.
            ready_twice = complete and output.exists() and (
                output.read_text(encoding="utf-8", errors="replace").count(ready_marker) >= 2
                and output.read_text(encoding="utf-8", errors="replace").count(orientation_ready_marker) >= 2
            )
            if ready_twice:
                break
            if any(e["event"] == "WINDOW_ERROR" for e in EVENTS):
                break
            if process.poll() is not None:
                break
            time.sleep(0.2)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=8)
        if log:
            log.close()
        if server:
            server.shutdown()
            server.server_close()
        observed.write_text(json.dumps(EVENTS, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        world_probe.cleanup()

    transcript = output.read_text(encoding="utf-8", errors="replace")
    found = [e["event"] for e in EVENTS]
    # Preserve enough evidence to distinguish a browser launch failure
    # from HTML loading, script evaluation, bridge initialization and native
    # liveness. Do not mark READY on the strength of these diagnostic markers.
    browser_log = world_probe.ROOT / "ci-artifacts/progression-sequence-mission/browser-launch.log"
    browser_log_text = (browser_log.read_text(encoding="utf-8", errors="replace")
                        if browser_log.exists() else "")
    browser_launched = ("BROWSER_LAUNCHED args=" in browser_log_text and
                        "altitude_scene_ack_probe.html" in browser_log_text)
    (ARTIFACT / "browser-launch-evidence.json").write_text(
        json.dumps({"browser_launched": browser_launched,
                    "launch_log": browser_log_text[-2000:]}, indent=2) + "\n",
        encoding="utf-8")
    missing = [name for name in REQUIRED if found.count(name) != 1]
    fatal = ("WEBEEBLOCKS_ALTITUDE_FATAL" in transcript or
             "WEBEEBLOCKS_ORIENTATION_3D_FATAL" in transcript or
             "WEBEEBLOCKS_ORIENTATION_3D_ERROR" in transcript or
             "WEBEEBLOCKS_RUNTIME_V2 FATAL" in transcript)
    # Two successive imports genuinely start the scene-local evaluator twice.
    two_evaluators = transcript.count(
        "WEBEEBLOCKS_ALTITUDE_READY scene=altitude-v1 oracle=progression-altitude-3d-v1") >= 2
    two_orientations = transcript.count(
        "WEBEEBLOCKS_ORIENTATION_3D_READY scene=orientation-v1 oracle=progression-orientation-3d-v1") >= 2
    flight_ready = "WEBEEBLOCKS_RUNTIME_V2 READY" in transcript
    if (missing or "WINDOW_ERROR" in found or fatal or not two_evaluators
            or not two_orientations or not flight_ready or not browser_launched):
        print("FAIL native altitude SCENE/ACK witness: " +
              json.dumps({"missing":missing, "events":EVENTS,
                          "browser_launched":browser_launched,
                          "fatal":fatal, "altitude_ready_twice":two_evaluators,
                          "orientation_ready_twice":two_orientations,
                          "flight_ready":flight_ready}), file=sys.stderr)
        print(transcript[-8000:], file=sys.stderr)
        return 1
    print("PASS real R2025a SCENE altitude-v1/orientation-v1 ACK, legacy restoration and two native starts per evaluator")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        print("FAIL native altitude SCENE witness exception: " + repr(exc), file=sys.stderr)
        raise
