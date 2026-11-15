#!/usr/bin/env python3
"""Adversarial source contract: same A5 v2 scene, rotated actual Solid."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_v2_geometry_mutant as mutant
import run_classroom_reactive_L_v2_evaluator_attestation as baseline

class NativeRotationMutantContract(unittest.TestCase):
    def test_changes_only_one_existing_physical_wall_rotation(self):
        original=baseline.compose_with_evaluator("A")
        changed=mutant.rotated_scene("A")
        self.assertNotEqual(original,changed)
        self.assertEqual(changed.count(mutant.DEF),1)
        self.assertEqual(changed.count(mutant.ROTATION),1)
        self.assertEqual(changed.replace(mutant.ROTATION+"\n","",1),original)
        self.assertEqual(changed.count('controller "progression_reactive_L_v2"'),1)
        self.assertEqual(changed.count('controller "progression_reactive_L_sensor_probe_v2"'),1)
        for other in ("B","C",None):
            with self.subTest(other=other),self.assertRaises(ValueError):
                mutant.rotated_scene(other)

    def test_actual_webots_native_rejection_not_python_geometry_only(self):
        source=(ROOT/"tools/ci/run_classroom_reactive_L_v2_geometry_mutant.py"
                ).read_text(encoding="utf-8")
        self.assertIn('sensor.run_one("A")',source)
        self.assertIn('actual.count(FATAL)!=1',source)
        self.assertIn('READY in actual',source)
        self.assertIn('RESULT in actual',source)
        self.assertIn("pupil_flight=NOT_TESTED",source)
        self.assertNotIn("wb_motor_set_velocity",source)

if __name__=="__main__":
    unittest.main()
