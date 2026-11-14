#!/usr/bin/env python3
"""Adversarial source-world checks for Activity 3 raw native-flight witness.

This tests only composition and probe contracts, NOT a successful Webots flight.
The independent R2025a mission runner must prove real pose and C outcome.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'tools/ci/prepare_classroom_orientation_flight.py'
spec=importlib.util.spec_from_file_location('orientation_flight_world',MODULE)
# The composer imports the existing strict scene-ACK preparation module.
import sys
sys.path.insert(0,str(MODULE.parent))
w=importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

class OrientationFlightWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start=w.ack.SOURCE.read_text(encoding='utf-8')
    def test_isolated_native_roles_without_preloaded_oracle(self):
        created=w.compose(self.start)
        self.assertEqual(created.count(w.MARKER),1)
        self.assertEqual(created.count('window "orientation_flight_probe"'),1)
        self.assertEqual(created.count('controller "crazyflie_classroom_v2"'),1)
        self.assertNotIn('controller "crazyflie_runtime_v2"',created)
        self.assertNotIn('DEF WEBEEBLOCKS_ORIENTATION_SCENE',created)
        self.assertNotIn('DEF WEBEEBLOCKS_ALTITUDE_SCENE',created)
        self.assertNotIn('WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN',created)
        self.assertEqual(w.PROJECT_BYTES,
                         'Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n')
    def test_reject_ambiguous_native_source_before_write(self):
        for altered in (
            self.start.replace('window "blockly_v2"','window "wrong"',1),
            self.start.replace('controller "crazyflie_runtime_v2"',
                               'controller "unknown"',1),
            self.start.replace('#VRML_SIM R2025a utf8','#VRML_SIM R2023a utf8',1),
            self.start+'\\nDEF WEBEEBLOCKS_ORIENTATION_SCENE Group { children [] }\\n',
        ):
            with self.subTest(altered=altered[-80:]),self.assertRaises(ValueError):
                w.compose(altered)
    def test_probe_requires_real_relative_three_leg_flight_and_c_verdict(self):
        js=(ROOT/'plugins/robot_windows/orientation_flight_probe/orientation_flight_probe.js').read_text()
        native=(ROOT/'tools/ci/run_classroom_orientation_flight.py').read_text()
        self.assertEqual(js.count("await backend.turn(-90)"),2)
        self.assertEqual(js.count("await backend.turn(90)"),1)
        self.assertEqual(js.count("await backend.vertical('up',0.16)"),1)
        self.assertEqual(js.count("await backend.vertical('down',0.16)"),1)
        self.assertEqual(js.count("await backend.move('forward',0.45)"),4)
        for fragment in ('await backend.prepareActivity(ORIENT_PROFILE)',
                         'await backend.completeActivityMission(ORIENT_ORACLE)',
                         "await orientOutcome(backend)"):
            self.assertIn(fragment,js)
        self.assertIn('status=achieved checkpoints=3',native)
        self.assertIn("responses==[str(n) for n in range(1,14)]",native)
        self.assertIn("'WEBEEBLOCKS_RUNTIME_V2 FATAL' not in txt",native)
        self.assertNotIn("WebeeBlocksSemanticAst",js)
        self.assertNotIn("Blockly.Workspace",js)

if __name__=='__main__':
    unittest.main()
