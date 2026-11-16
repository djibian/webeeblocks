#!/usr/bin/env python3
"""A5 information-alias prototype is a bounded negative/positive physical test."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tools/ci"))
import run_classroom_reactive_L_memory_alias as alias

class A5MemoryAliasingPrototypeTests(unittest.TestCase):
    def test_native_scene_pair_uses_unchanged_real_crazyflie(self):
        for v in "AB":
            with self.subTest(v=v):
                world=alias.compose(v)
                self.assertEqual(world.count(alias.MARKER),1)
                self.assertEqual(world.count(alias.PROBE_CONTROLLER),1)
                self.assertNotIn(alias.SOURCE_CONTROLLER,world)
                self.assertNotIn(alias.SOURCE_WINDOW,world)
                self.assertEqual(world.count(
                    f"DEF WEBEEBLOCKS_A5_ALIAS_{v}_SCENE Group"),1)
                self.assertEqual(world.count("boundingObject Box"),3)
                self.assertNotIn('controller "crazyflie_runtime_v2"',world)
        for invalid in ("", "C", "AB", None, 1):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    alias.compose(invalid)

    def test_missing_collision_box_or_foreign_scene_fail_before_webots(self):
        for v in "AB":
            scene=alias.scene_path(v).read_text(encoding="utf-8")
            with self.subTest(v=v):
                for damaged in (scene+scene,
                                scene.replace("boundingObject Box",
                                              "geometry Box",1),
                                scene.replace(" Solid {"," Robot {",1)):
                    with self.assertRaises(ValueError):
                        alias.compose(v,scene=damaged)

    def test_scene_variants_have_only_early_cue_geometry_difference(self):
        a=alias.scene_path("A").read_text(encoding="utf-8")
        b=alias.scene_path("B").read_text(encoding="utf-8")
        self.assertEqual(a.count(" Solid {"),3)
        self.assertEqual(b.count(" Solid {"),3)
        self.assertIn("translation 0.000 0.580 0.550",a)
        self.assertIn("translation 0.000 1.180 0.550",b)
        self.assertIn("translation 2.100 0.000 0.550",a)
        self.assertIn("translation 2.100 0.000 0.550",b)
        for visual in ("translation 1.500 0.620 0.002",
                       "translation 1.500 -0.620 0.002"):
            self.assertIn(visual,a)
            self.assertIn(visual,b)
        # Ignore both the prototype label and only the early physical cue's
        # vertical coordinate. If anything downstream differs, this fails.
        normal=lambda s:(s.replace("A5_ALIAS_A_","A5_ALIAS_X_")
                         .replace("A5_ALIAS_B_","A5_ALIAS_X_")
                         .replace("0.580","CUE_Y").replace("0.780","TIP_Y")
                         .replace("1.180","CUE_Y").replace("1.380","TIP_Y"))
        self.assertEqual(normal(a),normal(b))

    def test_native_attestation_does_not_claim_unproven_motor_mission(self):
        source=(ROOT/"controllers/progression_reactive_L_memory_alias_probe"/
                "progression_reactive_L_memory_alias_probe.c").read_text()
        script=(ROOT/"tools/ci/run_classroom_reactive_L_memory_alias.py").read_text()
        for token in ("wb_distance_sensor_get_value(front)",
                      "wb_distance_sensor_get_value(left)",
                      "wb_distance_sensor_get_value(right)",
                      "wb_supervisor_node_get_orientation(self)",
                      "wb_supervisor_node_reset_physics(self)",
                      "wb_robot_get_basic_time_step()",
                      "for(int i=0;i<16;i++)",
                      "WEBEEBLOCKS_A5_ALIAS_SAMPLE"):
            self.assertIn(token,source)
        for forbidden in ("wb_motor_set_velocity", "wb_motor_set_position",
                          "wb_supervisor_node_set_velocity"):
            self.assertNotIn(forbidden,source)
        self.assertIn("far-near > .35",script)
        self.assertIn("max(deltas) > .035",script)
        # A failed geometric hypothesis must be archived as genuine negative
        # evidence, never hidden by a green static/motor-only Draft workflow.
        for marker in ('refutation.json', 'WEBEEBLOCKS_A5_ALIAS_NATIVE_REFUTED',
                       '"outcome": "REFUTED"', '"yaw_deg": scan_index * 22.5',
                       '"variant_A_m": a', '"variant_B_m": b',
                       '"revealing_rays": revealing'):
            self.assertIn(marker, script)
        self.assertIn("backtracking_or_local_translations_not_falsified",script)
        self.assertIn("variable_required_for_all_strategies_NOT_PROVEN",script)
        self.assertIn("classroom_student_PASS",script)
        self.assertIn("len(rows) != 17",script)
        self.assertIn("late_oblique_scans=16",script)
        self.assertIn("for idx in range(1, 17)",script)
        self.assertIn("i*PI/8,step",source)
        self.assertIn("scope=local_perception_only motor_flight=UNPROVEN",script)

if __name__=="__main__":
    unittest.main()
