#!/usr/bin/env python3
"""Adversarial source-world checks for the isolated Activity 3 Webots smoke."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/ci/prepare_classroom_orientation_smoke.py"
spec = importlib.util.spec_from_file_location("classroom_orientation_smoke", MODULE)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class NativeOrientationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = smoke.START.read_text(encoding="utf8")
        cls.scene = smoke.SCENE.read_text(encoding="utf8")

    def test_exact_native_processes_and_unmodified_original_world(self):
        output = smoke.compose(self.start, self.scene)
        self.assertTrue(output.startswith("#VRML_SIM R2025a utf8\n"))
        self.assertEqual(output.count(smoke.MARKER), 1)
        self.assertEqual(output.count('controller "crazyflie_classroom_v2"'), 1)
        self.assertEqual(output.count('controller "progression_orientation_3d"'), 1)
        self.assertNotIn('controller "crazyflie_runtime_v2"', output)
        self.assertNotIn('window "blockly_v2"', output)
        self.assertNotIn(smoke.START_EVALUATOR, output)
        self.assertNotIn("WEBEEBLOCKS_LEGACY_EVALUATORS", output)
        self.assertEqual(output.count("DEF WEBEEBLOCKS_ORIENTATION_SCENE Group {"), 1)
        self.assertEqual(self.start.count('controller "crazyflie_runtime_v2"'), 2)
        self.assertEqual(self.scene.count(" Robot {"), 1)
        self.assertNotIn(" Solid {", self.scene)
        self.assertEqual(self.scene.count("    Pose { translation "), 30)

    def test_deny_foreign_or_incomplete_worlds_and_observers(self):
        variants = (
            (self.start.replace("#VRML_SIM R2025a utf8", "#VRML_SIM R2023a utf8", 1),
             self.scene),
            (self.start.replace('name "Crazyflie WebeeBlocks"',
                                'name "Unknown Webots Craft"', 1), self.scene),
            (self.start.replace('window "blockly_v2"',
                                'window "student"', 1), self.scene),
            (self.start.replace(smoke.END_EVALUATOR,
                                "# EVALUATOR_NOT_CLOSED", 1), self.scene),
            (self.start.replace(smoke.START_EVALUATOR,
                                "# EVALUATOR_START_MISSING", 1), self.scene),
            (self.start, self.scene.replace(
                'controller "progression_orientation_3d"',
                'controller "missing_observer"', 1)),
            (self.start, self.scene.replace(
                'name "Progression orientation 3D evaluator"',
                'name "unexpected supervisor"', 1)),
            (self.start, self.scene.replace(" Robot {", " Solid {", 1)),
            (self.start, self.scene.replace(
                "geometry Box { size 0.32 0.32 0.004 }",
                "geometry Box { size 0.50 0.50 0.004 }", 1)),
            (self.start, self.scene.replace(
                "    Pose { translation 0.450000",
                "      Pose { translation 0.450000", 1)),
        )
        for start, scene in variants:
            with self.subTest(input=(len(start), len(scene))):
                with self.assertRaises(ValueError):
                    smoke.compose(start, scene)

    def test_exclusive_temporary_output_and_safe_cleaning(self):
        source = MODULE.read_text(encoding="utf8")
        self.assertIn('refusing to overwrite an existing world', source)
        self.assertIn('refusing to delete unrecognized world', source)
        self.assertIn('OUTPUT = ROOT / "worlds/ci_classroom_orientation_smoke.wbt"', source)
        self.assertIn('raise SystemExit(main())', source)


if __name__ == "__main__":
    unittest.main()
