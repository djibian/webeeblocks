#!/usr/bin/env python3
"""Exercise the actual read-only X3 health path without a hardware module."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/physical"))
spec = importlib.util.spec_from_file_location(
    "health_subject", ROOT / "tools/physical/prepare_x3_independent_capture.py",
)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
URI = "radio://0/80/2M"


class Callbacks:
    def __init__(self):
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


class Config:
    def __init__(self, name, period):
        self.name = name
        self.period = period
        self.columns = []
        self.data_received_cb = Callbacks()
        self.error_cb = Callbacks()
        self.active = False
        self.start_error = False

    def add_variable(self, name, ctype):
        assert ctype == "float"
        self.columns.append(name)

    def start(self):
        if self.start_error:
            raise RuntimeError("synthetic log start failed")
        self.active = True

    def stop(self):
        self.active = False


class FakeCf:
    def __init__(self):
        self.config = None
        self.log = types.SimpleNamespace(add_config=self.add_config)
        self.param = types.SimpleNamespace(set_value=self.forbidden)
        self.commander = types.SimpleNamespace(send_setpoint=self.forbidden)
        self.state = 3

    def add_config(self, config):
        self.config = config

    def forbidden(self, *_args):
        raise AssertionError("health evidence attempted a physical effect")

    close_link = forbidden


class Clock:
    def __init__(self, cf, mode):
        self.now = 10.0
        self.last = self.now
        self.count = 0
        self.cf = cf
        self.mode = mode

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += duration
        config = self.cf.config
        if config is None or not config.active or self.now - self.last < 0.1:
            return
        self.last = self.now
        self.count += 1
        if self.mode == "interrupt" and self.count == 5:
            raise KeyboardInterrupt("synthetic operator interruption")
        if self.mode == "log_error" and self.count == 5:
            config.error_cb.emit(config, "synthetic radio/log failure")
            return
        if self.mode == "insufficient" and self.count > 3:
            return
        values = {name: 0.0 for name in subject.HEALTH_BOUNDS}
        values["stateEstimate.z"] = 0.6
        if self.count == 5:
            if self.mode == "divergent":
                values["stateEstimate.z"] = -2.814063310623169
            elif self.mode == "nonfinite":
                values["stateEstimate.z"] = float("nan")
            elif self.mode == "missing":
                del values["stateEstimate.z"]
        config.data_received_cb.emit(self.count * 100, values, config)


class HealthEvidenceTests(unittest.TestCase):
    def run_case(self, mode, *, write_failure=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record = root / "prepared.json"
            record.write_bytes(b'{"synthetic_preparation":"exact bytes"}\n')
            output = root / "capture.health"
            cf = FakeCf()
            if mode == "teardown_error":
                def fail_close():
                    raise RuntimeError("synthetic teardown failure")
                cf.link = types.SimpleNamespace(close=fail_close)
            clock = Clock(cf, mode)
            log_module = types.ModuleType("cflib.crazyflie.log")

            def config_factory(name, period):
                config = Config(name, period)
                config.start_error = mode == "start_error"
                return config

            log_module.LogConfig = config_factory
            modules = {"cflib": types.ModuleType("cflib"),
                       "cflib.crazyflie": types.ModuleType("cflib.crazyflie"),
                       "cflib.crazyflie.log": log_module}
            health = None
            exception = None

            def open_link(uri):
                self.assertEqual(uri, URI)
                if mode == "connect_error":
                    raise subject.PreparationError("synthetic connection failure")
                return cf

            original_received = subject.HealthEvidence.received
            original_evaluate = subject.evaluate_health_samples

            def received(evidence, timestamp, data):
                if write_failure and evidence.sample_count == 4:
                    raise OSError("synthetic disk failure")
                original_received(evidence, timestamp, data)

            def evaluate(samples):
                # Inspect disk at the actual guard boundary, before its verdict.
                with (output / "health-samples.csv").open(newline="") as stream:
                    retained = list(csv.DictReader(stream))
                self.assertEqual(len(retained), len(samples))
                self.assertEqual([row["stateEstimate.z"] for row in retained],
                                 [repr(row.get("stateEstimate.z")) for row in samples])
                self.assertFalse((output / "health-result.json").exists())
                return original_evaluate(samples)

            with patch.dict(sys.modules, modules), patch.object(subject, "time", clock), \
                    patch.object(subject, "open_live_crazyflie", open_link), \
                    patch.object(subject.HealthEvidence, "received", received), \
                    patch.object(subject, "evaluate_health_samples", evaluate):
                try:
                    health = subject.verify_live_health(
                        URI, evidence_output=output, preparation_record=record,
                    )
                except BaseException as exc:
                    exception = exc

                # Bounds must see already retained, closed raw evidence.
                raw = (output / "health-samples.csv").read_bytes()
                if cf.config is not None:
                    cf.config.data_received_cb.emit(99999, {"stateEstimate.z": 4.0}, cf.config)
                self.assertEqual((output / "health-samples.csv").read_bytes(), raw)

            start = json.loads((output / "health-start.json").read_text())
            result = json.loads((output / "health-result.json").read_text())
            with (output / "health-samples.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual((output / "preparation-record.json").read_bytes(), record.read_bytes())
            self.assertEqual(start["preparation_record_sha256"], hashlib.sha256(record.read_bytes()).hexdigest())
            self.assertEqual(start["bounds"], {name: list(value) for name, value in subject.HEALTH_BOUNDS.items()})
            self.assertEqual(start["observe_seconds"], 2.0)
            self.assertEqual(start["period_ms"], 100)
            self.assertEqual(result["sample_count"], len(rows))
            self.assertIsNone(result["scientific_verdict"])
            if cf.config is not None:
                self.assertEqual(cf.config.columns, list(subject.HEALTH_BOUNDS))
                self.assertFalse(cf.config.active)
                if mode != "teardown_error":
                    self.assertEqual(cf.state, 0)
            return health, exception, result, rows

    def test_healthy_control(self):
        health, error, result, rows = self.run_case("healthy")
        self.assertIsNone(error)
        self.assertEqual(result["status"], "HEALTHY")
        self.assertEqual(health["sample_count"], len(rows))
        self.assertGreaterEqual(len(rows), 10)
        self.assertEqual(rows[0]["device_timestamp_ms"], "100")
        self.assertEqual(rows[0]["stateEstimate.z"], "0.6")

    def test_raw_failure_retained_before_bounds(self):
        for mode, raw in (("divergent", "-2.814063310623169"), ("nonfinite", "nan"), ("missing", "None")):
            with self.subTest(mode=mode):
                health, error, result, rows = self.run_case(mode)
                self.assertIsNone(health)
                self.assertIsInstance(error, subject.PreparationError)
                self.assertEqual(result["status"], "FAILED")
                self.assertIn(raw, [row["stateEstimate.z"] for row in rows])

    def test_incomplete_windows(self):
        for mode, expected in (("connect_error", 0), ("start_error", 0), ("insufficient", 3), ("log_error", 4), ("interrupt", 4)):
            with self.subTest(mode=mode):
                health, error, result, rows = self.run_case(mode)
                self.assertIsNone(health)
                self.assertIsNotNone(error)
                self.assertEqual(result["status"], "FAILED")
                self.assertEqual(len(rows), expected)
                self.assertIsNotNone(result["error"])

    def test_write_failure_cannot_admit(self):
        health, error, result, _rows = self.run_case("healthy", write_failure=True)
        self.assertIsNone(health)
        self.assertIsInstance(error, subject.PreparationError)
        self.assertIn("synthetic disk failure", result["error"])
        self.assertEqual(result["status"], "FAILED")

    def test_teardown_failure_is_retained(self):
        health, error, result, rows = self.run_case("teardown_error")
        self.assertIsNone(health)
        self.assertIsNotNone(error)
        self.assertGreaterEqual(len(rows), 10)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["health"]["status"], "HEALTHY")
        self.assertIn("synthetic teardown failure", result["error"])

    def test_existing_sidecar_rejected_before_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "capture.health"
            output.mkdir()
            record = Path(temp) / "prepared.json"
            record.write_bytes(b"synthetic bytes")
            sentinel = output / "health-samples.csv"
            sentinel.write_bytes(b"existing evidence")
            with patch.object(subject, "open_live_crazyflie") as connect:
                with self.assertRaises(FileExistsError):
                    subject.verify_live_health(URI, evidence_output=output, preparation_record=record)
                connect.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"existing evidence")


if __name__ == "__main__":
    unittest.main()
