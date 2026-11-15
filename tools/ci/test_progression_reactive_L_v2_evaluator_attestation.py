#!/usr/bin/env python3
"""Static contract for draft native evaluator startup (not a pupil flight)."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_v2_evaluator_attestation as witness

class A5NativeEvaluatorStartup(unittest.TestCase):
    def test_source_world_uses_one_crazyflie_and_one_readonly_evaluator(self):
        for v in "ABC":
            with self.subTest(variant=v):
                world=witness.compose_with_evaluator(v)
                self.assertEqual(world.count(
                    'controller "progression_reactive_L_sensor_probe_v2"'),1)
                self.assertEqual(world.count(
                    'controller "progression_reactive_L_v2"'),1)
                self.assertEqual(world.count(
                    f"DEF WEBEEBLOCKS_REACTIVE_L_V2_{v}_SCENE Group"),1)
                self.assertEqual(world.count(
                    'name "Crazyflie WebeeBlocks"'),1)
                self.assertEqual(world.count("Robot {"),1)
                self.assertEqual(world.count("supervisor TRUE"),2)
                self.assertNotIn('controller "crazyflie_runtime_v2"',world)
                self.assertNotIn("WEBEEBLOCKS_A5_V2_RESULT attempt=",world)
        for invalid in ("D","",None,1):
            with self.assertRaises(ValueError):
                witness.compose_with_evaluator(invalid)

if __name__=="__main__":
    unittest.main()
