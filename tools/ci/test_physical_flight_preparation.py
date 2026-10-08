#!/usr/bin/env python3
"""Exercise the production props-off preparation and its no-effect admission."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/physical"))
import prepare_physical_flight as subject
import prepare_x3_independent_capture as x3
import probe_reference_hardware as probe

URI = "radio://0/80/2M"
# Independent expected release metadata/types, not generated from the validator.
HEALTHY = {
    "firmware.revision0": {"ctype": "uint32_t", "value": 0x54F31E24, "raw": repr(str(0x54F31E24))},
    "firmware.revision1": {"ctype": "uint16_t", "value": 0x3A0B, "raw": repr(str(0x3A0B))},
    "firmware.modified": {"ctype": "uint8_t", "value": 0, "raw": "'0'"},
    "stabilizer.estimator": {"ctype": "uint8_t", "value": 2, "raw": "'2'"},
    "stabilizer.controller": {"ctype": "uint8_t", "value": 1, "raw": "'1'"},
}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "package"
        binary = self.root / subject.FIRMWARE_RELATIVE
        binary.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / subject.FIRMWARE_RELATIVE, binary)
        (self.root / "SOURCE_SHA").write_text("a" * 40 + "\n")
        self.output = Path(self.temp.name) / "preparation"
        self.calls = []

    def installer(self, uri, binary, observations):
        self.calls.append((uri, binary))
        self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(),
                         "9b745fe76da30e071ba8e04e6a8535d1dbd747d7ce6ca72d2d3ccf8c18978298")
        self.assertTrue((self.output / "preparation-start.json").is_file())
        observations["device_type"] = "Crazyflie 2.1"
        observations["protocol_raw"] = "12"
        observations["readbacks"].update(copy.deepcopy(HEALTHY))

    def prepare(self, installer=None):
        return subject.prepare(self.root, URI, self.output, True,
                               installer=installer or self.installer)

    def test_success_and_exact_record_binding_without_hardware(self):
        value = self.prepare()
        self.assertEqual(value["status"], "PREPARED")
        self.assertEqual(len(self.calls), 1)
        record = self.output / "preparation.json"
        self.assertEqual(subject.verify_record(self.root, URI, record), value)
        for key, wrong in (("source_sha", "b" * 40), ("uri", "radio://0/81/2M"),
                           ("status", "FAILED"), ("execution_authority", True),
                           ("props_removed", False), ("firmware", {}), ("observations", {})):
            candidate = {**value, key: wrong}
            record.write_text(json.dumps(candidate))
            with self.assertRaises(subject.FlightPreparationError):
                subject.verify_record(self.root, URI, record)
        self.assertEqual(len(self.calls), 1, "record verification must not install/connect")

    def test_bad_local_admission_and_existing_output_do_not_install(self):
        for uri, props in ((URI, False), ("usb://0", True)):
            with self.assertRaises(subject.FlightPreparationError):
                subject.prepare(self.root, uri, self.output, props, installer=self.installer)
        with self.assertRaises(subject.FlightPreparationError):
            subject.prepare(self.root, URI, self.root / "new-output", True, installer=self.installer)
        binary = self.root / subject.FIRMWARE_RELATIVE
        original = binary.read_bytes()
        binary.write_bytes(original + b"x")
        with self.assertRaises(subject.FlightPreparationError):
            self.prepare()
        binary.write_bytes(original)
        binary.unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        binary.write_bytes(original)
        self.output.mkdir()
        sentinel = self.output / "preparation.json"
        sentinel.write_bytes(b"existing evidence")
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertFalse(self.calls)
        self.assertEqual(sentinel.read_bytes(), b"existing evidence")

    def test_failed_interrupted_and_bad_readbacks_are_retained_once(self):
        for label in ("flash", "interrupt", "ukf", "wrong_type", "missing"):
            output = self.output / label
            calls = []
            def install(_uri, _binary, observations):
                calls.append(label)
                observations["readbacks"].update(copy.deepcopy(HEALTHY))
                if label == "flash":
                    raise RuntimeError("ambiguous flash transport")
                if label == "interrupt":
                    raise KeyboardInterrupt("operator interruption")
                if label == "ukf":
                    observations["readbacks"]["stabilizer.estimator"]["value"] = 3
                if label == "wrong_type":
                    observations["readbacks"]["firmware.revision1"]["ctype"] = "float"
                if label == "missing":
                    del observations["readbacks"]["stabilizer.controller"]
            with self.subTest(label=label):
                with self.assertRaises(BaseException):
                    subject.prepare(self.root, URI, output, True, installer=install)
                value = json.loads((output / "preparation.json").read_text())
                self.assertEqual(value["status"], "FAILED")
                self.assertIsNotNone(value["error"])
                self.assertFalse(value["execution_authority"])
                self.assertEqual(calls, [label])
                with self.assertRaises(subject.FlightPreparationError):
                    subject.verify_record(self.root, URI, output / "preparation.json")

    def test_actual_live_path_flashes_once_reads_fresh_and_never_writes_configuration(self):
        events = []
        def forbidden(*_args, **_kwargs):
            raise AssertionError("Commander/configuration effect attempted")
        cf = types.SimpleNamespace(state=3, platform=types.SimpleNamespace(get_protocol_version=lambda: 12),
                                   commander=types.SimpleNamespace(send_setpoint=forbidden), close_link=forbidden)
        class Adapter:
            def __init__(self, actual):
                self.assert_identity = actual is cf
            def describe(self, name):
                return HEALTHY[name]["ctype"], False, "wrong cached value"
            def read_fresh(self, name):
                events.append(("fresh", name))
                return str(HEALTHY[name]["value"])
            write = forbidden
        def flash(uri, binary):
            events.append(("flash", uri, binary.name))
        with patch.object(subject, "flash_exact_firmware", flash), \
             patch.object(x3, "open_live_crazyflie", lambda uri: cf), \
             patch.object(x3, "CflibParamAdapter", Adapter), \
             patch.object(probe, "_read_device_type_name", lambda actual: "Crazyflie 2.1"):
            value = self.prepare(subject.live_install)
        self.assertEqual(value["status"], "PREPARED")
        self.assertEqual(events, [("flash", URI, "cf2-2026.08.bin")] +
                         [("fresh", name) for name in HEALTHY])
        self.assertEqual(cf.state, 0, "actual no-Commander teardown must run")

    def test_real_bootloader_adapter_is_stm32_only_and_ambiguity_never_opens_cf(self):
        for failure in (None, "start", "flash", "reset", "close"):
            events = []
            class Bootloader:
                def __init__(self, clink):
                    events.append(("bootloader", clink))
                def start_bootloader(self, *, warm_boot, cf):
                    events.append(("start", warm_boot, cf))
                    return failure != "start"
                def flash(self, filename, targets, *, cf, enable_console_log, boot_delay):
                    events.append(("flash", Path(filename).name, targets, cf, enable_console_log, boot_delay))
                    if failure == "flash":
                        raise RuntimeError("flash uncertain")
                def reset_to_firmware(self, *, boot_delay):
                    events.append(("reset", boot_delay))
                    return failure != "reset"
                def close(self):
                    events.append(("close",))
                    if failure == "close":
                        raise RuntimeError("bootloader close uncertain")
            crtp = types.ModuleType("cflib.crtp")
            crtp.init_drivers = lambda: events.append(("drivers",))
            cflib = types.ModuleType("cflib"); cflib.crtp = crtp
            boot = types.ModuleType("cflib.bootloader")
            boot.Bootloader = Bootloader; boot.Target = lambda *args: args
            with self.subTest(failure=failure), patch.dict(sys.modules, {
                    "cflib": cflib, "cflib.crtp": crtp, "cflib.bootloader": boot}):
                if failure:
                    with self.assertRaises(Exception):
                        subject.flash_exact_firmware(URI, self.root / subject.FIRMWARE_RELATIVE)
                else:
                    subject.flash_exact_firmware(URI, self.root / subject.FIRMWARE_RELATIVE)
                    self.assertEqual(events, [("drivers",), ("bootloader", URI),
                        ("start", True, None), ("flash", "cf2-2026.08.bin",
                        [("cf2", "stm32", "fw", [], [])], None, False, 5.0),
                        ("reset", 5.0), ("close",)])
                self.assertEqual(events[-1], ("close",))
                self.assertLessEqual(sum(event[0] == "flash" for event in events), 1)

    def test_live_readback_and_teardown_failures_preserve_both_causes(self):
        class Link:
            def close(self):
                raise RuntimeError("teardown transport failure")
        cf = types.SimpleNamespace(state=3, link=Link(),
            platform=types.SimpleNamespace(get_protocol_version=lambda: 12))
        class Adapter:
            def __init__(self, actual):
                pass
            def describe(self, name):
                return HEALTHY[name]["ctype"], False, None
            def read_fresh(self, name):
                if name == "stabilizer.estimator":
                    raise RuntimeError("fresh estimator read failed")
                return str(HEALTHY[name]["value"])
        calls = []
        with patch.object(subject, "flash_exact_firmware", lambda *_: calls.append("flash")), \
             patch.object(x3, "open_live_crazyflie", lambda _: cf), \
             patch.object(x3, "CflibParamAdapter", Adapter), \
             patch.object(probe, "_read_device_type_name", lambda _: "Crazyflie 2.1"):
            with self.assertRaises(RuntimeError):
                self.prepare(subject.live_install)
        value = json.loads((self.output / "preparation.json").read_text())
        self.assertEqual(value["status"], "FAILED")
        self.assertEqual(value["error"], ["RuntimeError: teardown transport failure",
                                          "RuntimeError: fresh estimator read failed"])
        self.assertEqual(set(value["readbacks"]), set(list(HEALTHY)[:3]))
        self.assertEqual(calls, ["flash"])

    def test_qualification_runner_requires_preparation_before_other_work(self):
        runner = ROOT / "tools/physical/run_packaged_physical_qualification.sh"
        result = subprocess.run(["bash", str(runner), "--uri", URI], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("exact --preparation-record", result.stderr)


if __name__ == "__main__":
    unittest.main()
