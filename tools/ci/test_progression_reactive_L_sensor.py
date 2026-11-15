#!/usr/bin/env python3
"""A5 Draft source contracts: native witness is diagnostic, never a pupil PASS."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_sensor as probe


class A5NativeSensorContract(unittest.TestCase):
    def test_three_exact_world_variants_and_test_only_controller(self):
        for letter in "ABC":
            with self.subTest(letter=letter):
                body=probe.compose(letter)
                self.assertEqual(body.count(probe.MARKER),1)
                self.assertEqual(body.count(probe.TEST_CONTROLLER),1)
                self.assertNotIn(probe.BASE_CONTROLLER,body)
                self.assertNotIn(probe.BASE_WINDOW,body)
                self.assertEqual(body.count(
                    f"DEF WEBEEBLOCKS_REACTIVE_L_{letter}_SCENE Group"),1)
                self.assertNotIn('controller "crazyflie_runtime_v2"',body)
                self.assertIn('window ""',body)
        for invalid in ("", "D", "AB", None, 1):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):probe.compose(invalid)

    def test_missing_or_duplicate_collider_refuses_composition(self):
        for letter in "ABC":
            scene=(ROOT/f"worlds/scenes/reactive-L-{letter.lower()}-v1.wbo"
                   ).read_text(encoding="utf-8")
            with self.subTest(variant=letter):
                with self.assertRaises(ValueError):
                    probe.compose(letter,scene=scene.replace("boundingObject Box","geometry Box",1))
                with self.assertRaises(ValueError):
                    probe.compose(letter,scene=scene+scene)

    def test_two_measure_classifier_is_falsifiable_and_not_pupil_proof(self):
        self.assertEqual(probe.classify_with_two_fixed_observations((.96,1.2)),"A")
        self.assertEqual(probe.classify_with_two_fixed_observations((1.36,.28)),"B")
        self.assertEqual(probe.classify_with_two_fixed_observations((.96,.28)),"C")
        # The classifier is intentionally not a proof that flight is possible.
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_sensor.py").read_text(encoding="utf-8")
        c=(ROOT/"controllers/progression_reactive_L_sensor_probe/"
           "progression_reactive_L_sensor_probe.c").read_text(encoding="utf-8")
        for required in ("no motors", "does_not_prove_drone_flight_or_student_solution",
                         "A5_NATIVE_TWO_RAY_COUNTEREXAMPLE"):
            self.assertIn(required,runner)
        self.assertIn("wb_distance_sensor_get_value(front)",c)
        self.assertIn("wb_distance_sensor_get_value(left)",c)
        self.assertIn("wb_supervisor_node_get_position(self)",c)
        for forbidden in ("wb_motor_set_velocity", "wb_motor_set_position",
                          "wb_supervisor_node_set_velocity", "wb_supervisor_node_set_position"):
            self.assertNotIn(forbidden,c)


if __name__=="__main__":unittest.main()
