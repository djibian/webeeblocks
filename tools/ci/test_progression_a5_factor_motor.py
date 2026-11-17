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
                         "const targetRight=initialH>.80",
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
        self.assertIn('far?1.18:.58',scene)
        self.assertIn('far?1.38:.78',scene)
        self.assertIn('target_y=far_h?-.62:.62',trace)
        self.assertIn("if(near==far_h)return 0",trace)
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
