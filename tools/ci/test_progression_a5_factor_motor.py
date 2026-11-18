#!/usr/bin/env python3
"""A5 seven-collider original-PID G motor pilot: PRIVATE diagnostic only."""
from pathlib import Path
import unittest
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_reactive_L_factor_motor as motor

class A5FactorMotorTests(unittest.TestCase):
    def test_original_crazyflie_and_exact_native_g_geometry(self):
        for var in "ABCD":
            world=motor.compose(var)
            self.assertEqual(world.count(motor.PILOT_CONTROLLER),1)
            self.assertEqual(world.count(motor.PILOT_WINDOW),1)
            self.assertNotIn(motor.SOURCE_CONTROLLER,world)
            self.assertNotIn(motor.SOURCE_WINDOW,world)
            self.assertEqual(world.count("Floor { size 12 6 }"),1)
            self.assertEqual(world.count("boundingObject Box"),7)
            self.assertEqual(world.count(" Solid {"),7)
            self.assertEqual(world.count(
                f"DEF WEBEEBLOCKS_A5_FACTOR_G{'L' if var in ('A','C') else 'R'}_SCENE Group"),1)
        for bad in ("",None,"AB","E"):
            with self.assertRaises(ValueError):motor.compose(bad)

    def test_refuse_changed_world_assets(self):
        for v in "ABCD":
            text=motor.scene_file(v).read_text()
            for changed in (text+text,text.replace(" Solid {"," Robot {",1),
                            text.replace("boundingObject Box","geometry Box",1)):
                with self.assertRaises(ValueError):
                    motor.compose(v,scene=changed)

    def test_known_working_robot_window_isolated_alias(self):
        html=(ROOT/"plugins/robot_windows/a5_alias_motor_probe"/
              "a5_alias_motor_probe.html").read_text()
        copied=(ROOT/"plugins/robot_windows/a5_alias_motor_probe"/
                "a5_alias_motor_probe.js").read_bytes()
        canonical=(ROOT/"plugins/robot_windows/a5_factor_motor_probe"/
                   "a5_factor_motor_probe.js").read_bytes()
        self.assertEqual(copied,canonical)
        self.assertIn('script src="a5_alias_motor_probe.js"',html)
        self.assertIn('window "a5_alias_motor_probe"',motor.PILOT_WINDOW)
        self.assertIn("WB_A5_FACTOR_BOOTSTRAP",html)
        for required in ("blockly_compressed.js","blocks_compressed.js",
                         "semantic_ast.js","interpreter.js",
                         "project_files.js","activity_contract.js"):
            self.assertIn(required,html)

    def test_browser_job_prepares_the_actual_original_robot_window(self):
        workflow=(ROOT/".github/workflows/ci-progression-a5-factor-draft.yml").read_text()
        motor=workflow.split("  a5-factor-g-motor-draft-only:",1)[1].split(
            "  a5-factor-g-native-pid-feeder-draft-only:",1)[0]
        feeder=workflow.split("  a5-factor-g-native-pid-feeder-draft-only:",1)[1]
        for required in ("./tools/prepare_runtime_v2.sh",
                         "python3 /workspace/tools/prepare_webots_apt.py",
                         "google-chrome-stable_current_amd64.deb",
                         "Webots-R2025a.conf",
                         "[RobotWindow]",
                         "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh",
                         "test -x /usr/bin/google-chrome",
                         "python3 tools/ci/run_classroom_reactive_L_factor_motor.py"):
            self.assertIn(required,motor)
        self.assertNotIn("google-chrome-stable_current_amd64.deb",feeder)
        self.assertNotIn("prepare_runtime_v2.sh",feeder)
        self.assertIn("run_classroom_reactive_L_factor_motor.py --blockly",motor)
        self.assertIn("run_classroom_reactive_L_factor_motor.py --blockly-fixed",motor)
        self.assertLess(motor.index(" --blockly\n"),
                        motor.index(" --blockly-fixed"))

    def test_private_wbb_model_has_real_blockly_not_fake_native_authority(self):
        source=(ROOT/"tools/ci/build_a5_private_blockly_witness.js").read_text()
        workflow=(ROOT/".github/workflows/ci-progression-a5-factor-draft.yml").read_text()
        original=(ROOT/"plugins/robot_windows/blockly/webeeblocks/activities.js").read_text()
        for token in ("Blockly.serialization.workspaces.load",
                      "ProjectFiles.encodeProject",
                      "ProjectFiles.validateProjectText",
                      "Semantic.compileWorkspace",
                      "Interpreter.run",
                      "controls_whileUntil",
                      "variables_set",
                      "set('destination',range('left'))",
                      "frontReads>=21",
                      "conditional loops unavailable on this backend",
                      "native_2x2_from_this_wbb:false",
                      "pupil_activity_published:false",
                      "os_save_open:false"):
            self.assertIn(token,source)
        self.assertIn("node tools/ci/build_a5_private_blockly_witness.js",workflow)
        self.assertIn("ci-artifacts/progression-reactive-L-factor-blockly/",workflow)
        self.assertIn("node-version: '22'",workflow)
        self.assertIn("a5-private-fixed-front-ci-only.wbb",workflow)
        # A truly blind front-range candidate must not receive a guessed
        # success: same native R2025a monitor/7 Solids/Floor for both WBBs.
        for token in ("'controls_repeat_ext'",
                      "kind:'repeat',count:12",
                      "fixed.frontReads===0",
                      "fixed_front_adversary_virtual_four_pass:true"):
            # Fixed mock uses 'blind', not 'fixed' as the backend variable.
            if token=="fixed.frontReads===0":
                token="blind.frontReads===0"
            self.assertIn(token,source)
        # Real front ray stops the loop one 0.1m step before the old model.
        # The correction changes the private pupil AST, never native Floor.
        self.assertIn("Math.min(2,3.065-this.x)",source)
        self.assertEqual(
            source.count("forward(.85),forward(.8),forward(.1),"),2)
        self.assertNotIn("forward(.1),\n    {kind:'land'}",source)
        module=(ROOT/"plugins/robot_windows/a5_alias_motor_probe"/
                "a5_private_blockly_probe.js").read_text()
        native=(ROOT/"tools/ci/run_classroom_reactive_L_factor_motor.py").read_text()
        for key in ("WebeeBlocksProjectFiles.validateProjectText",
                    "Blockly.serialization.workspaces.load",
                    "WebeeBlocksInterpreter.run",
                    "WebeeBlocksActivityContract.preflightBackend",
                    "fresh_front_loop:!fixed",
                    "fixed_front_blind:fixed",
                    "missionOracle:false",
                    "frontReads<21",
                    "progression-reactive-hg-private-ci-only",
                    "progression-reactive-hg-fixed-blind-ci-only",
                    "facts.ranges.has('front')",
                    "fresh_front_loop:!fixed"):
            self.assertIn(key,module)
        for key in ("--blockly",
                    "WEBEEBLOCKS_A5_PRIVATE_REAL_WBB_NATIVE_PASS",
                    "WEBEEBLOCKS_A5_PRIVATE_REAL_WBB_NATIVE_UNPROVEN",
                    "native_collision_coverage(trace,variant)",
                    "len(left_reads)==2",
                    "21<=len(front_reads)<=33",
                    "mission_oracle_proven",
                    "WEBEEBLOCKS_A5_PRIVATE_FOUR_REAL_FIXED_WBB_NATIVE_PASS",
                    "len(front_reads)==0 if fixed",
                    "fixed_front_blind"):
            self.assertIn(key,native)

        self.assertNotIn("progression-reactive-hg-private-ci-only",original)
        self.assertNotIn("progression-reactive-hg-fixed-blind-ci-only",original)
        self.assertNotIn("tools/ci/build_a5_private_blockly_witness.js",
                         original)

    def test_actual_loopback_get_has_exactly_one_cors_origin_header(self):
        # Handler inherits an end_headers() which already appends ACAO.
        # Two identical '*' fields are INVALID in Chrome CORS and make the
        # otherwise genuine browser /variant fetch fail before any takeoff.
        import json
        import threading
        import urllib.request
        import urllib.error
        import run_classroom_reactive_L_factor_motor as trial

        handler=trial.Handler
        old_mode,old_variant=handler.mode,handler.variant
        handler.mode="positive"
        handler.variant="A"
        server=trial.events.http.server.ThreadingHTTPServer(
            ("127.0.0.1",0),handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        try:
            thread.start()
            base="http://127.0.0.1:"+str(server.server_address[1])
            request=urllib.request.Request(base+"/variant",
                         headers={"Origin":"http://localhost:1234"})
            with urllib.request.urlopen(request,timeout=5) as response:
                self.assertEqual(response.status,200)
                origins=response.headers.get_all("Access-Control-Allow-Origin")
                self.assertEqual(origins,["*"],"duplicate ACAO breaks Chrome")
                self.assertEqual(json.load(response),
                                 {"variant":"A","mode":"positive"})
            with self.assertRaises(urllib.error.HTTPError) as failed:
                urllib.request.urlopen(base+"/a5-private-wbb",timeout=5)
            self.assertEqual(failed.exception.code,404,
                             "private WBB must not be served in positive mode")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            handler.mode,handler.variant=old_mode,old_variant

    def test_native_pid_has_7_physical_obstacle_contact_streams(self):
        directory=ROOT/"controllers/progression_reactive_L_factor_motor_pilot"
        make=(directory/"Makefile").read_text()
        scene=(directory/"factor_school_scene.cpp").read_text()
        trace=(directory/"factor_motor_trace.c").read_text()
        js=(ROOT/"plugins/robot_windows/a5_factor_motor_probe"/
            "a5_factor_motor_probe.js").read_text()
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_factor_motor.py").read_text()
        for required in ("../crazyflie_runtime_v2/crazyflie_runtime_v2.c",
                         "../crazyflie_square/pid_controller.c",
                         "-Wl,--wrap=wb_robot_step","factor_motor_trace.c",
                         "factor_school_scene.cpp"):
            self.assertIn(required,make)
        for required in ("webeeblocks_select_activity_scene",
                         "wb_supervisor_node_get_orientation(node)",
                         "get_count(members)!=11",
                         "A5_FACTOR_G_LOWER","A5_FACTOR_G_UPPER",
                         "A5_FACTOR_G_SIDE_ARM",
                         "colliders=7"):
            self.assertIn(required,scene)
        for required in ("obstacles[7]","types[7]",
                         "for(int i=0;i<7;i++)",
                         "__real_wb_robot_step(duration)",
                         "wb_supervisor_node_get_contact_points(obstacles[i]",
                         "wb_supervisor_node_get_contact_points(craft,true,&n)",
                         "segment_hits(start,position,center[i],half[i])",
                         "swept_boxes_checked=7",
                         "WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR"):
            self.assertIn(required,trace)
        for required in ("await backend.readRange('left')",
                         "const targetRight=config.mode==='blind_h'?false:initialH>.80",
                         "const chooseLeft=config.mode==='blind'?true:left>1.0",
                         "await backend.move('forward',.60)",
                         "await backend.move('forward',1.24)",
                         "await backend.land()",
                         "A5_FACTOR_MOTOR_G_OBSERVATION"):
            self.assertIn(required,js)
        self.assertLess(js.index("A5_FACTOR_MOTOR_H_OBSERVATION"),
                        js.index("A5_FACTOR_MOTOR_APPROACH"))
        self.assertLess(js.index("A5_FACTOR_MOTOR_APPROACH"),
                        js.rindex("await backend.readRange('left')"))
        self.assertEqual(js.count("await backend.readRange("),2)
        self.assertIn("side:targetRight?'right':'left'",js)
        self.assertIn("await backend.turn(targetRight?-90:90)",js)
        self.assertIn("a5-factor-hfar-g-",js)
        self.assertIn("config.mode==='blind_h'?false:initialH>.80",js)
        self.assertIn("config.mode==='blind_h'?'blind_fixed_left'",js)
        self.assertIn("if mode==\"blind_h\" and variant!=\"C\":",runner)
        self.assertIn("WEBEEBLOCKS_A5_FACTOR_H_BLIND_NATIVE_REJECTED",runner)
        self.assertIn('"real_wrong_pad_floor":contact',runner)
        self.assertIn('"WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR" not in trace',runner)
        self.assertIn('land.get("nativeReply") is True',runner)
        self.assertIn('finished.get("missionOracle") is False',runner)
        self.assertIn('"mission_oracle":False',runner)
        g_negative=runner.split('    if mode=="blind":',1)[1].split(
            '    if mode=="blind_h":',1)[0]
        h_negative=runner.split('    if mode=="blind_h":',1)[1].split(
            '    missing=[k for k in REQUIRED',1)[0]
        self.assertIn('"A5_FACTOR_MOTOR_LAND_ACK" not in names',g_negative)
        self.assertNotIn('"A5_FACTOR_MOTOR_LAND_ACK" not in names',h_negative)
        self.assertIn('land.get("nativeReply") is True',h_negative)
        self.assertIn('finished.get("missionOracle") is False',h_negative)
        self.assertIn('--blind-h',
                      (ROOT/".github/workflows/ci-progression-a5-factor-draft.yml").read_text())
        self.assertIn('far?1.18:.58',scene)
        self.assertIn('far?1.38:.78',scene)
        self.assertIn('target_y=far_h?-.62:.62',trace)
        self.assertIn("if(near==far_h)return 0",trace)
        # A distant H must still reject a wrong pad on genuine Floor contact.
        self.assertIn("if(airborne&&floor&&!target)",trace)
        self.assertIn("WEBEEBLOCKS_A5_FACTOR_MOTOR_WRONG_PAD_NATIVE",trace)
        self.assertIn("position[2]>=0&&position[2]<=.025",trace)
        # C shares real G-left with A; D shares G-right with B.
        # The old 'variant == A' shortcut falsely mirrored C's swept
        # obstacle and refused an otherwise legitimate left-gate flight.
        self.assertIn("gate_left=a!=NULL;",trace)
        self.assertIn("variant=gate_left?(far_h?'C':'A'):(far_h?'D':'B');",trace)
        self.assertEqual(trace.count("gate_left?"),6)
        self.assertNotIn("variant=='A'?",trace)
        self.assertIn("WEBEEBLOCKS_A5_FACTOR_MOTOR_BROWSER_BOUNDARY_MISSING",runner)
        self.assertIn('"web_browser_invoked":launch.exists()',runner)
        self.assertIn('"native_motor_attempted":False',runner)
        self.assertIn("env[\"WEBEEBLOCKS_CI_ARTIFACT_DIR\"]=str(folder)",runner)
        for required in ("native_collision_coverage(trace,variant)",
                         "swept_boxes_checked=7",
                         "WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE left",
                         "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 VALUE",
                         "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 8 VALUE",
                         "WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR",
                         "pupil_wbb_or_full_mission_proven"):
            # Full mission remains false in the final aggregate report.
            if required=="pupil_wbb_or_full_mission_proven":
                self.assertIn('"pupil_wbb_or_full_mission_proven":False',runner)
            else:self.assertIn(required,runner)

if __name__=="__main__":
    unittest.main()
