#!/usr/bin/env python3
"""Falsification tests for scene-local 3D Activity-1 oracle (no Webots mock PASS)."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "controllers/progression_sequence_3d/progression_sequence_3d.py"
spec = spec_from_file_location("progression_sequence_3d", SOURCE)
oracle = module_from_spec(spec)
spec.loader.exec_module(oracle)


class Sequence3DOracleTests(unittest.TestCase):
    def test_protocol_rejects_wrong_attempt_or_oracle_or_trailing_data(self):
        self.assertEqual(oracle.parse_attempt("WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 9"), 9)
        for value in ("WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 0",
                      "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 -1",
                      "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 01",
                      "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 4 trailing",
                      "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=2 oracle=progression-sequence-3d-v1"):
            self.assertIsNone(oracle.parse_attempt(value))
        valid = "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=9 oracle=" + oracle.ORACLE
        self.assertTrue(oracle.parse_completion(valid, 9))
        self.assertFalse(oracle.parse_completion(valid, 8))
        self.assertFalse(oracle.parse_completion(valid + " trailing", 9))
        self.assertFalse(oracle.parse_completion(valid.replace(oracle.ORACLE, "progression-sequence-v1"), 9))

    def test_success_requires_real_flight_then_complete_stable_3d_landing(self):
        attempt = oracle.Attempt(11, 0.0)
        self.assertIsNone(attempt.sample(1.0, [0.0, 0.0, 0.5], [0, 0, 0], completed=False))
        self.assertIsNone(attempt.sample(5.0, [0.35, 0.28, 0.02], [0, 0, 0], completed=False))
        self.assertEqual(
            attempt.sample(5.1, [0.35, 0.28, 0.02], [0, 0, 0], completed=True),
            "achieved",
        )
        self.assertEqual(attempt.sample(99.0, [0, 0, 5], [0, 0, 10], True), "achieved")

    def test_forward_only_lateral_only_no_flight_moving_and_near_edge_fail(self):
        for label, samples in {
            "forward-only": [(0, [0, 0, 0.5], False), (1, [0.35, 0, 0.02], True)],
            "lateral-only": [(0, [0, 0, 0.5], False), (1, [0, 0.28, 0.02], True)],
            "never-took-off": [(0, [0.35, 0.28, 0.02], True)],
            "moving": [(0, [0, 0, 0.5], False), (1, [0.35, 0.28, 0.02], True)],
            # Centers just 0.08/0.10 m away were accepted by the old oracle
            # despite the craft's 0.09 m conservative half-span crossing the pad.
            "craft-overhang-x": [(0, [0, 0, 0.5], False), (1, [0.43, 0.28, 0.02], True)],
            "craft-overhang-y": [(0, [0, 0, 0.5], False), (1, [0.35, 0.38, 0.02], True)],
            "just-outside-x": [(0, [0, 0, 0.5], False), (1, [0.45, 0.28, 0.02], True)],
            "just-outside-y": [(0, [0, 0, 0.5], False), (1, [0.35, 0.41, 0.02], True)],
            "not-landed": [(0, [0, 0, 0.5], False), (1, [0.35, 0.28, 0.3], True)],
        }.items():
            with self.subTest(case=label):
                attempt = oracle.Attempt(1, 0)
                for now, pose, completed in samples:
                    self.assertIsNone(attempt.sample(now, pose, [0.3, 0, 0] if label == "moving" else [0, 0, 0], completed))
                self.assertEqual(attempt.sample(2.6, samples[-1][1], [0.3, 0, 0] if label == "moving" else [0, 0, 0], True),
                                 "not-achieved")


    def test_legitimate_slightly_off_center_3d_landing_still_succeeds(self):
        attempt = oracle.Attempt(20, 0.0)
        self.assertIsNone(attempt.sample(1.0, [0, 0, 0.50], [0, 0, 0], False))
        self.assertEqual(
            attempt.sample(3.0, [0.39, 0.34, 0.02], [0, 0, 0], True),
            "achieved",
        )

    def test_oracle_pad_margin_matches_scene_geometry_and_drone_span(self):
        scene = (ROOT / "worlds/scenes/sequence-v1.wbo").read_text(encoding="utf-8")
        self.assertIn("Pose { translation 0.35 0.28 0.002", scene)
        self.assertIn("geometry Box { size 0.28 0.34 0.004 }", scene)
        conservative_half_span = 0.09
        self.assertLessEqual(
            oracle.TARGET_X_TOLERANCE + conservative_half_span, 0.28 / 2 + 1e-12
        )
        self.assertLessEqual(
            oracle.TARGET_Y_TOLERANCE + conservative_half_span, 0.34 / 2 + 1e-12
        )
        self.assertAlmostEqual(oracle.TARGET_X_TOLERANCE, 0.05)
        self.assertAlmostEqual(oracle.TARGET_Y_TOLERANCE, 0.08)

    def test_incomplete_pose_and_replay_never_produce_success(self):
        attempt = oracle.Attempt(2, 0)
        self.assertIsNone(attempt.sample(0, [0, 0, 0.5], [0, 0, 0], False))
        self.assertEqual(attempt.sample(1, None, None, True), "not-achieved")
        self.assertEqual(attempt.sample(2, [0.35, 0.28, 0.02], [0, 0, 0], True), "not-achieved")
        next_attempt = oracle.Attempt(3, 0)
        self.assertIsNone(next_attempt.sample(2, [0.35, 0.28, 0.02], [0, 0, 0], False))
        self.assertIsNone(next_attempt.result)


if __name__ == "__main__":
    unittest.main()
