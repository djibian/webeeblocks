#!/usr/bin/env python3
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import frozen_vertical_predictor as predictor


def build_stream(period, columns, fn, duration=58.0, origin=1000):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("cf_timestamp_ms", "host_monotonic_s", *columns))
    n = round(duration / period) + 1
    for i in range(n):
        t = i * period
        writer.writerow((origin + round(t * 1000), 100 + t, *fn(t)))
    return stream.getvalue().encode()


def fixture(errors=False):
    start, end = 34.0, 35.0
    accel = 0.8

    def z_truth(t):
        if t <= start:
            return 0.0
        if t < start + 0.5:
            u = t - start
            return 0.5 * accel * u * u
        if t < end:
            u = t - (start + 0.5)
            return 0.1 + 0.4 * u - 0.5 * accel * u * u
        return 0.2

    def az(t):
        if start <= t < start + 0.5:
            a = accel
        elif start + 0.5 <= t < end:
            a = -accel
        else:
            a = 0.0
        return 1.0 + a / predictor.G

    baro = build_stream(.02, ("baro.asl", "baro.pressure", "baro.temp"),
                        lambda t: (100 + z_truth(t), 1000, 20))
    imu = build_stream(.01, ("acc.x", "acc.y", "acc.z", "gyro.x", "gyro.y", "gyro.z"),
                       lambda t: (0, 0, az(t), 0, 0, 0))
    pose = build_stream(.02, ("range.zrange", "stabilizer.roll", "stabilizer.pitch", "stateEstimate.z", "stateEstimate.vz"),
                        lambda t: (500, 0, 0, 9999, -9999))
    spec = {"schema": "webeeblocks.x3.vertical-predictor-input.v1",
            "declared_bounds": {"specific_force_error_g": .002 if errors else .0005,
                                "max_body_z_tilt_deg": .2 if errors else .05,
                                "initial_velocity_error_m_s": .005 if errors else .001,
                                "barometer_displacement_error_m": .01 if errors else .005,
                                "sensor_time_error_s": .005 if errors else 0,
                                "delivery_latency_error_s": .05 if errors else 0}}
    reference = {"schema": "webeeblocks.x3.metric-reference-result.v1",
                 "status": "COMPUTED_CONDITIONAL",
                 "calibration_start_device_s": [0, 0], "calibration_end_device_s": [30, 30],
                 "events": [{"id": "vertical-up", "kind": "vertical",
                             "start_device_s": [start, start], "end_device_s": [end, end]}],
                 "physical_reference_validated": False, "affine_clock_validated": False}
    return baro, imu, pose, spec, reference


class PredictorTests(unittest.TestCase):
    def test_vertical_replay_excludes_tof_state_and_overlaps(self):
        baro, imu, _pose, spec, reference = fixture()
        result = predictor.analyze(*predictor.read_sources(baro, imu), spec, reference)
        event = result["events"][0]
        self.assertEqual(event["consistency"], "OVERLAP")
        self.assertLessEqual(event["barometer"]["delta_z_interval_m"][0], .2)
        self.assertGreaterEqual(event["barometer"]["delta_z_interval_m"][1], .2)
        self.assertLess(abs(event["inertial"]["nominal_delta_z_m"] - .2), .005)
        self.assertLess(event["conditional_uncertainty_width_m"], .02)
        self.assertTrue(event["conditional_half_width_within_5cm"])
        self.assertTrue(event["conditional_latency_within_1s"])
        self.assertFalse(result["declared_bounds_validated"])
        self.assertEqual(result["independent_displacement_verdict"], "UNPROVEN")
        self.assertIsNone(result["physical_verdict"])

    def test_declared_errors_widen_bounds_without_becoming_validation(self):
        baro, imu, _pose, spec, reference = fixture(errors=True)
        result = predictor.analyze(*predictor.read_sources(baro, imu), spec, reference)
        event = result["events"][0]
        self.assertGreater(event["conditional_uncertainty_width_m"], 0)
        self.assertEqual(event["conditional_latency_upper_s"], .81)
        self.assertFalse(result["declared_bounds_validated"])

    def test_disjoint_sensors_fail_closed_as_conditional_disagreement(self):
        baro, imu, _pose, spec, reference = fixture()
        text = imu.decode().splitlines()
        header = text[0].split(',')
        idx = header.index('acc.z')
        rows = [text[0]]
        for line in text[1:]:
            fields = line.split(',')
            fields[idx] = '1.0'
            rows.append(','.join(fields))
        flat_imu = ('\n'.join(rows) + '\n').encode()
        event = predictor.analyze(*predictor.read_sources(baro, flat_imu), spec, reference)["events"][0]
        self.assertEqual(event["consistency"], "DISJOINT")
        self.assertIsNone(event["conditional_delta_z_interval_m"])
        self.assertFalse(event["conditional_half_width_within_5cm"])

    def test_imu_prefix_before_barometer_origin_uses_signed_modular_alignment(self):
        baro, imu, _pose, _spec, _reference = fixture()
        text = imu.decode().splitlines()
        rows = [text[0]]
        for line in text[1:]:
            fields = line.split(',')
            fields[0] = str((int(fields[0]) - 10) % predictor.MODULUS)
            rows.append(','.join(fields))
        lead_imu = ('\n'.join(rows) + '\n').encode()
        _barometer, aligned_imu = predictor.read_sources(baro, lead_imu)
        self.assertAlmostEqual(aligned_imu[0][0], -0.01)
        self.assertAlmostEqual(aligned_imu[1][0], 0.0)
        self.assertTrue(all(left[0] < right[0] for left, right in zip(aligned_imu, aligned_imu[1:])))

    def test_calibration_and_event_constraints_reject_optimism(self):
        baro, imu, _pose, spec, reference = fixture()
        streams = predictor.read_sources(baro, imu)
        bad_reference = copy.deepcopy(reference)
        bad_reference["calibration_start_device_s"] = [0, 1]
        bad_reference["calibration_end_device_s"] = [30, 30]
        with self.assertRaisesRegex(ValueError, "30 s"):
            predictor.analyze(*streams, spec, bad_reference)
        bad = copy.deepcopy(spec)
        bad["declared_bounds"]["specific_force_error_g"] = -0.1
        with self.assertRaises(ValueError):
            predictor.analyze(*streams, bad, reference)
        bad_reference = copy.deepcopy(reference)
        bad_reference["events"][0]["start_device_s"] = [34.1, 33.9]
        with self.assertRaises(ValueError):
            predictor.analyze(*streams, spec, bad_reference)

    def test_reference_time_intervals_are_not_midpointed(self):
        baro, imu, _pose, spec, reference = fixture(errors=True)
        widened = copy.deepcopy(reference)
        widened["events"][0]["start_device_s"] = [34.0, 34.01]
        widened["events"][0]["end_device_s"] = [35.0, 35.01]
        result = predictor.analyze(*predictor.read_sources(baro, imu), spec, widened)
        event = result["events"][0]
        self.assertEqual(event["inertial"]["anchor_device_s"], [34.0, 35.0])
        self.assertGreater(event["inertial"]["timing_sensitivity_error_m"], 0)
        self.assertGreater(event["barometer"]["before_median_time_s"][1],
                           event["barometer"]["before_median_time_s"][0])
        self.assertFalse(result["sensor_producer_timing_validated"])

    def test_timing_envelope_includes_off_grid_bracketing_acceleration(self):
        prep = {"bounds": {"specific_force_error_g": 0.0,
                           "max_body_z_tilt_deg": 0.0,
                           "initial_velocity_error_m_s": 0.0,
                           "sensor_time_error_s": 0.005},
                "zero_specific_force_interval_g": [1.0, 1.0],
                "nominal_zero_specific_force_g": 1.0}
        imu = []
        for i in range(53):
            t = 0.99 + 0.02 * i
            az = 11.0 if i == 0 else 1.0
            imu.append((t, 100.0 + t, (0.0, 0.0, az)))
        start = (1.005, 1.005)
        end = (2.005, 2.005)
        segment = predictor.imu_segment(imu, start, end, prep)
        outer_start, outer_end = segment["admissible_device_s"]
        samples = predictor.projected_samples(imu, outer_start, outer_end, prep)
        _nominal, shifted, _points = predictor.integrate_projected(samples, outer_start, outer_end, prep)

        self.assertAlmostEqual(segment["max_abs_vertical_accel_bound_m_s2"], 10.0 * predictor.G)
        self.assertLessEqual(segment["delta_z_interval_m"][0], shifted[0])
        self.assertGreaterEqual(segment["delta_z_interval_m"][1], shifted[1])

    def test_metric_reference_validation_flags_require_json_booleans(self):
        baro, imu, _pose, spec, reference = fixture()
        streams = predictor.read_sources(baro, imu)
        malformed = copy.deepcopy(reference)
        malformed["physical_reference_validated"] = "false"
        with self.assertRaisesRegex(ValueError, "validation flags"):
            predictor.analyze(*streams, spec, malformed)
        malformed = copy.deepcopy(reference)
        malformed["affine_clock_validated"] = 1
        with self.assertRaisesRegex(ValueError, "validation flags"):
            predictor.analyze(*streams, spec, malformed)

    def test_full_file_entry_binds_exact_sources_and_rejects_pose_input(self):
        baro, imu, pose, spec, reference = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {}
            for name, raw in (("barometer", baro), ("imu", imu)):
                path = root / f"{name}.csv"
                path.write_bytes(raw)
                sources[name] = {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest()}
            reference["input_provenance"] = {"sources": [
                {"id": "capture", "path": "barometer.csv", "sha256": sources["barometer"]["sha256"], "kind": "barometer-capture"},
                {"id": "external", "path": "notes.txt", "sha256": "0" * 64, "kind": "external-metric-reference"}]}
            reference_raw = json.dumps(reference).encode()
            (root / "metric-reference.json").write_bytes(reference_raw)
            sources["metric_reference"] = {"path": "metric-reference.json", "sha256": hashlib.sha256(reference_raw).hexdigest()}
            spec["sources"] = sources
            path = root / "input.json"
            path.write_text(json.dumps(spec))
            result = predictor.run(path)
            self.assertEqual(result["input_provenance"]["sources"]["imu"], sources["imu"]["sha256"])

            pose_path = root / "pose.csv"
            pose_path.write_bytes(pose)
            forbidden = copy.deepcopy(spec)
            forbidden["sources"]["pose"] = {"path": pose_path.name, "sha256": hashlib.sha256(pose).hexdigest()}
            forbidden_path = root / "forbidden.json"
            forbidden_path.write_text(json.dumps(forbidden))
            with self.assertRaisesRegex(ValueError, "pose/ToF/estimator"):
                predictor.run(forbidden_path)

            (root / "imu.csv").write_bytes(imu + b"\n")
            with self.assertRaisesRegex(ValueError, "digest"):
                predictor.run(path)


if __name__ == "__main__":
    unittest.main()
