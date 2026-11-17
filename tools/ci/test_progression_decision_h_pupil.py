#!/usr/bin/env python3
"""Contract for the isolated Activity 4 real Blockly/.wbb pupil falsifier.

This is a CI witness exercising the real public pupil profile, not a human
Windows acceptance or an independent V5 review.
"""
from __future__ import annotations
import ast
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
JS=ROOT/'plugins/robot_windows/decision_h_pupil_probe/decision_h_pupil_probe.js'
HTML=ROOT/'plugins/robot_windows/decision_h_pupil_probe/decision_h_pupil_probe.html'
PREP=ROOT/'tools/ci/prepare_classroom_decision_h_pupil.py'
RUN=ROOT/'tools/ci/run_classroom_decision_h_pupil.py'
BACKEND=ROOT/'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js'
ACTIVITIES=ROOT/'plugins/robot_windows/blockly/webeeblocks/activities.js'
PHYSICAL=ROOT/'controllers/crazyflie_runtime_v2/activity_scene.cpp'


class PupilA4Tests(unittest.TestCase):
    def test_real_blockly_project_and_same_bytes_both_variants(self):
        node=shutil.which('node')
        self.assertIsNotNone(node,'Node is mandatory for real JS syntax checks')
        for path in (JS,BACKEND):
            result=subprocess.run([node,'--check',str(path)],
                                  capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        html=HTML.read_text(encoding='utf-8')
        js=JS.read_text(encoding='utf-8')
        run=RUN.read_text(encoding='utf-8')
        self.assertIn('WB_A4_PUPIL_BOOTSTRAP',html)
        self.assertIn('decision_h_pupil_probe.js',html)
        profiles=(ROOT/'plugins/robot_windows/blockly/webeeblocks/activity_profiles.js').read_text(encoding='utf-8')
        for scene in ('decision-h-a-v1','decision-h-b-v1'):
            self.assertIn("profile.runtime.scene !== '"+scene+"'",profiles)
        self.assertIn("fail('runtime.scene must be sequence-v1",profiles)
        for resource in ('blockly_compressed.js','blocks_compressed.js',
                         'semantic_ast.js','interpreter.js','activity_contract.js',
                         'project_files.js','wwi_backend.js'):
            self.assertIn(resource,html)
        self.assertIn("const wbb=WebeeBlocksProjectFiles.encodeProject(",js)
        self.assertEqual(js.count('WebeeBlocksProjectFiles.encodeProject('),1)
        self.assertIn("for(const letter of ['a','b'])",js)
        self.assertIn('WebeeBlocksProjectFiles.validateProjectText(',js)
        self.assertIn('Blockly.serialization.workspaces.load(',js)
        self.assertIn('WebeeBlocksActivityContract.execute(',js)
        self.assertIn("await backend.resetSimulation()",js)
        self.assertIn('backend.completeActivityMission(',js)
        self.assertIn('backend.readActivityOutcome(',js)
        self.assertIn("decision.elseCount_=1",js)
        self.assertIn("condition.condition.left.direction==='front'",js)
        self.assertIn("condition.condition.right.value===0.8",js)
        self.assertIn("condition.then.length===4&&condition.else.length===4",js)
        self.assertIn("const near=[vertical('down',0.35),move(0.75),vertical('up',0.25),vertical('up',0.20)]",js)
        self.assertIn("a4Number(ws,takeoff,'HEIGHT',0.50)",js)
        self.assertIn("const initialClimb=vertical('up',0.25)",js)
        self.assertIn("a4Chain([takeoff,speed,initialClimb,firstMove",js)
        catalog=ACTIVITIES.read_text(encoding='utf-8')
        self.assertIn("'takeoff.height_m': { min: 0.50, max: 0.50 }",catalog)
        self.assertIn("'vertical.distance_m': { min: 0.1, max: 0.35 }",catalog)
        self.assertIn("const far=[vertical('up',0.10),move(0.75),vertical('down',0.25),vertical('down',0.20)]",js)
        self.assertIn("'webeeblocks_v2_takeoff', 'webeeblocks_v2_speed'",catalog)
        self.assertNotIn('WB_DH_ACHIEVED',js)
        self.assertNotIn("wb_supervisor_node_set",js)
        for name in ('decision-h-a-v1','decision-h-b-v1'):
            self.assertIn("'"+name+"'",BACKEND.read_text(encoding='utf-8'))
            self.assertNotIn("'"+name+"'",PHYSICAL.read_text(encoding='utf-8'))
        self.assertNotIn("ci-decision-h-conditional-v1",ACTIVITIES.read_text(encoding='utf-8'))
        self.assertIn("getProfile('progression-decision-h-v1')",js)
        self.assertIn('activitiesDocument:WebeeBlocksActivities.DOCUMENT',js)
        self.assertIn("parsed.get('activity',{}).get('id')=='progression-decision-h-v1'",run)
        self.assertNotIn("id:'ci-decision-h-conditional-v1'",js)

    def test_ci_wwi_trace_is_bounded_and_does_not_weaken_oracle(self):
        js=JS.read_text(encoding='utf-8')
        run=RUN.read_text(encoding='utf-8')
        self.assertIn('const a4WwiFrames=[]',js)
        self.assertIn('a4WwiFrames.length<96',js)
        self.assertIn("a4TraceFrame('attempted_send',text)",js)
        self.assertIn("a4TraceFrame('received',text)",js)
        self.assertIn("'A4_PUPIL_WWI_TRACE',{frames:a4WwiFrames}",js)
        self.assertNotIn("a4WwiFrames.push({text",js)
        self.assertIn("'wwi_frames':wwi_frames",run)
        self.assertIn("outcomes==[('A','1','achieved','4'),('B','2','achieved','4')]",run)
        self.assertIn("events.count('A4_PUPIL_ERROR')==0",run)

    def test_browser_script_never_generates_a_fresh_second_project(self):
        js=JS.read_text(encoding='utf-8')
        begin=js.index("const wbb=WebeeBlocksProjectFiles.encodeProject(")
        loop=js.index("for(const letter of ['a','b'])")
        self.assertLess(begin,loop)
        within=js[loop:]
        self.assertIn("wbb,profile,a4Options(profile)",within)
        self.assertNotIn('encodeProject(',within)
        self.assertNotIn('a4Workspace(',within)
        self.assertIn('A4_PUPIL_PROJECT_REOPENED',within)
        self.assertIn('identical_bytes:true',within)

    def test_native_webots_world_and_runner_fail_closed(self):
        prep=PREP.read_text(encoding='utf-8')
        run=RUN.read_text(encoding='utf-8')
        ast.parse(prep,filename=str(PREP))
        ast.parse(run,filename=str(RUN))
        self.assertIn('prepare_classroom_altitude_scene_ack as ack',prep)
        self.assertIn('controller "crazyflie_classroom_v2"',prep)
        self.assertIn('window "decision_h_pupil_probe"',prep)
        self.assertIn('refusing overwrite of existing A4 pupil CI world',prep)
        for t in ('A4_PUPIL_WBB_CHUNK','pupil-project.wbb',
                  "hashlib.sha256(project.encode('utf-8')).hexdigest()",
                  'A4_PUPIL_NATIVE_RESET','A4_PUPIL_NATIVE_ACHIEVED',
                  "outcomes==[('A','1','achieved','4'),('B','2','achieved','4')]",
                  'WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE front'):
            self.assertIn(t,run)
        self.assertIn('browser bootstrap missing after 45s',run)
        self.assertIn("browser_log=ARTIFACT/'browser-launch.log'",run)
        self.assertNotIn('set_sf_vec3f',run)
        self.assertNotIn('wb_motor_set_',run)

if __name__=='__main__':
    unittest.main()
