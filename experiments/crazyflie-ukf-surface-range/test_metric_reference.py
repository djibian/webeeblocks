#!/usr/bin/env python3
"""Synthetic reference arithmetic and provenance controls; no physical result."""

import copy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import metric_reference as subject


def example():
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


class ReferenceTests(unittest.TestCase):
    def result(self, spec=None):
        return subject.analyze(spec or example(), Fraction(100), {"reference"})

    def test_signed_mixed_round_trip_and_same_arithmetic_for_every_label(self):
        spec = example()
        reverse = copy.deepcopy(spec["events"][0])
        reverse.update(id="exit", start_reference_s=[40, 40], end_reference_s=[41, 41])
        for before, after in (("z_before_m", "z_after_m"), ("surface_before_m", "surface_after_m")):
            reverse[before], reverse[after] = reverse[after], reverse[before]
        spec["events"].append(reverse)
        result = self.result(spec)
        for event, sign in zip(result["events"], (1, -1)):
            for field, expected in (("reference_delta_z_m", sign * Fraction(1, 10)),
                                    ("reference_delta_surface_m", sign * Fraction(1, 5)),
                                    ("reference_delta_clearance_m", -sign * Fraction(1, 10))):
                self.assertLessEqual(Fraction(event[field][0]), expected)
                self.assertGreaterEqual(Fraction(event[field][1]), expected)
                self.assertAlmostEqual(event[field][0], float(expected))
        baseline = result["events"][0]
        for kind in subject.KINDS:
            spec["events"][0]["kind"] = kind
            observed = self.result(spec)["events"][0]
            self.assertEqual({k: v for k, v in observed.items() if k != "kind"},
                             {k: v for k, v in baseline.items() if k != "kind"})
        self.assertEqual(result["independent_displacement_verdict"], "UNPROVEN")
        self.assertIsNone(result["physical_verdict"])
        self.assertFalse(result["physical_reference_validated"])
        self.assertFalse(result["affine_clock_validated"])

    def test_metric_bounds_are_not_collapsed_to_midpoints(self):
        spec = example()
        spec["events"][0].update(z_before_m=[0.99, 1.01], z_after_m=[1.08, 1.12])
        event = self.result(spec)["events"][0]
        self.assertLessEqual(Fraction(event["reference_delta_z_m"][0]), Fraction(7, 100))
        self.assertGreaterEqual(Fraction(event["reference_delta_z_m"][1]), Fraction(13, 100))

    def test_affine_clock_preserves_correlated_rate_and_offset(self):
        spec = example()
        spec["clock"]["anchors"][0]["device_s"] = [0, 0.2]
        spec["clock"]["anchors"][1]["device_s"] = [99.8, 100]
        polygon, domain = subject.clocks(spec["clock"]["anchors"], {"reference"})
        bound = subject.mapped([50, 50], polygon, domain)
        self.assertEqual(bound, (Fraction(499, 10), Fraction(501, 10)))
        # Independent analytic check: convex interpolation of uncertain endpoint
        # observations. An axis-aligned rate/offset box would be needlessly wider.
        for left in range(21):
            for right in range(21):
                d0, d1 = Fraction(left, 100), Fraction(9980 + right, 100)
                midpoint = (d0 + d1) / 2
                self.assertLessEqual(bound[0], midpoint)
                self.assertGreaterEqual(bound[1], midpoint)
        spec["events"][0]["start_reference_s"] = [36, 36.1]
        event = self.result(spec)["events"][0]
        self.assertLess(event["start_device_s"][0], event["start_device_s"][1])

    def test_inconsistent_interior_sync_observation_is_rejected(self):
        spec = example()
        spec["clock"]["anchors"].insert(1, {"reference_s": [50, 50], "device_s": [60, 60],
                                              "witness": spec["calibration"]["witness"]})
        with self.assertRaisesRegex(ValueError, "no common affine"):
            self.result(spec)

    def test_nonzero_reference_anchor_uncertainty_encloses_clock(self):
        spec = example()
        spec["clock"]["anchors"][0].update(reference_s=[0, 0.1], device_s=[0, 0.2])
        spec["clock"]["anchors"][1].update(reference_s=[99.9, 100], device_s=[99.8, 100])
        polygon, domain = subject.clocks(spec["clock"]["anchors"], {"reference"})
        lo, hi = subject.mapped([50, 50], polygon, domain)
        self.assertLessEqual(lo, 50)
        self.assertGreaterEqual(hi, 50)
        with self.assertRaisesRegex(ValueError, "extrapolate"):
            subject.mapped([0, 0], polygon, domain)

    def test_uncertainty_cannot_hide_invalid_duration_plateaus_or_coverage(self):
        for change in (
            lambda s: s["calibration"].update(end_reference_s=[29.9, 32]),
            lambda s: s["events"][0].update(start_reference_s=[33.9, 36]),
            lambda s: s["events"][0].update(end_reference_s=[35.9, 37]),
            lambda s: s["events"][0].update(end_reference_s=[99.5, 100]),
        ):
            spec = example()
            change(spec)
            with self.assertRaises(ValueError):
                self.result(spec)

    def test_clock_basis_and_external_witness_are_required(self):
        for change in (
            lambda s: s["clock"].update(device_origin="host-receipt-time"),
            lambda s: s["clock"].update(model="unknown"),
            lambda s: s["events"][0].update(witness={"source": "barometer", "locator": "UKF Z"}),
            lambda s: s["events"][0].update(z_after_m=[float("nan"), 1]),
            lambda s: s["events"][0].update(surface_after_m=[2, 2]),
        ):
            spec = example()
            change(spec)
            with self.assertRaises(ValueError):
                self.result(spec)

    def test_post_window_cannot_extend_past_sync_even_when_raw_capture_continues(self):
        spec = example()
        spec["clock"]["anchors"][-1].update(reference_s=[37.5, 37.5], device_s=[37.5, 37.5])
        with self.assertRaisesRegex(ValueError, "recording/synchronization"):
            self.result(spec)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        baro = "cf_timestamp_ms,host_monotonic_s,baro.asl,baro.pressure,baro.temp\n"
        baro += "".join(f"{i * 20},{1000 + i * 0.02:.2f},1,1000,20\n" for i in range(5001))
        (self.root / "barometer.csv").write_text(baro)
        (self.root / "reference.txt").write_text("SYNTHETIC observations only; no physical reference.\n")
        self.spec = example()
        self.spec["sources"] = [
            {"id": identifier, "path": name, "kind": kind,
             "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}
            for identifier, name, kind in (("barometer", "barometer.csv", "barometer-capture"),
                                            ("reference", "reference.txt", "external-metric-reference"))]
        self.path = self.root / "spec.json"

    def write(self):
        self.path.write_text(json.dumps(self.spec))

    def test_exact_input_provenance_and_successful_cli_without_overwrite(self):
        self.write()
        result = subject.run(self.path)
        self.assertEqual(result["input_provenance"]["specification_sha256"],
                         hashlib.sha256(self.path.read_bytes()).hexdigest())
        command = [sys.executable, str(Path(subject.__file__)), str(self.path), "--output", str(self.root / "result.json")]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        original = (self.root / "result.json").read_bytes()
        second = subprocess.run(command, capture_output=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn(b"UNPROVEN", second.stderr)
        self.assertEqual((self.root / "result.json").read_bytes(), original)

    def test_changed_missing_reused_or_escaping_source_is_rejected(self):
        self.write()
        original = (self.root / "reference.txt").read_bytes()
        (self.root / "reference.txt").write_bytes(original + b"changed")
        with self.assertRaisesRegex(ValueError, "digest"):
            subject.run(self.path)
        (self.root / "reference.txt").write_bytes(original)
        for path in ("missing.txt", "../reference.txt", "/etc/hosts", "barometer.csv"):
            self.spec["sources"][1]["path"] = path
            self.write()
            with self.assertRaises(ValueError):
                subject.run(self.path)

    def test_hard_link_cannot_alias_barometer_as_external_reference(self):
        alias = self.root / "reference-hardlink.txt"
        os.link(self.root / "barometer.csv", alias)
        self.spec["sources"][1].update(
            path=alias.name,
            sha256=hashlib.sha256(alias.read_bytes()).hexdigest(),
        )
        self.write()
        with self.assertRaisesRegex(ValueError, "one file cannot act as two independent sources"):
            subject.run(self.path)

    def test_duplicate_json_and_wrong_capture_are_rejected(self):
        self.write()
        self.path.write_text('{"schema":"shadow",' + self.path.read_text()[1:])
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            subject.run(self.path)
        (self.root / "barometer.csv").write_text("host_monotonic_s,stateEstimate.z\n1000,1\n")
        self.spec["sources"][0]["sha256"] = hashlib.sha256((self.root / "barometer.csv").read_bytes()).hexdigest()
        self.write()
        with self.assertRaisesRegex(ValueError, "continuous barometer"):
            subject.run(self.path)


if __name__ == "__main__":
    unittest.main()
