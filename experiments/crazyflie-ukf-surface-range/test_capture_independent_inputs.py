#!/usr/bin/env python3
"""Deterministic acquisition tests. All telemetry/links here are synthetic."""

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import capture_independent_inputs as capture


class Event:
    def __init__(self):
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_required_live_signals_and_unchanged_parameters(self):
        available = {v for _, names in capture.BLOCKS.values() for v in names}
        values = {k: str(v) for k, v in capture.PARAMETERS.items()}
        cf = SimpleNamespace(
            log=SimpleNamespace(toc=SimpleNamespace(get_element_by_complete_name=lambda n: n if n in available else None)),
            param=SimpleNamespace(get_value=lambda n: values[n]),
        )
        self.assertEqual(capture.require_inputs(cf), values)
        available.remove("baro.asl")
        with self.assertRaisesRegex(ValueError, "baro.asl"):
            capture.require_inputs(cf)
        available.add("baro.asl")
        values["ukf.qualityGateTof"] = "100"
        with self.assertRaisesRegex(ValueError, "unchanged"):
            capture.require_inputs(cf)
        self.assertTrue(all(4 * len(names) <= 26 and period % 10 == 0
                            for period, names in capture.BLOCKS.values()))

    def test_invalid_samples_preserved_and_timestamp_wrap_distinguished(self):
        recorder = capture.Recorder(self.root)
        cb = recorder.callback("barometer")
        data = {"baro.asl": 10.0, "baro.pressure": 1013.0, "baro.temp": 20.0}
        cb((1 << 24) - 10, data, None)
        cb(10, data, None)  # genuine forward 24-bit wrap, 20 ms
        self.assertIsNone(recorder.error)
        cb(10, data, None)  # duplicate, not a new sensor observation
        self.assertIn("duplicate", recorder.error)
        cb(30, {"baro.asl": float("nan")}, None)
        recorder.close()
        with (self.root / "barometer.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1]["baro.asl"], "nan")
        self.assertEqual(rows[-1]["baro.pressure"], "")
        self.assertEqual(recorder.stats["barometer"]["invalid_rows"], 1)
        self.assertEqual(recorder.stats["barometer"]["max_gap_ms"], 20)

    def test_large_gap_and_stopped_stream_are_incomplete(self):
        recorder = capture.Recorder(self.root)
        self.addCleanup(recorder.close)
        with patch.object(capture.time, "monotonic", return_value=100.0):
            for name, (period, columns) in capture.BLOCKS.items():
                callback = recorder.callback(name)
                data = dict.fromkeys(columns, 0.0)
                callback(1000, data, None)
                callback(1000 + period, data, None)
            self.assertTrue(recorder.check_streams())
        with patch.object(capture.time, "monotonic", return_value=101.1):
            with self.assertRaisesRegex(RuntimeError, "stopped"):
                recorder.check_streams()
        recorder.callback("barometer")(1140, dict.fromkeys(capture.BLOCKS["barometer"][1], 0.0), None)
        with self.assertRaisesRegex(RuntimeError, "gap"):
            recorder.check_streams()
        self.assertEqual(recorder.stats["barometer"]["max_gap_ms"], 120)

    def fake_record(self, *, omit=None, interrupt=False, bad_stop=False, no_connection=False):
        configs = []
        clock = [1000.0]
        class Config:
            def __init__(self, name, period):
                self.name, self.period, self.columns = name, period, []
                self.data_received_cb, self.error_cb = Event(), Event()
                self.active = False
                configs.append(self)
            def add_variable(self, name, fetch_as):
                assert fetch_as == "float"
                self.columns.append(name)
            def start(self):
                self.active = True
            def stop(self):
                self.active = False
                if bad_stop:
                    raise RuntimeError("synthetic log stop failure")
        class CF:
            def __init__(self, **_):
                self.connection_lost, self.connection_failed, self.fully_connected = Event(), Event(), Event()
                self.log = SimpleNamespace(
                    toc=SimpleNamespace(get_element_by_complete_name=lambda _: object()),
                    add_config=lambda _: None,
                )
                self.param = SimpleNamespace(get_value=lambda n: str(capture.PARAMETERS[n]))
            def open_link(self, uri):
                if not no_connection:
                    self.fully_connected.emit(uri)
            def close_link(self):
                pass
        def sleep(seconds):
            clock[0] += seconds
            if interrupt and clock[0] > 1000.2:
                raise KeyboardInterrupt("synthetic interruption")
            stamp = round(clock[0] * 1000) % (1 << 24)
            for conf in configs:
                if conf.active and conf.name != omit:
                    conf.data_received_cb.emit(stamp, {v: 0.0 for v in conf.columns}, conf)
        modules = {n: ModuleType(n) for n in (
            "cflib", "cflib.crtp", "cflib.crazyflie", "cflib.crazyflie.log",
        )}
        modules["cflib"].__file__ = __file__
        modules["cflib"].crtp = modules["cflib.crtp"]
        modules["cflib.crtp"].init_drivers = lambda: None
        modules["cflib.crazyflie"].Crazyflie = CF
        modules["cflib.crazyflie.log"].LogConfig = Config
        modules["cflib.crazyflie.log"].__file__ = __file__
        binary = self.root / "synthetic.bin"
        binary.write_bytes(b"SYNTHETIC FIRMWARE FIXTURE, NOT A FLIGHT ARTIFACT")
        args = SimpleNamespace(
            props_removed=True, installed_bin_confirmed=True, firmware_bin=binary,
            uri="radio://0/80/2M", checkpoint_url="https://github.com/djibian/webeeblocks/issues/251",
            request_sha=capture.FIRMWARE_TARGET,
            output=self.root / "capture", seconds=30,
        )
        with patch.dict("sys.modules", modules), patch.object(capture.time, "monotonic", lambda: clock[0]), \
             patch.object(capture.time, "sleep", sleep), \
             patch.object(capture, "FIRMWARE_BIN_SHA256", hashlib.sha256(binary.read_bytes()).hexdigest()), \
             contextlib.redirect_stdout(io.StringIO()):
            result = capture.record(args)
        return result, json.loads((args.output / "capture-result.json").read_text())

    def test_complete_acquisition_is_not_a_physical_verdict(self):
        code, result = self.fake_record()
        self.assertEqual(code, 0)
        self.assertEqual(result["capture_status"], "CAPTURED")
        self.assertIsNone(result["physical_verdict"])
        self.assertTrue(all(s["rows"] > 100 for s in result["streams"].values()))
        self.assertEqual(len(list((self.root / "capture").glob("*.csv"))), 4)

    def test_missing_stream_retains_incomplete_output(self):
        code, result = self.fake_record(omit="X3_barometer")
        self.assertEqual(code, 1)
        self.assertEqual(result["capture_status"], "INCOMPLETE")
        self.assertEqual(result["streams"]["barometer"]["rows"], 0)
        self.assertGreater(result["streams"]["imu"]["rows"], 0)
        self.assertFalse((self.root / "capture" / "recording-ready.json").exists())

    def test_connection_or_parameter_download_timeout_is_incomplete(self):
        code, result = self.fake_record(no_connection=True)
        self.assertEqual(code, 1)
        self.assertIn("within 30 s", result["error"])
        self.assertEqual(result["capture_status"], "INCOMPLETE")
        self.assertTrue(all(s["rows"] == 0 for s in result["streams"].values()))
        self.assertFalse((self.root / "capture" / "recording-ready.json").exists())

    def test_interruption_and_uncertain_stop_cannot_report_completion(self):
        code, result = self.fake_record(interrupt=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["capture_status"], "INCOMPLETE")
        self.assertIn("KeyboardInterrupt", result["error"])

    def test_log_stop_error_is_retained(self):
        code, result = self.fake_record(bad_stop=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["capture_status"], "INCOMPLETE")
        self.assertIn("stop", result["error"])

    def test_wrong_binary_or_missing_confirmation_cannot_open_link(self):
        binary = self.root / "wrong.bin"
        binary.write_bytes(b"wrong")
        args = SimpleNamespace(props_removed=False, installed_bin_confirmed=True, firmware_bin=binary)
        with self.assertRaisesRegex(ValueError, "confirmed"):
            capture.record(args)
        args.props_removed = True
        with self.assertRaisesRegex(ValueError, "exact #251"):
            capture.record(args)
        # These failures occur before cflib is imported and before output creation.


if __name__ == "__main__":
    unittest.main()
