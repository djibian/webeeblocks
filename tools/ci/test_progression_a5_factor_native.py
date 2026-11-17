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
        for v in ("L","R","FL","FR"):
            text=witness.compose(v)
            self.assertEqual(text.count(witness.SENSOR_CONTROLLER),1)
            self.assertNotIn(witness.SOURCE_CONTROLLER,text)
            self.assertEqual(text.count("Floor { size 12 6 }"),1)
            self.assertEqual(text.count("boundingObject Box"),7)
            self.assertEqual(text.count(" Solid {"),7)
        for bad in ("",None,"A","LR"):
            with self.assertRaises(ValueError):witness.scene_path(bad)
    def test_malformed_sources_are_not_admitted(self):
        for v in ("L","R","FL","FR"):
            src=witness.scene_path(v).read_text()
            for bad in (src+src,src.replace(" Solid {"," Robot {",1),
                        src.replace("boundingObject Box","geometry Box",1)):
                with self.assertRaises(ValueError):witness.compose(v,bad)
    def test_opening_ray_delta_is_signed_toward_the_open_gap(self):
        script=(ROOT/"tools/ci/run_classroom_reactive_L_factor_probe.py").read_text()
        self.assertIn('gap_left=L[2]["front_m"]-R[2]["front_m"]',script)
        self.assertIn('gap_right=R[3]["front_m"]-L[3]["front_m"]',script)
        self.assertIn("gap_left<.35 or gap_right<.35",script)

    def test_native_2x2_rejects_fake_initial_memory_and_gate_leakage(self):
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_factor_probe.py").read_text()
        native=(ROOT/"controllers/progression_reactive_L_factor_probe"/
                "progression_reactive_L_factor_probe.c").read_text()
        for token in ('"L","R","FL","FR"', "min(h_initial_left_deltas)<.35",
                      "h_initial_other_delta>.035", "h_late_delta>.035",
                      "early_far>.035", "approach_far<.35",
                      "gap_left_far<.35", "gap_right_far<.35",
                      "motor_Hfactor_unproven=true"):
            self.assertIn(token,runner)
        for token in ("wb_distance_sensor_get_value(left)",
                      'cue=%c phase=%s', "if(near==far)",
                      'box("A5_FACTOR_H_CUE_TIP",fh2,sh2)'):
            self.assertIn(token,native)

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
