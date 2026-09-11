#!/usr/bin/env python3
"""Record missing X3 sensor inputs on the unchanged #251 firmware, props off.

This is acquisition support, not a checkpoint request, estimator or physical
verdict. Imports cflib only for an explicit recording. Never flashes, changes
parameters, resets the estimator or invokes a commander. cflib's normal link
close can still emit its documented safety-zero setpoint.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import threading
import time


FIRMWARE_TARGET = "6562ad827bf0c8bf2c9b609edad36f3e15652133"
FIRMWARE_BIN_SHA256 = "67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738"
PARAMETERS = {
    "stabilizer.estimator": 3, "ukf.qualityGateTof": 20,
    "ukf.baroNoise": 6.25, "ukf.surfaceOffsetS3": 1,
}
# Every variable is fetched as a 32-bit float: at most 24 of 26 payload bytes.
# A log timestamp is NOT a per-sensor producer timestamp. No synchronized IMU
# integration claim follows from this choice of log periods.
BLOCKS = {
    "barometer": (20, ("baro.asl", "baro.pressure", "baro.temp")),
    "imu": (10, ("acc.x", "acc.y", "acc.z", "gyro.x", "gyro.y", "gyro.z")),
    "pose": (20, ("range.zrange", "stabilizer.roll", "stabilizer.pitch",
                  "stateEstimate.z", "stateEstimate.vz")),
    "detector": (20, ("sensorFilter.surfState", "sensorFilter.surfReason",
                      "sensorFilter.surfOffset", "sensorFilter.surfBaroD",
                      "sensorFilter.flowLocal", "sensorFilter.lateElig")),
}
TIMESTAMP_MODULUS = 1 << 24


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_inputs(cf: object) -> dict[str, str]:
    missing = [name for _, names in BLOCKS.values() for name in names
               if cf.log.toc.get_element_by_complete_name(name) is None]
    if missing:
        raise ValueError("required live log variables missing: " + ", ".join(missing))
    observed = {}
    for name, expected in PARAMETERS.items():
        raw = cf.param.get_value(name)
        observed[name] = str(raw)
        if isinstance(raw, bool) or float(raw) != expected:
            raise ValueError(f"unchanged #251 parameter required: {name}")
    return observed


class Recorder:
    """Append observed samples; keep incomplete/invalid captures for inspection."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.lock = threading.Lock()
        self.error: str | None = None
        self.closed = False
        self.streams = {}
        self.writers = {}
        self.stats = {}
        for name, (_, columns) in BLOCKS.items():
            stream = (root / f"{name}.csv").open("x", newline="", encoding="utf-8")
            writer = csv.writer(stream)
            writer.writerow(("cf_timestamp_ms", "host_monotonic_s", *columns))
            stream.flush()
            self.streams[name] = stream
            self.writers[name] = writer
            self.stats[name] = {"rows": 0, "last_timestamp_ms": None,
                                "last_host_s": None, "max_gap_ms": 0,
                                "nonincreasing_timestamps": 0, "invalid_rows": 0}

    def fail(self, reason: str) -> None:
        with self.lock:
            if self.error is None:
                self.error = reason

    def callback(self, name: str):
        def received(timestamp, data, _config):
            host_s = time.monotonic()
            with self.lock:
                if self.closed:
                    return
                stats = self.stats[name]
                _, columns = BLOCKS[name]
                values = [data.get(column) for column in columns]
                # Retain the observed invalid row before marking it unusable.
                try:
                    self.writers[name].writerow((timestamp, repr(host_s), *values))
                    self.streams[name].flush()
                except OSError as exc:
                    self.error = self.error or f"{name}: output write failed: {exc}"
                    return
                stats["rows"] += 1
                valid = (isinstance(timestamp, int) and not isinstance(timestamp, bool)
                         and 0 <= timestamp < TIMESTAMP_MODULUS
                         and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                 and math.isfinite(v) for v in values))
                if not valid:
                    stats["invalid_rows"] += 1
                    self.error = self.error or f"{name}: missing/malformed/non-finite sample"
                    return
                previous = stats["last_timestamp_ms"]
                if previous is not None:
                    gap = (timestamp - previous) % TIMESTAMP_MODULUS
                    if gap == 0 or gap >= TIMESTAMP_MODULUS // 2:
                        stats["nonincreasing_timestamps"] += 1
                        self.error = self.error or f"{name}: duplicate/backward log timestamp"
                    else:
                        stats["max_gap_ms"] = max(stats["max_gap_ms"], gap)
                        if gap > 5 * BLOCKS[name][0]:
                            self.error = self.error or f"{name}: log gap exceeds five periods"
                stats["last_timestamp_ms"] = timestamp
                stats["last_host_s"] = host_s
        return received

    def check_streams(self, *, startup: bool = False) -> bool:
        with self.lock:
            if self.error:
                raise RuntimeError(self.error)
            now = time.monotonic()
            ready = all(s["rows"] >= 2 for s in self.stats.values())
            if not startup and any(s["last_host_s"] is None or now - s["last_host_s"] > 1
                                   for s in self.stats.values()):
                raise RuntimeError("one or more required log streams stopped")
            return ready

    def close(self) -> None:
        with self.lock:
            self.closed = True
            for stream in self.streams.values():
                stream.close()


def write_json_once(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def record(args) -> int:
    if not args.props_removed or not args.installed_bin_confirmed:
        raise ValueError("props removal and installation of the supplied exact binary must be confirmed")
    if file_digest(args.firmware_bin) != FIRMWARE_BIN_SHA256:
        raise ValueError("the supplied firmware file is not the exact #251 cf2.bin")
    if not re.fullmatch(r"radio://[0-9]+/[0-9]+/(250K|1M|2M)(/[0-9A-Fa-f]+)?", args.uri):
        raise ValueError("one explicit Crazyradio URI is required")
    if not re.fullmatch(r"https://github.com/djibian/webeeblocks/issues/[1-9][0-9]*", args.checkpoint_url):
        raise ValueError("an exact existing checkpoint issue URL is required")
    if not re.fullmatch(r"[0-9a-f]{40}", args.request_sha):
        raise ValueError("the exact checkpoint request SHA is required")
    if not 30 <= args.seconds <= 300:
        raise ValueError("capture duration must be 30–300 seconds")

    import cflib
    import cflib.crtp
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.log import LogConfig

    args.output.mkdir(parents=True, exist_ok=False)
    write_json_once(args.output / "capture-start.json", {
        "schema": "webeeblocks.x3.sensor-capture.v1",
        "checkpoint_url": args.checkpoint_url, "request_sha": args.request_sha,
        "test_profile": "s3-props-off", "purpose": "checkpoint",
        "tested_firmware_source_sha": FIRMWARE_TARGET,
        "verified_local_firmware_bin_sha256": FIRMWARE_BIN_SHA256,
        "installed_firmware_identity": "operator-confirmed; not remote attestation",
        "props_removed_operator_confirmation": True,
        "capture_script_sha256": file_digest(Path(__file__)),
        "cflib_module_sha256": file_digest(Path(cflib.__file__)),
        "cflib_logging_module_sha256": file_digest(Path(sys.modules["cflib.crazyflie.log"].__file__)),
        "runtime_boundary": "module fingerprints are not a complete dependency/runtime lock",
        "started_host_monotonic_s": time.monotonic(), "duration_seconds": args.seconds,
        "blocks": BLOCKS, "uri": args.uri,
        "time_boundary": "device log and host receipt times; no sensor producer times",
        "physical_verdict": None,
    })
    recorder = Recorder(args.output)
    configs = []
    outcome = "INCOMPLETE"
    error = None
    try:
        cflib.crtp.init_drivers()
        cf = Crazyflie(rw_cache=None)
        fully_connected = threading.Event()
        cf.fully_connected.add_callback(lambda *_: fully_connected.set())
        cf.connection_failed.add_callback(lambda _, msg: recorder.fail(f"connection failed: {msg}"))
        cf.connection_lost.add_callback(lambda *_: recorder.fail("Crazyradio connection lost"))
        try:
            cf.open_link(args.uri)
            deadline = time.monotonic() + 30
            while not fully_connected.is_set():
                recorder.check_streams(startup=True)
                if time.monotonic() >= deadline:
                    raise RuntimeError("connection/parameter download did not complete within 30 s")
                time.sleep(0.02)
            recorder.check_streams(startup=True)
            observed = require_inputs(cf)
            write_json_once(args.output / "observed-parameters.json", observed)
            try:
                for name, (period, columns) in BLOCKS.items():
                    config = LogConfig("X3_" + name, period)
                    for column in columns:
                        config.add_variable(column, "float")
                    cf.log.add_config(config)
                    config.data_received_cb.add_callback(recorder.callback(name))
                    config.error_cb.add_callback(lambda conf, msg: recorder.fail(f"{conf.name}: {msg}"))
                    configs.append(config)
                    config.start()
                deadline = time.monotonic() + 5
                while not recorder.check_streams(startup=True):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("required streams did not become observable within 5 s")
                    time.sleep(0.02)
                # Startup samples stay in the raw files. This timestamp identifies
                # readiness, not the physical start/end of a movement.
                ready_at = time.monotonic()
                write_json_once(args.output / "recording-ready.json", {"host_monotonic_s": ready_at})
                print("ENREGISTREMENT : suivez uniquement la procédure du checkpoint ; hélices retirées.", flush=True)
                while time.monotonic() - ready_at < args.seconds:
                    recorder.check_streams()
                    time.sleep(0.02)
                recorder.check_streams()
                outcome = "CAPTURED"
            finally:
                for config in configs:
                    try:
                        config.stop()
                    except Exception as exc:
                        recorder.fail(f"log stop failed: {exc}")
        finally:
            cf.close_link()
    except (Exception, KeyboardInterrupt) as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        recorder.close()
        if error or recorder.error:
            outcome = "INCOMPLETE"
        write_json_once(args.output / "capture-result.json", {
            "capture_status": outcome, "error": error or recorder.error,
            "streams": recorder.stats, "physical_verdict": None,
            "boundary": "capture completion is not scientific sufficiency or durable publication",
        })
    print(f"{outcome}: {args.output}")
    return 0 if outcome == "CAPTURED" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true", help="show log plan without importing cflib")
    parser.add_argument("--uri")
    parser.add_argument("--checkpoint-url")
    parser.add_argument("--request-sha")
    parser.add_argument("--firmware-bin", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seconds", type=int, default=150)
    parser.add_argument("--props-removed", action="store_true")
    parser.add_argument("--installed-bin-confirmed", action="store_true")
    args = parser.parse_args()
    if args.describe:
        print(json.dumps({"blocks": BLOCKS, "parameters": PARAMETERS,
                          "firmware_target": FIRMWARE_TARGET,
                          "firmware_bin_sha256": FIRMWARE_BIN_SHA256}, indent=2))
        return 0
    if not all((args.uri, args.checkpoint_url, args.request_sha, args.firmware_bin, args.output)):
        parser.error("recording requires URI, checkpoint URL/SHA, exact firmware file and new output directory")
    try:
        return record(args)
    except (OSError, ValueError, ImportError) as exc:
        print(f"CAPTURE_ERROR: {exc}; retain any partial output for inspection", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
