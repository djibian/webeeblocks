#!/usr/bin/env python3
"""Fail closed on mutated A6 world composition for the native leak experiment."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_classroom_count_h_rear_range as diagnostic

class CountHRearRangeWorldTests(unittest.TestCase):
    def test_worlds_use_original_crazyflie_sensor_without_pupil_controller(self):
        for n in (1,2,3):
            world=diagnostic.compose(n)
            self.assertEqual(world.count('controller "progression_count_h_range_probe"'),1)
            self.assertNotIn('controller "crazyflie_runtime_v2"',world)
            self.assertNotIn('controller "crazyflie_classroom_v2"',world)
            self.assertEqual(world.count(f'DEF WEBEEBLOCKS_COUNT_{n}_SCENE Group'),1)
            for other in (1,2,3):
                if other!=n:
                    self.assertNotIn(f'DEF WEBEEBLOCKS_COUNT_{other}_SCENE Group',world)
            self.assertEqual(world.count("boundingObject Box"),3*n+2)
            self.assertEqual(world.count(f'DEF ACTIVITY6_{n}_FINISH_SCREEN Solid'),1)
            self.assertEqual(world.count(diagnostic.MARKER),1)

    def test_native_observer_probes_all_three_pads_not_legacy_single_ray(self):
        source=(diagnostic.ROOT /
                "controllers/progression_count_h_range_probe/"
                "progression_count_h_range_probe.c").read_text(encoding="utf-8")
        self.assertIn("for (int pad = 0; pad < 3; ++pad)", source)
        self.assertIn("WEBEEBLOCKS_COUNT_H_BACK_MASKED variant=%d pad=%d", source)
        self.assertNotIn("const int disclosed=", source)
        self.assertNotIn("WEBEEBLOCKS_COUNT_H_BACK_OBSERVED", source)
        runner=(diagnostic.ROOT /
                "tools/ci/run_classroom_count_h_rear_range.py").read_text(
                    encoding="utf-8")
        self.assertIn("len(findings)!=3", runner)
        self.assertIn("for pad in range(len(PADS)):", runner)
        self.assertIn("max(values)-min(values) > .025", runner)

    def test_real_contact_sweep_and_positive_control_cannot_be_silenced(self):
        source=(diagnostic.ROOT /
                "controllers/progression_count_h_range_probe/"
                "progression_count_h_range_probe.c").read_text(encoding="utf-8")
        self.assertIn("wb_supervisor_node_get_contact_points(self, true, &contact_count)", source)
        self.assertIn("wb_supervisor_node_get_contact_points(self, true, &self_contacts)", source)
        self.assertIn("wb_supervisor_node_enable_contact_points_tracking(self, step, true)", source)
        self.assertIn("wb_supervisor_node_get_contact_points(first_bar, false, &bar_contacts)", source)
        self.assertIn("WEBEEBLOCKS_COUNT_H_CONTACT_CONTROL variant=%d k=%d", source)
        self.assertNotIn("wb_supervisor_node_get_contact_points(self, &contact_count, true)", source)
        self.assertIn("for (int i = 0; i <= 144 + 28 * 2; ++i)", source)
        self.assertIn("return invalid(\"contact detector failed deliberate H-bar intersection\")", source)
        self.assertIn("WEBEEBLOCKS_COUNT_H_SWEEP_PASS variant=%d samples=%d", source)
        self.assertNotIn("WEBEEBLOCKS_COUNT_H_SWEEP_PASS", source.split(
            "wb_supervisor_node_get_contact_points", 1)[0])
        runner=(diagnostic.ROOT /
                "tools/ci/run_classroom_count_h_rear_range.py").read_text(
                    encoding="utf-8")
        self.assertIn("int(sweep[0][1])!=201", runner)
        self.assertIn("int(sweep[0][2])<1", runner)
        self.assertIn("A6_CONTACT_SWEEP_NATIVE_OK", runner)
        self.assertIn('TOKEN="WEBEEBLOCKS_COUNT_H_SWEEP_PASS"', runner)
        self.assertNotIn('TOKEN="WEBEEBLOCKS_COUNT_H_BACK_MASKED"', runner)

    def test_refuse_unknown_scene_or_corrupted_start(self):
        for n in (0,4,-1,'1'):
            with self.subTest(variant=n),self.assertRaises(ValueError):
                diagnostic.compose(n)
        source=diagnostic.classroom.SOURCE.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            diagnostic.compose(1,source=source.replace(
                'name "Crazyflie WebeeBlocks"','name "Evil"'))

if __name__=="__main__":
    unittest.main()
