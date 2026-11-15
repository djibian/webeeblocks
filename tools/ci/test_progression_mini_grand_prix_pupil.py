#!/usr/bin/env python3
"""Fail-closed CI-only A7 real-Blockly motor-flight witness contracts."""
from __future__ import annotations
import ast
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_mini_gp_pupil as world  # noqa: E402
JS=ROOT/"plugins/robot_windows/mini_gp_pupil_probe/mini_gp_pupil_probe.js"
HTML=ROOT/"plugins/robot_windows/mini_gp_pupil_probe/mini_gp_pupil_probe.html"
PREP=ROOT/"tools/ci/prepare_classroom_mini_gp_pupil.py"
RUN=ROOT/"tools/ci/run_classroom_mini_gp_pupil.py"
BACKEND=ROOT/"plugins/robot_windows/blockly/webeeblocks/wwi_backend.js"
ACTIVITIES=ROOT/"plugins/robot_windows/blockly/webeeblocks/activities.js"
PHYSICAL=ROOT/"controllers/crazyflie_runtime_v2/activity_scene.cpp"
RUNTIME=ROOT/"controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c"


class PupilA7Tests(unittest.TestCase):
    def test_source_world_is_blue_and_real_classroom_motor_runtime(self):
        start=(ROOT/"worlds/crazyflie_classroom_start.wbt").read_text(encoding="utf-8")
        created=world.compose(start)
        self.assertEqual(created.count('  translation -1.4 0 0.015\n'),1)
        self.assertEqual(created.count('controller "crazyflie_classroom_v2"'),1)
        self.assertEqual(created.count('window "mini_gp_pupil_probe"'),1)
        self.assertEqual(created.count(world.MARKER),1)
        for forbidden in ('controller "crazyflie_runtime_v2"',
                          'DEF WEBEEBLOCKS_MINI_GP_L_SCENE',
                          'DEF WEBEEBLOCKS_MINI_GP_R_SCENE'):
            self.assertNotIn(forbidden,created)
        for invalid in (start+start,start.replace(
            'window "blockly_v2"','window "unknown"'),
            start.replace('controller "crazyflie_runtime_v2"',
                          'controller "untrusted"',1)):
            with self.subTest(invalid=invalid[:80]),self.assertRaises(ValueError):
                world.compose(invalid)

    def test_exact_one_real_blockly_project_reopened_in_both_variants(self):
        node=shutil.which("node")
        self.assertIsNotNone(node,"Node is required to validate native browser JS")
        for source in (JS,BACKEND):
            result=subprocess.run([node,"--check",str(source)],
                                  capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        js=JS.read_text(encoding="utf-8")
        html=HTML.read_text(encoding="utf-8")
        self.assertIn("WB_A7_PUPIL_BOOTSTRAP",html)
        self.assertIn("mini_gp_pupil_probe.js",html)
        for resource in ("blockly_compressed.js","blocks_compressed.js",
                         "semantic_ast.js","interpreter.js","activity_contract.js",
                         "project_files.js","wwi_backend.js"):
            self.assertIn(resource,html)
        self.assertEqual(js.count("WebeeBlocksProjectFiles.encodeProject("),1)
        begin=js.index("const wbb=WebeeBlocksProjectFiles.encodeProject(")
        loop=js.index("for(const letter of ['l','r'])")
        self.assertLess(begin,loop)
        after=js[loop:]
        self.assertNotIn("encodeProject(",after)
        self.assertNotIn("workspace()",after)
        for token in ("WebeeBlocksProjectFiles.validateProjectText(",
                      "Blockly.serialization.workspaces.load(",
                      "WebeeBlocksActivityContract.execute(",
                      "backend.completeActivityMission(",
                      "backend.readActivityOutcome(",
                      "await backend.resetSimulation()",
                      "identical_bytes:true",
                      "A7_PUPIL_NATIVE_ACHIEVED"):
            self.assertIn(token,js)
        for required in ("decision.elseCount_=1",
                         "sensor.setFieldValue('front'",
                         "condition.left.direction==='front'",
                         "condition.right.value===0.75",
                         "statement.then[3].angle_deg===90",
                         "statement.else[4].angle_deg===-90"):
            self.assertIn(required,js)
        self.assertIn("'takeoff.height_m':{min:0.50,max:0.50}",js)
        self.assertNotIn("wb_supervisor_",js)
        self.assertNotIn("WB_MINI_ACHIEVED",js)
        profiles=(ROOT/"plugins/robot_windows/blockly/webeeblocks/activity_profiles.js").read_text(encoding="utf-8")
        for scene in ("mini-grand-prix-l-v1","mini-grand-prix-r-v1"):
            self.assertIn("profile.runtime.scene !== '"+scene+"'",profiles)
            self.assertIn("'"+scene+"'",BACKEND.read_text(encoding="utf-8"))
            self.assertNotIn("'"+scene+"'",PHYSICAL.read_text(encoding="utf-8"))
        self.assertNotIn("ci-mini-grand-prix-conditional-v1",
                         ACTIVITIES.read_text(encoding="utf-8"))

    def test_motor_runner_requires_native_oracle_real_sensors_and_immutable_file(self):
        for path in (PREP,RUN):
            src=path.read_text(encoding="utf-8")
            ast.parse(src,filename=str(path))
        run=RUN.read_text(encoding="utf-8")
        for token in ("A7_PUPIL_WBB_CHUNK","pupil-project.wbb",
                      "hashlib.sha256(project.encode('utf-8')).hexdigest()",
                      "A7_PUPIL_NATIVE_RESET","A7_PUPIL_NATIVE_ACHIEVED",
                      "WB_MINI_NATIVE_RESULT variant=([LR]) attempt=([0-9]+)",
                      "WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE front",
                      "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1",
                      "'motorized_flight':valid",
                      "'same_pupil_wbb':project_ok and in_order",
                      "browser bootstrap missing after 45s"):
            self.assertIn(token,run)
        self.assertNotIn("set_sf_vec3f",run)
        self.assertNotIn("wb_motor_set_",run)
        self.assertNotIn("wb_supervisor_node_reset_physics",run)
        self.assertIn("wb_supervisor_field_set_sf_vec3f",RUNTIME.read_text(encoding="utf-8"))
        # Only production-grade native backend may RESET this craft, not the witness.
        self.assertIn("WEBOTS_WEB_BROWSER",run)

if __name__=="__main__":
    unittest.main()
