#!/usr/bin/env python3
"""Behavioral unit tests for Activity 3's independent scene-local oracle.

Pure Python proofs cannot establish actual Webots R2025a body orientation,
supervisor activation, native scene selection, RESET, or student acceptance.
"""
import importlib.util
import math
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "controllers/progression_orientation_3d/progression_orientation_3d.py"
spec = importlib.util.spec_from_file_location("progression_orientation_3d", PATH)
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def sample_sequence(attempt, *, yaw_a=-math.pi/2, z_b=0.79, ordered=True):
    if ordered:
        points = [
            ([0.45, 0, 0.63], yaw_a),
            ([0.45, -0.45, z_b], 0),
            ([0.90, -0.45, 0.63], -math.pi/2),
        ]
    else:
        points = [
            ([0.45, -0.45, z_b], 0),
            ([0.45, 0, 0.63], yaw_a),
            ([0.90, -0.45, 0.63], -math.pi/2),
        ]
    for now, (position, yaw) in enumerate(points, 1):
        attempt.sample(float(now), position, yaw, [0, 0, 0], completed=False)


class OrientationOracleUnitTests(unittest.TestCase):
    def test_protocol_exact_attempt_and_oracle(self):
        self.assertEqual(oracle.parse_attempt("WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 11"), 11)
        for value in ("WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 0",
                      "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 01",
                      "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 11 trailing",
                      "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 -1"):
            self.assertIsNone(oracle.parse_attempt(value))
        valid = ("WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=11 oracle="
                 + oracle.ORACLE)
        self.assertTrue(oracle.parse_completion(valid, 11))
        self.assertFalse(oracle.parse_completion(valid, 10))
        self.assertFalse(oracle.parse_completion(valid + " suffix", 11))
        self.assertFalse(oracle.parse_completion(valid.replace(oracle.ORACLE, "progression-sequence-v1"), 11))

    def test_actual_orientation_matrix_yaw_and_wrapping(self):
        identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]
        quarter = [0, 1, 0, -1, 0, 0, 0, 0, 1]
        self.assertAlmostEqual(oracle.yaw_from_orientation(identity), 0)
        self.assertAlmostEqual(oracle.yaw_from_orientation(quarter), -math.pi/2)
        self.assertIsNone(oracle.yaw_from_orientation(None))
        self.assertIsNone(oracle.yaw_from_orientation([0] * 9))
        self.assertIsNone(oracle.yaw_from_orientation([float("nan")] * 9))
        self.assertAlmostEqual(oracle.wrapped_error(math.pi, -math.pi), 0)

    def test_real_airborne_then_ordered_3d_and_heading_then_stable_landing(self):
        a = oracle.Attempt(9, 0)
        self.assertIsNone(a.sample(0, [0, 0, 0.0], 0, [0, 0, 0], False))
        sample_sequence(a)
        self.assertEqual(a.stage, 3)
        self.assertTrue(a.airborne)
        self.assertEqual(a.sample(4, [0.9, -0.9, 0.035], 0, [0, 0, 0], True), "achieved")
        self.assertEqual(a.sample(5, [50, 50, 10], 0, [0, 0, 0], False), "achieved")

    def test_wrong_headings_or_wrong_order_cannot_pass(self):
        for name, settings in {
            "no-turn-at-A": {"yaw_a": 0},
            "wrong-order": {"ordered": False},
            "wrong-height-at-B": {"z_b": 0.63},
        }.items():
            with self.subTest(name=name):
                a = oracle.Attempt(11, 0)
                sample_sequence(a, **settings)
                self.assertLess(a.stage, 3)
                self.assertEqual(a.sample(4, [0.9, -0.9, 0.03], 0, [0, 0, 0], True), "not-achieved")

    def test_no_flight_or_moving_or_not_landed_cannot_pass(self):
        for name, mode in {"no-flight": "no-flight",
                           "moving": "moving",
                           "too-high": "too-high",
                           "outside-pad": "outside-pad"}.items():
            with self.subTest(name=name):
                a = oracle.Attempt(5, 0)
                if mode != "no-flight":
                    sample_sequence(a)
                position = ([0.9, -0.9, 0.03] if mode != "too-high" else [0.9, -0.9, 0.4])
                if mode == "outside-pad":
                    position[0] = 1.10
                velocity = [0.4, 0, 0] if mode == "moving" else [0, 0, 0]
                result_at_completion = a.sample(4, position, 0, velocity, True)
                if mode == "no-flight":
                    self.assertEqual(result_at_completion, "not-achieved")
                else:
                    self.assertIsNone(result_at_completion)
                self.assertEqual(a.sample(6, position, 0, velocity, False), "not-achieved")

    def test_unavailable_orientation_after_completion_fails_closed(self):
        a = oracle.Attempt(2, 0)
        sample_sequence(a)
        self.assertEqual(a.sample(4, [0.9, -0.9, 0.03], None, [0, 0, 0], True), "not-achieved")
        self.assertEqual(a.sample(5, [0.9, -0.9, 0.03], 0, [0, 0, 0], False), "not-achieved")

    def test_world_and_oracle_consist_on_waypoints_and_yaw(self):
        scene = (ROOT / "worlds/scenes/orientation-v1.wbo").read_text(encoding="utf8")
        checkpoint = re.compile(r"# CHECKPOINT ([ABC]):[^\n]*\n\s*Pose \{ translation "
                                r"(-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)")
        direction = re.compile(r"# DIRECTION ([ABC]):[^\n]*\n\s*Pose \{ translation "
                               r"(-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+) rotation 0 0 1 (-?[0-9.]+)")
        found = dict((m[1], tuple(map(float, m.groups()[1:]))) for m in checkpoint.finditer(scene))
        headings = dict((m[1], float(m[5])) for m in direction.finditer(scene))
        self.assertEqual(len(found), 3)
        self.assertEqual(len(headings), 3)
        for index, label in enumerate("ABC"):
            self.assertEqual(found[label], oracle.CHECKPOINTS[index][:3])
            self.assertAlmostEqual(headings[label], oracle.CHECKPOINTS[index][3], places=5)
        self.assertEqual(scene.count("    Pose { translation "), oracle.SCENE_CHILDREN)


if __name__ == "__main__":
    unittest.main()
