#!/usr/bin/env python3
"""Synthetic arithmetic/data-quality controls, not physical X3 evidence."""

import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import frozen_pressure_probe as probe


def fixture():
    spec = {"schema": "webeeblocks.x3.pressure-probe-input.v1",
            "calibration": {"start_s": 0, "end_s": 30},
            "events": [{"id": kind, "kind": kind, "start_s": 34 + 6 * i,
                        "end_s": 35 + 6 * i} for i, kind in enumerate(probe.KINDS)]}
    # Deliberately synthetic linear pressure drift plus a +0.20 m transition.
    samples = []
    for i in range(3201):
        t = i * 0.02
        z = 100 + 0.002 * t
        for event in spec["events"]:
            z += 0.2 * max(0, min(1, t - event["start_s"]))
        samples.append((t, z))
    return samples, spec


class PressureProbeTests(unittest.TestCase):
    def test_fixed_windows_signed_contrast_and_shared_path(self):
        samples, spec = fixture()
        result = probe.analyze(samples, spec)
        self.assertAlmostEqual(result["calibration_slope_m_per_s"], 0.002)
        for event in result["events"]:
            self.assertAlmostEqual(event["pressure_contrast"]["drift_corrected_delta_m"], 0.2)
            # Medians land at start-0.26 and end+0.50 on this 20 ms grid.
            self.assertAlmostEqual(event["pressure_contrast"]["raw_delta_m"], 0.20352)
            self.assertEqual(event["pressure_contrast"]["after_s"][1], event["end_s"] + 0.75)
            self.assertIsNone(event["uncertainty_bound_m"])
            self.assertIsNone(event["effective_independent_count"])
        negative = probe.analyze([(t, -y) for t, y in samples], spec)
        self.assertAlmostEqual(negative["events"][-1]["pressure_contrast"]["drift_corrected_delta_m"], -0.2)
        self.assertIsNone(result["physical_verdict"])
        self.assertEqual(result["independent_displacement_verdict"], "UNPROVEN")

    def test_terrain_values_cannot_train_calibration_or_windows(self):
        samples, spec = fixture()
        original = probe.analyze(samples, spec)
        altered = probe.analyze([(t, y + (1000 if t >= 35 else 0)) for t, y in samples], spec)
        self.assertEqual(original["calibration_slope_m_per_s"], altered["calibration_slope_m_per_s"])
        for a, b in zip(original["events"], altered["events"]):
            self.assertEqual(a["matched_calibration_pairs"], b["matched_calibration_pairs"])
            self.assertEqual(a["pressure_contrast"]["before_s"], b["pressure_contrast"]["before_s"])

    def test_matched_pairs_preserve_separation_and_do_not_overlap(self):
        samples, spec = fixture()
        event = probe.analyze(samples, spec)["events"][0]
        previous_end = 0
        for pair in event["matched_calibration_pairs"]:
            self.assertGreaterEqual(pair["before_s"][0], previous_end)
            self.assertAlmostEqual(pair["after_s"][0] - pair["before_s"][0], 1.75)
            previous_end = pair["after_s"][1]
            self.assertLessEqual(previous_end, 30)

    def test_missing_coverage_and_invalid_episode_cannot_compute(self):
        samples, spec = fixture()
        with self.assertRaisesRegex(ValueError, "coverage"):
            probe.analyze([(t, y) for t, y in samples if not 33.5 <= t < 34], spec)
        for change in ({"start_s": 20}, {"end_s": float("nan")}, {"kind": "gate-bypass"}):
            invalid = copy.deepcopy(spec)
            invalid["events"][0].update(change)
            with self.assertRaises(ValueError):
                probe.analyze(samples, invalid)

    def test_csv_clock_wrap_and_bad_samples(self):
        header = "cf_timestamp_ms,host_monotonic_s,baro.asl,baro.pressure,baro.temp\n"
        raw = header + f"{(1 << 24) - 10},100,1,1000,20\n10,100.02,2,1000,20\n"
        self.assertEqual(probe.read_barometer(raw.encode()), [(0.0, 1.0), (0.02, 2.0)])
        for invalid in (raw.replace("10,100.02", "9,99"), raw.replace("2,1000,20", "nan,1000,20"),
                        raw + "10,100.04,2,1000,20\n", raw.replace("10,100.02", "110,100.12")):
            with self.assertRaises(ValueError):
                probe.read_barometer(invalid.encode())

    def test_full_file_path_preserves_bytes_and_binds_digests(self):
        samples, spec = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(("cf_timestamp_ms", "host_monotonic_s", "baro.asl", "baro.pressure", "baro.temp"))
            for t, y in samples:
                writer.writerow((round(t * 1000), 1000 + t, y, 1000, 20))
            raw = stream.getvalue().encode()
            source = root / "barometer.csv"
            source.write_bytes(raw)
            spec["barometer"] = {"path": source.name, "sha256": hashlib.sha256(raw).hexdigest()}
            path = root / "spec.json"
            path.write_text(json.dumps(spec))
            result = probe.run(path)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(result["input_provenance"]["barometer_sha256"], spec["barometer"]["sha256"])
            source.write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "digest"):
                probe.run(path)


if __name__ == "__main__":
    unittest.main()
