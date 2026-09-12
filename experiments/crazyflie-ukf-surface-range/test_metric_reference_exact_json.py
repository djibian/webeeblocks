#!/usr/bin/env python3
"""File-boundary regressions for exact X3 metric-reference JSON decimals."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import metric_reference as subject


def base_spec():
    witness = {"source": "reference", "locator": "synthetic fixture, not a measurement"}
    return {
        "schema": "webeeblocks.x3.metric-reference-input.v1",
        "clock": {"model": "affine", "device_origin": "first-barometer-log-row",
                  "barometer_source": "barometer", "anchors": [
                      {"reference_s": [0, 0], "device_s": [0, 0], "witness": witness},
                      {"reference_s": [100, 100], "device_s": [100, 100], "witness": witness}]},
        "calibration": {"start_reference_s": [0, 0], "end_reference_s": [32, 32], "witness": witness},
        "events": [{"id": "entry", "kind": "mixed", "start_reference_s": [36, 36],
                    "end_reference_s": [37, 37], "z_before_m": [1, 1], "z_after_m": [1.1, 1.1],
                    "surface_before_m": [0, 0], "surface_after_m": [0.2, 0.2], "witness": witness}],
    }


class ExactJsonFileBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        barometer = "cf_timestamp_ms,host_monotonic_s,baro.asl,baro.pressure,baro.temp\n"
        barometer += "".join(f"{i * 20},{1000 + i * 0.02:.2f},1,1000,20\n" for i in range(5001))
        (self.root / "barometer.csv").write_text(barometer)
        (self.root / "reference.txt").write_text("SYNTHETIC observations only; no physical reference.\n")
        self.spec = base_spec()
        self.spec["sources"] = [
            {"id": identifier, "path": name, "kind": kind,
             "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}
            for identifier, name, kind in (("barometer", "barometer.csv", "barometer-capture"),
                                            ("reference", "reference.txt", "external-metric-reference"))]
        self.path = self.root / "spec.json"

    def write_with_raw_decimal(self, marker, literal):
        text = json.dumps(self.spec)
        quoted = json.dumps(marker)
        self.assertIn(quoted, text)
        self.path.write_text(text.replace(quoted, literal))

    def test_decimal_sync_contradiction_survives_json_file_entry(self):
        witness = self.spec["calibration"]["witness"]
        self.spec["clock"]["anchors"].insert(
            1, {"reference_s": [50, 50], "device_s": ["EXACT_DEVICE", "EXACT_DEVICE"],
                "witness": witness})
        self.write_with_raw_decimal("EXACT_DEVICE", "50.000000000000001")
        with self.assertRaisesRegex(ValueError, "no common affine"):
            subject.run(self.path)

    def test_sub_float_metric_displacement_does_not_collapse_to_zero(self):
        self.spec["events"][0]["z_after_m"] = ["EXACT_Z", "EXACT_Z"]
        self.spec["events"][0]["surface_after_m"] = [0, 0]
        self.write_with_raw_decimal("EXACT_Z", "1.00000000000000001")
        result = subject.run(self.path)
        delta = result["events"][0]["reference_delta_z_m"]
        self.assertGreater(delta[0], 0.0)
        self.assertGreaterEqual(delta[1], delta[0])


if __name__ == "__main__":
    unittest.main()
