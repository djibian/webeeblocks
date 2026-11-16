#!/usr/bin/env python3
"""Adversarial source contract for original native A5 G sensor experiment."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_factor_probe as witness
class NativeFactorTests(unittest.TestCase):
    def test_world_uses_exact_original_crazyflie_and_solid_boxes(self):
        for v in ("L","R"):
            text=witness.compose(v)
            self.assertEqual(text.count(witness.SENSOR_CONTROLLER),1)
            self.assertNotIn(witness.SOURCE_CONTROLLER,text)
            self.assertEqual(text.count("Floor { size 12 6 }"),1)
            self.assertEqual(text.count("boundingObject Box"),7)
            self.assertEqual(text.count(" Solid {"),7)
        for bad in ("",None,"A","LR"):
            with self.assertRaises(ValueError):witness.scene_path(bad)
    def test_malformed_sources_are_not_admitted(self):
        for v in ("L","R"):
            src=witness.scene_path(v).read_text()
            for bad in (src+src,src.replace(" Solid {"," Robot {",1),
                        src.replace("boundingObject Box","geometry Box",1)):
                with self.assertRaises(ValueError):witness.compose(v,bad)
    def test_native_authority_and_failure_are_real(self):
        src=(ROOT/"controllers/progression_reactive_L_factor_probe"/
             "progression_reactive_L_factor_probe.c").read_text()
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_factor_probe.py").read_text()
        for marker in ("wb_distance_sensor_get_value(front)",
                       "wb_distance_sensor_get_value(left)",
                       "wb_supervisor_node_reset_physics(self)",
                       "wb_supervisor_field_get_sf_node(field)",
                       "WEBEEBLOCKS_A5_FACTOR_SAMPLE",
                       "WEBEEBLOCKS_A5_FACTOR_DONE"):
            self.assertIn(marker,src)
        for forbidden in ("wb_motor_set_position","wb_motor_set_velocity",
                          "variables_set","setProfile("):
            self.assertNotIn(forbidden,src)
        for marker in ("early>.035","approach<.35","gap_left<.35",
                       "gap_right<.35","motorized_passage_proven=False",
                       "pupil_wbb_or_mission_proven=False"):
            self.assertIn(marker,runner)
if __name__=="__main__":
    unittest.main()
