#!/usr/bin/env python3
"""Bounded props-off raw front-range capture; no flight or sensor verdict."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import threading
import time

import prepare_physical_flight as preparation
from prepare_x3_independent_capture import CflibParamAdapter, open_live_crazyflie
from range_observer import FreshRangeObserver, RangeReadError, range_mm_to_m, _timestamp_is_later
from x3_no_commander_link import close_link_without_commander

DURATION_SECONDS = 10.0
SAMPLE_TIMEOUT_SECONDS = 0.7
SCHEMA = "webeeblocks.front-range-diagnostic.v1"


def require_geometry(value):
    if (not isinstance(value, dict) or set(value) != {"target_distance_m", "uncertainty_m", "method"}
            or not isinstance(value["method"], str) or not value["method"].strip()):
        raise ValueError("measured finite target geometry required")
    for name in ("target_distance_m", "uncertainty_m"):
        if type(value[name]) not in (int, float) or not math.isfinite(value[name]):
            raise ValueError("finite geometry coordinates required")
    if not 0 < value["uncertainty_m"] < value["target_distance_m"] <= 2.0:
        raise ValueError("positive measured target within 2 m required")


class RawWindow:
    def __init__(self, output, *, clock=None):
        self.clock = clock or time.monotonic
        self.lock = threading.Lock()
        self.stream = (output / "front-range.csv").open("x", encoding="utf-8", newline="")
        self.writer = csv.writer(self.stream)
        self.writer.writerow(("device_timestamp_ms", "host_received_monotonic_s", "raw_mm", "classification"))
        self.stream.flush()
        self.closed = False
        self.error = None
        self.last_timestamp = None
        self.last_receipt = self.clock()
        self.count = 0

    def fail(self, message):
        with self.lock:
            if not self.closed and self.error is None:
                self.error = str(message)

    def received(self, timestamp, data, _config):
        now = self.clock()
        with self.lock:
            if self.closed:
                return
            raw = data.get("range.front") if isinstance(data, dict) else None
            valid_timestamp = type(timestamp) is int and 0 <= timestamp < (1 << 24)
            valid_raw = type(raw) is int and 0 <= raw <= 65535
            classification = "malformed"
            if valid_raw:
                try:
                    range_mm_to_m(raw)
                    classification = "available"
                except RangeReadError:
                    classification = "unavailable"
            # Retain the rejected observation too; unavailable is diagnostic
            # data, never a numeric distance or clearance assertion.
            try:
                self.writer.writerow((repr(timestamp), now, repr(raw), classification))
                self.stream.flush()
                self.count += 1
            except Exception as exc:
                self.error = "raw evidence write failed: " + str(exc)
                return
            if not valid_timestamp or not valid_raw:
                self.error = self.error or "malformed range observation"
            elif self.last_timestamp is not None and not _timestamp_is_later(timestamp, self.last_timestamp):
                self.error = self.error or "range timestamp did not advance"
            elif now - self.last_receipt > SAMPLE_TIMEOUT_SECONDS:
                self.error = self.error or "range stream gap exceeded unchanged 0.7 s timeout"
            self.last_timestamp, self.last_receipt = timestamp, now

    def check(self):
        with self.lock:
            if self.error:
                raise RuntimeError(self.error)
            if not self.closed and self.clock() - self.last_receipt > SAMPLE_TIMEOUT_SECONDS:
                raise RuntimeError("range stream unavailable beyond 0.7 s")

    def close(self):
        with self.lock:
            self.closed = True
            self.stream.close()


def live_capture(uri, window, output):
    from cflib.crazyflie.log import LogConfig
    cf, config = None, None
    try:
        cf = open_live_crazyflie(uri)
        from probe_reference_hardware import _read_connected_descriptor
        descriptor = _read_connected_descriptor(cf)
        preparation.write_once(output / "connected-descriptor.json", descriptor)
        # Reuse the actual post-reset baseline validator as a pure check. No
        # factory/reset/session authority is constructed or requested here.
        from powered_session_authority import TrustedPoweredSessionFactory
        TrustedPoweredSessionFactory._validate_capabilities(None, descriptor)
        if "multi-ranger-deck" not in descriptor.get("hardware", ()):
            raise ValueError("live Multi-ranger presence/self-test required")
        adapter = CflibParamAdapter(cf)
        readbacks = {}
        for name in (*preparation.EXPECTED, "multiranger.filterMask"):
            ctype, _, _ = adapter.describe(name)
            raw = adapter.read_fresh(name)
            readbacks[name] = {"ctype": ctype, "raw": repr(raw), "value": None}
            preparation.write_once(output / ("raw-" + name + ".json"), readbacks[name])
            from probe_reference_hardware import _parse_uint
            readbacks[name]["value"] = _parse_uint(raw, name)
        preparation.check_readbacks({k: readbacks[k] for k in preparation.EXPECTED})
        mask = readbacks["multiranger.filterMask"]
        if mask["ctype"] != "uint16_t" or mask["value"] != 1:
            raise ValueError("unchanged official RANGE_VALID-only filter required")
        preparation.write_once(output / "fresh-readbacks.json", readbacks)
        FreshRangeObserver(cf, lambda: "diagnostic-only", "front")._require_exact_toc_entry()
        config = LogConfig("WebeeBlocks front diagnostic", 100)
        config.add_variable("range.front", "uint16_t")
        config.data_received_cb.add_callback(window.received)
        config.error_cb.add_callback(lambda _, message: window.fail(message))
        cf.disconnected.add_callback(lambda *_: window.fail("Crazyflie disconnected"))
        cf.connection_lost.add_callback(lambda *_: window.fail("Crazyradio connection lost"))
        cf.log.add_config(config)
        # Start the deadline immediately before logging, not during bounded
        # connection/PARAM setup, which has no claimed sensor coverage.
        window.last_receipt = window.clock()
        started = window.clock()
        config.start()
        while window.clock() - started < DURATION_SECONDS:
            window.check()
            time.sleep(0.02)
        window.check()
        if window.count == 0:
            raise RuntimeError("no front-range rows retained")
    finally:
        # Seal first so late callbacks cannot alter the retained evidence.
        window.close()
        try:
            if config is not None:
                config.stop()
                config.delete()
        finally:
            if cf is not None:
                close_link_without_commander(cf)


def diagnose(root, uri, record, geometry, output, props_removed, *, capture=live_capture):
    if props_removed is not True:
        raise ValueError("all four propellers must be removed")
    verified_record = preparation.verify_record(root, uri, record)
    record_bytes = record.read_bytes()
    if json.loads(record_bytes) != verified_record:
        raise ValueError("preparation record changed after verification")
    geometry_bytes = geometry.read_bytes()
    require_geometry(json.loads(geometry_bytes))
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(root.resolve()):
        raise ValueError("new output outside exact package required")
    output.mkdir(parents=True, exist_ok=False)
    (output / "preparation-record.json").write_bytes(record_bytes)
    (output / "geometry.json").write_bytes(geometry_bytes)
    preparation.write_once(output / "diagnostic-start.json", {
        "schema": SCHEMA, "uri": uri, "source_sha": (root / "SOURCE_SHA").read_text().strip(),
        "preparation_sha256": hashlib.sha256(record_bytes).hexdigest(),
        "geometry_sha256": hashlib.sha256(geometry_bytes).hexdigest(),
        "duration_seconds": DURATION_SECONDS, "period_ms": 100,
        "sample_timeout_seconds": SAMPLE_TIMEOUT_SECONDS,
        "props_removed": True, "execution_authority": False,
        "boundary": "one connection/window; geometry is operator evidence, not sensor-proven ground truth",
    })
    window = RawWindow(output)
    error = None
    try:
        capture(uri, window, output)
        window.check()
        if window.count == 0:
            raise RuntimeError("no front-range rows retained")
    except BaseException as exc:
        error = preparation.exception_chain(exc)
    finally:
        window.close()
        preparation.write_once(output / "diagnostic-result.json", {
            "schema": SCHEMA, "status": "OBSERVED" if error is None else "INCOMPLETE",
            "errors": error, "sample_count": window.count, "physical_verdict": None,
            "execution_authority": False, "boundary": "capture completion only; unavailable is not clearance or a sensor PASS",
        })
    return 0 if error is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--uri", required=True)
    parser.add_argument("--preparation-record", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--props-removed", action="store_true")
    args = parser.parse_args()
    return diagnose(args.root, args.uri, args.preparation_record, args.geometry, args.output, args.props_removed)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print("FRONT_DIAGNOSTIC_ERROR: " + str(exc))
        raise SystemExit(2)
