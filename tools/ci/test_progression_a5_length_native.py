#!/usr/bin/env python3
"""Fail-closed source and native-runner contracts for CI-only A5 L lengths."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_length_probe as native
from test_progression_a5_length_sources import CONFIG,source,reference

class LLengthSensorContract(unittest.TestCase):
    def test_exact_known_world_with_original_crazyflie(self):
        for variant in native.KNOWN:
            content=native.compose(variant)
            self.assertEqual(content.count(native.PROBE_CONTROLLER),1)
            self.assertNotIn(native.SOURCE_CONTROLLER,content)
            self.assertEqual(content.count("Floor { size 12 6 }"),1)
            self.assertEqual(content.count(" Solid {"),7)
            self.assertEqual(content.count("boundingObject Box"),7)
            self.assertEqual(content.count(native.MARKER),1)
            self.assertNotIn('controller "crazyflie_runtime_v2"',content)
            self.assertIn("DEF WEBEEBLOCKS_A5_LENGTH_",content)
        for v in ("",None,"sl","A","SX","LLR"):
            with self.assertRaises(ValueError):native.compose(v)
            with self.assertRaises(ValueError):native.scene_file(v)

    def test_native_world_generation_rejects_forged_scenes(self):
        for variant in native.KNOWN:
            original=native.scene_file(variant).read_text()
            opposite=native.scene_file("LR" if variant!="LR" else "SL").read_text()
            for corrupted in (original+original,
                 original.replace(" Solid {"," Robot {",1),
                 original.replace("boundingObject Box","geometry Box",1),
                 opposite):
                with self.subTest(variant=variant,change=len(corrupted)):
                    with self.assertRaises(ValueError):
                        native.compose(variant,corrupted)

    def test_native_C_attests_real_collision_and_visual_geometry(self):
        c=(ROOT/"controllers/progression_reactive_L_length_probe"/
           "progression_reactive_L_length_probe.c").read_text()
        for marker in ("wb_supervisor_node_get_from_def",
              "wb_supervisor_field_get_count(children)!=11",
              'strcmp(wb_supervisor_node_get_type_name(n),"Solid")',
              'strcmp(wb_supervisor_node_get_type_name(n),"Pose")',
              "untrusted_physical_L_boxes",
              "WBEEBLOCKS", # Keep the actual native controller subject visible.
              "wb_distance_sensor_get_value(front)",
              "wb_distance_sensor_get_value(left)",
              "wb_distance_sensor_get_value(right)",
              "wb_supervisor_node_reset_physics(self)",
              "WEBEEBLOCKS_A5_LENGTH_SAMPLE",
              "WEBEEBLOCKS_A5_LENGTH_DONE",
              "samples=5 supervisor_only=true motors=false"):
            if marker=="WBEEBLOCKS":marker="WEBEEBLOCKS"
            self.assertIn(marker,c)
        for dangerous in ("wb_motor_set_","setProfile(","Blockly","mission-state-v1"):
            self.assertNotIn(dangerous,c)
        self.assertEqual(c.count('!box("A5_FACTOR_'),7)
        self.assertIn('wb_robot_get_basic_time_step()',c)

    def test_native_observable_factors_and_false_success_rejected(self):
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_length_probe.py").read_text()
        for x in ("first[\"left_m\"]<.70","early_delta>.035",
                  "min(survey_contrast.values())<=.25",
                  "min(turn_contrast.values())<=.35",
                  "length_leak_into_turn>.035",
                  "min(gaps.values())<=.35",
                  "Webots Project File version R2025a",
                  "no_os_picker_proven"):
            # No OS picker is evaluated by the sensor-only script.
            if x=="no_os_picker_proven":
                self.assertNotIn(x,runner)
            else:
                self.assertIn(x,runner)
        self.assertIn('"motorized":False',runner)
        self.assertIn("pupil_wbb_pass",runner)
        self.assertIn("activity5_pedagogical_pass",runner)
        self.assertIn("WEBEEBLOCKS_A5_LENGTH_X_SIDE_NATIVE_PASS",runner)
        self.assertIn("xvfb-run",runner)
        self.assertNotIn("wb_motor_set_",runner)

if __name__=="__main__":
    unittest.main()
