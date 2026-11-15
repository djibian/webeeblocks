#!/usr/bin/env python3
"""Source-level contracts for a REAL native A5 attempt/RESET negative witness.

This is a test of mission protocol, not a substitute for an actual motorized
pupil project or evidence of simulated navigation.
"""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_v2_attempts as witness

class A5V2AttemptProtocol(unittest.TestCase):
    def test_original_crazyflie_one_native_evaluator_one_test_driver(self):
        for letter in "ABC":
            with self.subTest(variant=letter):
                world=witness.compose(letter)
                self.assertEqual(world.count('name "Crazyflie WebeeBlocks"'),1)
                self.assertEqual(world.count('controller "<none>"'),1)
                self.assertEqual(world.count(witness.EVAL),1)
                self.assertEqual(world.count(witness.PROBE),1)
                self.assertNotIn(witness.SENSOR,world)
                self.assertNotIn('controller "crazyflie_runtime_v2"',world)
                self.assertEqual(world.count(
                    f"DEF WEBEEBLOCKS_REACTIVE_L_V2_{letter}_SCENE Group"),1)
                self.assertEqual(world.count(witness.MARKER),1)
                self.assertEqual(world.count("Robot {"),2)
        for bad in ("D","AB","",None):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                witness.compose(bad)

    def test_actual_native_reset_contract_and_no_fabricated_flight(self):
        core=(ROOT/"controllers/progression_reactive_L_attempt_probe/"
              "progression_reactive_L_attempt_probe.c").read_text(encoding="utf-8")
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_v2_attempts.py"
                ).read_text(encoding="utf-8")
        for required in (
            "wb_supervisor_field_set_sf_string(channel,",
            "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1",
            "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2",
            "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=1",
            "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=2",
            "status=not-achieved",
            "fresh_reset=true",
        ):self.assertIn(required,core)
        for forbidden in (
            "wb_motor_set_velocity","wb_motor_set_position",
            "wb_supervisor_field_set_sf_vec3f",
            "wb_supervisor_node_set_velocity",
            "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=achieved",
        ):self.assertNotIn(forbidden,core)
        self.assertIn("for variant in",runner)
        self.assertIn('for variant in "ABC":',runner)
        self.assertIn('"WEBEEBLOCKS_A5_V2_FATAL" in data',runner)
        self.assertIn('status=achieved",data)',runner)

if __name__=="__main__":
    unittest.main()
