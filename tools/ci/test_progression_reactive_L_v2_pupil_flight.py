#!/usr/bin/env python3
"""Fail-closed source contract for same-payload native A5 pupil flight proof."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_v2_pupil_flight as flight
class TestA5PupilFlightStaging(unittest.TestCase):
    def test_one_original_native_classroom_source_no_injected_motors(self):
        for letter in "ABC":
            with self.subTest(variant=letter):
                text=flight.compose(letter)
                self.assertEqual(text.count(flight.MARKER),1)
                self.assertEqual(text.count(
                    'controller "crazyflie_classroom_v2"'),1)
                self.assertEqual(text.count(
                    'name "Crazyflie WebeeBlocks"'),1)
                self.assertEqual(text.count(
                    'window "reactive_l_v2_pupil_probe"'),1)
                self.assertNotIn("WEBEEBLOCKS_REACTIVE_L_V2_A_SCENE",text)
                self.assertNotIn("WEBEEBLOCKS_REACTIVE_L_V2_B_SCENE",text)
                self.assertNotIn("WEBEEBLOCKS_REACTIVE_L_V2_C_SCENE",text)
                self.assertNotIn('controller "crazyflie_runtime_v2"',text)
        for bad in ("","D","AB",None,1):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                flight.compose(bad)

    def test_browser_vendor_assets_are_prepared_before_native_launch(self):
        workflow=(ROOT/".github/workflows/ci-progression-a5-draft.yml").read_text(
            encoding="utf-8")
        section=workflow.split("  a5-pupil-flight-draft:",1)[1]
        self.assertIn("./tools/prepare_runtime_v2.sh",section)
        self.assertIn("test -s plugins/robot_windows/blockly_v2/vendor/blockly_compressed.js",section)
        self.assertIn('vendor/VERSION)',section)
        self.assertLess(section.index("./tools/prepare_runtime_v2.sh"),
                        section.index("node tools/ci/test_progression_reactive_L_v2_generic_program.js"))
        self.assertLess(section.index("./tools/prepare_runtime_v2.sh"),
                        section.index("run_classroom_reactive_L_v2_pupil_flight.py --variant A"))
        self.assertNotIn("npm ci --prefix plugins/robot_windows/blockly_v2",section)
        browser=(ROOT/"plugins/robot_windows/reactive_l_v2_pupil_probe/"
                 "reactive_l_v2_pupil_probe.html").read_text(encoding="utf-8")
        self.assertIn('src="../blockly_v2/vendor/blockly_compressed.js"',browser)
        self.assertIn('src="../blockly_v2/vendor/blocks_compressed.js"',browser)

    def test_browser_never_invents_native_outcome_or_activity_solution(self):
        js=(ROOT/"plugins/robot_windows/reactive_l_v2_pupil_probe/"
            "reactive_l_v2_pupil_probe.js").read_text(encoding="utf-8")
        for token in (
            "WebeeBlocksProjectFiles.validateProjectText",
            "Blockly.serialization.workspaces.load",
            "WebeeBlocksActivityContract.execute(",
            "await backend.completeActivityMission(profile.evaluation)",
            "await pupilA5Outcome(backend,profile)",
            "await crypto.subtle.digest('SHA-256',bytes)",
            "base.starterVisible!==false",
            "WebeeBlocksSemanticAst.installConditionalLoopBounds(Blockly)",
        ):self.assertIn(token,js)
        for forbidden in (
            "wb_supervisor_field_set_sf_vec3f",
            "wb_motor_set_velocity","wb_supervisor_node_set_velocity",
            "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=", 
            "class PupilSolution",
        ):self.assertNotIn(forbidden,js)
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_v2_pupil_flight.py"
                ).read_text(encoding="utf-8")
        self.assertIn("result[\"native_achieved\"]==1",runner)
        self.assertIn("wbb.get(\"variant\")==variant",runner)
        self.assertIn("result[\"error_events\"]==0",runner)
        self.assertIn('"A5_PUPIL_ERROR" in names',runner)
        self.assertIn('if world.read_text(encoding="utf-8")!=body:',runner)
if __name__=="__main__":
    unittest.main()
