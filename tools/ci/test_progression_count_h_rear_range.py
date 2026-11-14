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
