#!/usr/bin/env python3
"""A5 private short/long actual WBB motor experiment, strict source contracts.

No positive verdict from text: the draft CI must compile both C units and
actually fly the reactive, fixed-blind, snapshot and no-variable Blockly projects
through the original R2025a PID and unchanged independent C monitor.
"""
from pathlib import Path
import ast
import re
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_reactive_L_length_motor as composer

class LengthMotorSourceContract(unittest.TestCase):
    def test_worlds_exactly_seven_real_solids_and_original_crazyflie(self):
        for v in "ABCD":
            text=composer.compose(v)
            self.assertEqual(text.count('controller "progression_reactive_L_length_motor_pilot"'),1)
            self.assertEqual(text.count('window "a5_length_motor_probe"'),1)
            self.assertEqual(text.count(" Solid {"),7)
            self.assertEqual(text.count("boundingObject Box"),7)
            # The composed original classroom world contains other Poses.
            # The four additional visual markers belong to the isolated WBO.
            self.assertEqual(composer.scene_file(v).read_text().count(" Pose {"),4)
            self.assertEqual(text.count("Crazyflie {\n  name \"Crazyflie WebeeBlocks\""),1)
            self.assertNotIn('controller "crazyflie_classroom_v2"',text)
            self.assertIn(composer.MARKER,text)
            self.assertIn("Floor { size 12 6 }",text)
        for bad in ("E","",None,"SL","LL"):
            with self.assertRaises(ValueError):composer.compose(bad)
        for v in "ABCD":
            a=composer.scene_file(v).read_text()
            other=composer.scene_file("D" if v!="D" else "A").read_text()
            for forged in (a+a,other,
                    a.replace(" Solid {"," Robot {",1),
                    a.replace("boundingObject Box","geometry Box",1)):
                with self.subTest(variant=v,variation=len(forged)):
                    with self.assertRaises(ValueError):
                        composer.compose(v,forged)

    def test_independent_native_admission_and_32ms_contact_guard(self):
        folder=ROOT/"controllers/progression_reactive_L_length_motor_pilot"
        scene=(folder/"length_school_scene.cpp").read_text()
        physics=(folder/"length_motor_trace.c").read_text()
        make=(folder/"Makefile").read_text()
        for x in ("wb_supervisor_field_get_count(children)!=11",
                  "wb_supervisor_node_get_orientation",
                  'box("A5_FACTOR_H_CUE_ARM"',
                  'box("A5_FACTOR_G_SIDE_ARM"',
                  'box("A5_FACTOR_G_LEFT_BOUNDARY"',
                  'box("A5_FACTOR_G_RIGHT_BOUNDARY"',
                  "a5-length-short-g-left-proto",
                  "a5-length-long-g-right-proto",
                  "selected&&attest(selected)"):
            self.assertIn(x,scene)
        for x in ("__wrap_wb_robot_step",
                  "wb_supervisor_node_get_contact_points",
                  "wb_supervisor_node_enable_contact_points_tracking",
                  "segment_hits(start,position",
                  "const double inflate[3]={.105,.105,.060}",
                  "WEBEEBLOCKS_A5_LENGTH_MOTOR_WRONG_X_NATIVE",
                  "WEBEEBLOCKS_A5_LENGTH_MOTOR_NATIVE_FLOOR",
                  "WEBEEBLOCKS_A5_LENGTH_MOTOR_MONITOR_COMPLETE",
                  "target_x=is_long?4.35:3.95",
                  'fatal("premature_floor_contact",t)',
                  'duration!=32'):
            self.assertIn(x,physics)
        self.assertEqual(physics.count("obstacles[7]"),1)
        self.assertIn("../crazyflie_square/pid_controller.c",make)
        self.assertIn("length_motor_trace.c",make)
        self.assertIn("length_school_scene.cpp",make)
        self.assertIn("../crazyflie_runtime_v2/crazyflie_runtime_v2.c",make)
        self.assertNotIn("wb_motor_set_",physics)

    def test_real_two_wbb_runner_is_fail_closed(self):
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_length_motor.py").read_text()
        ast.parse(runner)
        for x in ("a5-private-loop-state-ci-only.wbb",
                  "a5-private-fixed-front-ci-only.wbb",
                  "a5-private-single-snapshot-ci-only.wbb",
                  'mode not in ("blockly","blockly_fixed","blockly_snapshot","blockly_no_variable")',
                  "len(fronts)==1 if snapshot",
                  "WEBEEBLOCKS_A5_LENGTH_SINGLE_SNAPSHOT_NATIVE_FOUR_PASS",
                  "len(fronts)==0 if fixed",
                  "WRONG_X_NATIVE",
                  "WEBEEBLOCKS_A5_LENGTH_MOTOR_NATIVE_FLOOR",
                  "WEBEEBLOCKS_A5_LENGTH_MOTOR_FATAL reason=premature_floor_contact",
                  "native_collision_coverage(trace,variant)",
                  "same_wbb_per_strategy=true",
                  "four_reactive_floor=true four_fixed_wrong_x=true"):
            self.assertIn(x,runner)
        self.assertIn("A5_FACTOR_MOTOR_WBB_REOPENED",runner)
        self.assertIn("A5_FACTOR_MOTOR_TEST_COMPLETE",runner)
        self.assertIn('"pupil_published":False',runner)
        self.assertIn('"mission_oracle":False',runner)
        self.assertNotIn("continue-on-error",runner)
        self.assertNotIn("|| true",runner)

    def test_browser_uses_original_ast_and_no_student_scene_identity(self):
        folder=ROOT/"plugins/robot_windows/a5_length_motor_probe"
        script=(folder/"a5_length_motor_probe.js").read_text()
        html=(folder/"a5_length_motor_probe.html").read_text()
        original=(ROOT/"plugins/robot_windows/a5_alias_motor_probe"/
                  "a5_private_blockly_probe.js").read_text()
        self.assertIn("await backend._request(['SCENE',scene])",script)
        self.assertIn("witness.runPrivateBlockly(backend,report",script)
        self.assertIn("a5_length_motor_probe.js",html)
        self.assertIn("WebeeBlocksInterpreter.run",original)
        self.assertIn("WebeeBlocksProjectFiles.validateProjectText",original)
        self.assertIn("single_front_snapshot:snapshot", original)
        self.assertIn("config.mode==='blockly_snapshot'", script)
        self.assertIn("snapshot&&frontReads!==1",original)
        generator=(ROOT/"tools/ci/build_a5_private_blockly_witness.js").read_text()
        for token in ("a5-private-single-snapshot-ci-only.wbb",
                      "snapshot_front_reads_structurally_one:true",
                      "count:18,body:[forward(.1)]",
                      "cmp('GT',range('front'),1.25)",
                      "iff(cmp('GT',range('front'),1.25),[forward(.8)],[forward(.4)])",
                      "snapshot_native_four_worlds: 'UNPROVEN'"):
            self.assertIn(token,generator)
        self.assertNotIn("config.variant",original)
        self.assertNotIn("a5-length-short",original)
        catalog=(ROOT/"plugins/robot_windows/blockly/webeeblocks/activities.js").read_text()
        self.assertNotIn("a5-length-short-g-left-proto",catalog)
        self.assertNotIn("a5-length-long-g-right-proto",catalog)

    def test_draft_job_and_exact_set_remain_nondeci(self):
        workflow=(ROOT/".github/workflows/ci-progression-a5-factor-draft.yml").read_text()
        job=workflow.split("\n  a5-length-real-blockly-motor-draft-only:\n",1)[1]
        self.assertIn("if: github.event.pull_request.draft == true",job)
        self.assertIn("persist-credentials: false",job)
        self.assertIn("run_classroom_reactive_L_length_motor.py",job)
        self.assertIn("test_progression_a5_length_motor",job)
        self.assertIn("build_a5_private_blockly_witness.js",job)
        self.assertIn("a5-private-single-snapshot-ci-only.wbb",job)
        self.assertIn("run_classroom_reactive_L_length_motor.py --snapshot",job)
        self.assertIn("a5-length-x-side-reactive-fixed-snapshot-motors-draft",job)
        self.assertIn("cyberbotics/webots@sha256:",job)
        self.assertNotIn("name: CI Gate",job)
        self.assertNotIn("continue-on-error",job)
        self.assertNotIn("|| true",job)

    def test_no_variable_physical_counterprogram_is_private_and_falsifiable(self):
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_length_motor.py").read_text()
        builder=(ROOT/"tools/ci/build_a5_private_blockly_witness.js").read_text()
        browser=(ROOT/"plugins/robot_windows/a5_alias_motor_probe/a5_private_blockly_probe.js").read_text()
        probe=(ROOT/"plugins/robot_windows/a5_length_motor_probe/a5_length_motor_probe.js").read_text()
        workflow=(ROOT/".github/workflows/ci-progression-a5-factor-draft.yml").read_text()
        for source,tokens in (
            (runner,("blockly_no_variable","--no-variable",
                     "WEBEEBLOCKS_A5_LENGTH_NO_VARIABLE_FOUR_PASS",
                     "left_native_reads","no_variable")),
            (builder,("build('no-variable')","a5-private-no-variable-ci-only.wbb",
                      "no_variable_native_four_worlds:'UNPROVEN'",
                      "noVariable.variableCount,0")),
            (browser,("strategy==='no-variable'","no_variable:noVariable",
                      "leftReads===(noVariable?1:2)",
                      "Object.keys(result.variables||{}).length!==0")),
            (probe,("config.mode==='blockly_no_variable'","'no-variable'")),
            (workflow,("a5-private-no-variable-ci-only.wbb",
                       "run_classroom_reactive_L_length_motor.py --no-variable",
                       "if: github.event.pull_request.draft == true"))
        ):
            for token in tokens:
                with self.subTest(token=token):
                    self.assertIn(token,source)
        self.assertNotIn("a5-private-no-variable-ci-only",
            (ROOT/"plugins/robot_windows/blockly/webeeblocks/activities.js").read_text())
        self.assertNotIn("name: CI Gate",workflow)
        self.assertNotIn("continue-on-error",workflow)


if __name__=="__main__":
    unittest.main()
