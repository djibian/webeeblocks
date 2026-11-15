#!/usr/bin/env python3
"""A5 V2 native probe contract: repeat real sensing, never certify pupil flight."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_sensor_v2 as probe


class A5V2WitnessTests(unittest.TestCase):
    def test_composes_only_one_original_crazyflie_and_its_native_v2_probe(self):
        for v in "ABC":
            with self.subTest(variant=v):
                body=probe.compose(v)
                self.assertEqual(body.count(probe.MARKER),1)
                self.assertEqual(body.count(probe.TEST_CONTROLLER),1)
                self.assertNotIn(probe.BASE_CONTROLLER,body)
                self.assertNotIn(probe.BASE_WINDOW,body)
                self.assertNotIn('controller "crazyflie_runtime_v2"',body)
                self.assertEqual(body.count(
                    f"DEF WEBEEBLOCKS_REACTIVE_L_V2_{v}_SCENE Group"),1)
                count=7 if v=="C" else 5
                self.assertEqual(body.count("boundingObject Box"),count)
        for invalid in ("","D","AB",None,1):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):probe.compose(invalid)

    def test_wrong_or_duplicate_scene_is_refused(self):
        for v in "ABC":
            with self.subTest(variant=v):
                path=ROOT/f"worlds/scenes/reactive-L-{v.lower()}-v2.wbo"
                scene=path.read_text(encoding="utf-8")
                with self.assertRaises(ValueError):
                    probe.compose(v,scene=scene+scene)
                with self.assertRaises(ValueError):
                    probe.compose(v,scene=scene.replace("boundingObject Box",
                                                         "geometry Box",1))

    def test_two_original_readings_cannot_distinguish_v2_variants(self):
        observations={v:(.98,1.21) for v in "ABC"}
        guesses={v:probe.classify_with_two_fixed_observations(obs)
                 for v,obs in observations.items()}
        self.assertEqual(set(guesses.values()),{"A"})
        self.assertNotEqual(guesses,{"A":"A","B":"B","C":"C"})

    def test_real_supervisor_4_samples_and_no_motor_or_pupil_algorithm(self):
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_sensor_v2.py"
                ).read_text(encoding="utf-8")
        source=(ROOT/"controllers/progression_reactive_L_sensor_probe_v2/"
                "progression_reactive_L_sensor_probe_v2.c").read_text(encoding="utf-8")
        for required in (
            "wb_supervisor_node_get_orientation(self)",
            "wb_distance_sensor_get_value(front)",
            "wb_distance_sensor_get_value(left)",
            "WEBEEBLOCKS_A5_V2_SENSOR_SAMPLE",
            "WEBEEBLOCKS_A5_V2_SENSOR_DONE",
            '"second",.8,1.0,1.5707963267948966,&third',
            '"after-pivot",.8,1.0,3.1415926535897932,&after_pivot',
            "fourth_m=%.9f test_only=true",
        ):self.assertIn(required,source)
        for forbidden in ("wb_motor_set_velocity","wb_motor_set_position",
                          "wb_supervisor_node_set_velocity",
                          "wb_supervisor_node_set_position"):
            self.assertNotIn(forbidden,source)
        self.assertIn("v1_two_measure_classifier_no_longer_succeeds",runner)
        self.assertIn("does_not_prove_loop_or_variable_necessary",runner)
        self.assertIn("post_pivot_left_readings_no_longer_distinguish_variants",runner)
        self.assertIn("does_not_prove_historical_reobservation_impossible",runner)
        self.assertIn('len(hits)!=4',runner)
        self.assertIn('max(post)-min(post)>.08',runner)
        self.assertIn("does_not_prove_drone_flight_or_student_solution",runner)


if __name__=="__main__":
    unittest.main()
