#!/usr/bin/env python3
"""Adversarial structural contracts for CI-only Blockly Activity 3 native flight.

This static harness never substitutes for the Webots R2025a observed outcome.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'tools/ci/prepare_classroom_orientation_pupil.py'
sys.path.insert(0,str(MODULE.parent))
spec=importlib.util.spec_from_file_location('orientation_pupil_world',MODULE)
pupil=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pupil)

class OrientationPupilWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start=pupil.flight.ack.SOURCE.read_text(encoding='utf-8')
        cls.js=(ROOT/'plugins/robot_windows/orientation_pupil_probe/orientation_pupil_probe.js').read_text(encoding='utf-8')
        cls.runner=(ROOT/'tools/ci/run_classroom_orientation_pupil.py').read_text(encoding='utf-8')
        cls.wrapper=(ROOT/'tools/ci/run_classroom_neutral_start.py').read_text(encoding='utf-8')

    def test_composition_requires_exact_unloaded_school_world(self):
        world=pupil.compose(self.start)
        self.assertEqual(world.count(pupil.MARKER),1)
        self.assertEqual(world.count('window "orientation_pupil_probe"'),1)
        self.assertEqual(world.count('controller "crazyflie_classroom_v2"'),1)
        for forbidden in ('controller "crazyflie_runtime_v2"',
                          'DEF WEBEEBLOCKS_ORIENTATION_SCENE',
                          'DEF WEBEEBLOCKS_ALTITUDE_SCENE',
                          'WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN'):
            self.assertNotIn(forbidden,world)
        self.assertEqual(pupil.PROJECT_BYTES,
            'Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n')

    def test_refuse_untrusted_world_source_without_mutating_it(self):
        bad=(
            self.start.replace('window "blockly_v2"','window "unexpected"',1),
            self.start.replace('controller "crazyflie_runtime_v2"','controller "other"',1),
            self.start.replace('#VRML_SIM R2025a utf8','#VRML_SIM R2023a utf8',1),
            self.start+'\nDEF WEBEEBLOCKS_ORIENTATION_SCENE Group { children [] }\n',
        )
        for mutated in bad:
            with self.subTest(length=len(mutated)),self.assertRaises(ValueError):
                pupil.compose(mutated)

    def test_real_blockly_repeat_and_serialization_are_part_of_the_witness(self):
        for token in (
            "new Blockly.Workspace()","block('controls_repeat_ext')",
            "repeat.getInput('TIMES')","repeat.getInput('DO')",
            "count.setFieldValue('2','NUM')",
            "const motif=[",
            "move(0.45),turn('right'),vertical('up',0.16),move(0.45)",
            "turn('left'),vertical('down',0.16)",
            "original.program[2].body.length!==6",
            "speed.setFieldValue('0.10','SPEED')",
            "a3MotionNumber(takeoff,'HEIGHT',0.63)",
            "vertical('up',0.16)","vertical('down',0.16)",
            "turn('right')","turn('left')",
            "WebeeBlocksProjectFiles.encodeProject",
            "WebeeBlocksProjectFiles.validateProjectText",
            "Blockly.serialization.workspaces.load",
            "WebeeBlocksActivityContract.applyFieldBounds",
            "WebeeBlocksActivityContract.preflightWorkspace",
            "WebeeBlocksSemanticAst.compileWorkspace",
            "WebeeBlocksActivityContract.preflightAst",
            "WebeeBlocksActivityContract.execute",
            "await backend.completeActivityMission(profile.evaluation)",
            "await a3Outcome(backend)",
        ):
            with self.subTest(token=token):
                self.assertIn(token,self.js)
        self.assertIn("id:'ci-orientation-blockly-v1'",self.js)
        self.assertIn("const doc={version:1,activities:[profile]}",self.js)
        self.assertNotIn('WebeeBlocksActivities.DOCUMENT.activities.push(',self.js)
        self.assertNotIn("webeeBlocks_physical",self.js)

    def test_native_c_verdict_and_sequence_are_necessary_not_browser_events(self):
        self.assertIn('status=achieved checkpoints=3',self.runner)
        self.assertIn('responses==[str(n) for n in range(1,17)]',self.runner)
        self.assertIn("moves==['0.450000000'] * 4",self.runner)
        self.assertIn("'90.000000000','-90.000000000','90.000000000'",self.runner)
        self.assertIn("roundtrip['repeat'].get('body',[])",self.runner)
        self.assertNotIn("move(0.225)",self.js)
        self.assertNotIn("speed.setFieldValue('0.12','SPEED')",self.js)
        self.assertIn("native is not None and browser",self.runner)
        self.assertIn("'WEBEEBLOCKS_RUNTIME_V2 FATAL' not in txt",self.runner)
        self.assertIn("python3 /workspace/tools/ci/run_classroom_orientation_flight.py",self.wrapper)
        self.assertIn("python3 /workspace/tools/ci/run_classroom_orientation_pupil.py",self.wrapper)
        self.assertLess(self.wrapper.index("run_classroom_orientation_flight.py"),
                        self.wrapper.index("run_classroom_orientation_pupil.py"))

if __name__=='__main__':
    unittest.main()
