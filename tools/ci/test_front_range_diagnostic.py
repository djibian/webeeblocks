#!/usr/bin/env python3
"""Exercise the actual diagnostic logging path with no hardware effects."""
import csv
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/physical"))
import diagnose_front_range as subject
import probe_reference_hardware as probe
import prepare_physical_flight as preparation
import test_physical_range_observer as fixtures

URI = "radio://0/80/2M"
EXPECTED = {
    "firmware.revision0": ("uint32_t", 0x54F31E24),
    "firmware.revision1": ("uint16_t", 0x3A0B),
    "firmware.modified": ("uint8_t", 0),
    "stabilizer.estimator": ("uint8_t", 2),
    "stabilizer.controller": ("uint8_t", 1),
}
DESCRIPTOR = {
    "connected": True, "executionAuthority": False,
    "hardware": ["flow-deck-v2", "multi-ranger-deck"],
    "identity": {"model": "crazyflie-2.1", "modelEvidence": "verified"},
    "evidence": {"protocolVersion": 12, "systemSelfTestPassed": True,
        "firmware": {"revision0": 0x54F31E24, "revision1": 0x3A0B, "modified": False},
        "flightConfiguration": {"estimator": 2, "controller": 1}},
}


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / "package"
        binary = self.root / preparation.FIRMWARE_RELATIVE
        binary.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / preparation.FIRMWARE_RELATIVE, binary)
        (self.root / "SOURCE_SHA").write_text("a" * 40)
        def install(_uri, _binary, observed):
            observed.update(device_type="Crazyflie 2.1", protocol_raw="12")
            observed["readbacks"].update({k: {"ctype": t, "value": v, "raw": repr(str(v))}
                                        for k, (t, v) in EXPECTED.items()})
        preparation.prepare(self.root, URI, self.base / "prepared", True, installer=install)
        self.record = self.base / "prepared/preparation.json"
        self.geometry = self.base / "geometry.json"
        self.geometry.write_text(json.dumps({"target_distance_m": 0.5, "uncertainty_m": 0.01,
                                            "method": "independent measured board, stationary vehicle"}))

    def run_case(self, mode="healthy"):
        output = self.base / mode
        cf = fixtures.FakeCf("range.front")
        cf.connection_lost = fixtures.FakeCaller()
        cf.state = 3
        def forbidden(*_args):
            raise AssertionError("physical/configuration/normal Commander-close effect")
        cf.close_link = forbidden
        cf.commander = types.SimpleNamespace(send_setpoint=forbidden)
        cf.param = types.SimpleNamespace(set_value=forbidden)
        events = []
        reads = []
        now = [10.0]
        config = fixtures.FakeConfig("range.front", initial_sample=(100, 500))
        config.add_variable = lambda name, ctype: events.append((name, ctype))
        if mode == "start": config.start_error = RuntimeError("start error")
        if mode == "stop": config.stop_error = RuntimeError("stop error")
        class Link:
            def close(self):
                events.append("close")
                if mode == "close": raise RuntimeError("close error")
        cf.link = Link()
        class Adapter:
            def __init__(self, actual):
                if actual is not cf: raise AssertionError("wrong link")
            def describe(self, name):
                return (*EXPECTED.get(name, ("uint16_t", 1))[:1], False, "wrong cached value")
            def read_fresh(self, name):
                reads.append(name)
                value = EXPECTED.get(name, ("uint16_t", 1))[1]
                if mode == "mask" and name == "multiranger.filterMask": value = 65535
                return str(value)
            write = forbidden
        count = [1]
        def sleep(duration):
            now[0] += duration
            if mode == "timeout": return
            if mode == "interrupt": raise KeyboardInterrupt("operator stopped")
            if mode == "disconnect": cf.disconnected.call(URI); return
            count[0] += 1
            stamp = 100 if mode == "duplicate" else count[0] * 100
            raw = None if mode == "malformed" else 32766 if mode == "unavailable" else 500
            config.emit(stamp, raw)
        log = types.ModuleType("cflib.crazyflie.log")
        log.LogConfig = lambda name, period: config if period == 100 else forbidden()
        descriptor = copy.deepcopy(DESCRIPTOR)
        if mode == "no_deck": descriptor["hardware"] = ["flow-deck-v2"]
        if mode == "wrong_firmware": descriptor["evidence"]["firmware"]["modified"] = True
        original_window = subject.RawWindow
        def make_window(*args):
            window = original_window(*args)
            if mode == "write":
                writer = window.writer
                class Writer:
                    def writerow(self, row):
                        if window.count >= 1: raise OSError("synthetic disk full")
                        writer.writerow(row)
                window.writer = Writer()
            return window
        with patch.dict(sys.modules, {"cflib": types.ModuleType("cflib"),
                "cflib.crazyflie": types.ModuleType("cflib.crazyflie"), "cflib.crazyflie.log": log}), \
             patch.object(subject, "open_live_crazyflie", lambda uri: cf), \
             patch.object(subject, "CflibParamAdapter", Adapter), \
             patch.object(probe, "_read_connected_descriptor", lambda _: descriptor), \
             patch.object(subject, "RawWindow", make_window), \
             patch.object(subject, "time", types.SimpleNamespace(monotonic=lambda: now[0], sleep=sleep)):
            status = subject.diagnose(self.root, URI, self.record, self.geometry, output, True)
        result = json.loads((output / "diagnostic-result.json").read_text())
        with (output / "front-range.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        before = (output / "front-range.csv").read_bytes()
        config.emit(999999, 10)
        self.assertEqual((output / "front-range.csv").read_bytes(), before, "late callback changed sealed evidence")
        self.assertEqual((output / "preparation-record.json").read_bytes(), self.record.read_bytes())
        self.assertIsNone(result["physical_verdict"])
        self.assertIs(result["execution_authority"], False)
        self.assertEqual(events.count("close"), 1)
        if mode not in ("mask", "no_deck", "wrong_firmware"):
            self.assertEqual(events[0], ("range.front", "uint16_t"))
        self.assertEqual(reads, [] if mode in ("no_deck", "wrong_firmware") else [*EXPECTED, "multiranger.filterMask"])
        return status, result, rows

    def test_actual_live_healthy_and_unavailable_windows(self):
        for mode in ("healthy", "unavailable"):
            with self.subTest(mode=mode):
                status, result, rows = self.run_case(mode)
                self.assertEqual(status, 0)
                self.assertEqual(result["status"], "OBSERVED")
                self.assertGreater(len(rows), 10)
                if mode == "unavailable":
                    self.assertEqual(rows[-1]["raw_mm"], "32766")
                    self.assertEqual(rows[-1]["classification"], "unavailable")

    def test_failures_are_retained_without_reconnection(self):
        for mode in ("no_deck", "wrong_firmware", "mask", "start", "stop", "close", "write", "timeout", "interrupt", "disconnect", "duplicate", "malformed"):
            with self.subTest(mode=mode):
                status, result, rows = self.run_case(mode)
                self.assertEqual(status, 1)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertTrue(result["errors"])
                if mode == "malformed": self.assertEqual(rows[-1]["raw_mm"], "None")
                if mode == "duplicate": self.assertEqual(rows[-1]["device_timestamp_ms"], "100")

    def test_local_rejection_never_opens_hardware_or_overwrites(self):
        calls = []
        def capture(*_): calls.append(1)
        output = self.base / "existing"
        output.mkdir(); (output / "sentinel").write_bytes(b"exact old evidence")
        for props, uri, target in ((False, URI, self.base / "new"), (True, "usb://0", self.base / "new"),
                                   (True, URI, output), (True, URI, self.root / "inside")):
            with self.assertRaises(Exception):
                subject.diagnose(self.root, uri, self.record, self.geometry, target, props, capture=capture)
        self.geometry.write_text('{"target_distance_m": NaN}')
        with self.assertRaises(Exception):
            subject.diagnose(self.root, URI, self.record, self.geometry, self.base / "new", True, capture=capture)
        self.assertFalse(calls)
        self.assertEqual((output / "sentinel").read_bytes(), b"exact old evidence")


if __name__ == "__main__":
    unittest.main()
