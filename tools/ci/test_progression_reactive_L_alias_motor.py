#!/usr/bin/env python3
"""Static/adversarial gate for private A5 alias PID feasibility; NOT pupil PASS."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_reactive_L_alias_motor as world

class A5AliasMotorSourceTests(unittest.TestCase):
    def test_exact_original_crazyflie_and_two_private_scenes(self):
        for variant in "AB":
            with self.subTest(variant=variant):
                text=world.compose(variant)
                self.assertEqual(text.count(world.PILOT_CONTROLLER),1)
                self.assertEqual(text.count(world.PILOT_WINDOW),1)
                self.assertNotIn(world.SOURCE_CONTROLLER,text)
                self.assertNotIn(world.SOURCE_WINDOW,text)
                self.assertNotIn('controller "crazyflie_runtime_v2"',text)
                self.assertEqual(text.count("boundingObject Box"),3)
                self.assertEqual(text.count(
                    f"DEF WEBEEBLOCKS_A5_ALIAS_{variant}_SCENE"),1)
        for bad in ("", "C", "AB", None,1):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):world.compose(bad)

    def test_malformed_or_double_native_obstacles_are_refused(self):
        for v in "AB":
            scene=world.scene_file(v).read_text(encoding="utf-8")
            for altered in (scene+scene,
                            scene.replace(" Solid {"," Robot {",1),
                            scene.replace("boundingObject Box",
                                          "geometry Box",1)):
                with self.assertRaises(ValueError):world.compose(v,altered)

    def test_pilot_is_native_pid_with_a_real_floor_contact_and_no_pupil_ast(self):
        base=ROOT/"controllers/progression_reactive_L_alias_motor_pilot"
        make=(base/"Makefile").read_text()
        cpp=(base/"alias_school_scene.cpp").read_text()
        trace=(base/"alias_motor_trace.c").read_text()
        js=(ROOT/"plugins/robot_windows/a5_alias_motor_probe/a5_alias_motor_probe.js"
            ).read_text()
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_alias_motor.py").read_text()
        for required in ("../crazyflie_runtime_v2/crazyflie_runtime_v2.c",
                         "../crazyflie_square/pid_controller.c",
                         "LFLAGS += -Wl,--wrap=wb_robot_step",
                         "-Wl,-rpath,$(WEBOTS_HOME)/lib/webots",
                         "-Wl,-rpath,$(WEBOTS_HOME)/lib/controller"):
            self.assertIn(required,make)
        for required in ("webeeblocks_select_activity_scene",
                         "webeeblocks_activity_scene_ready",
                         "wb_supervisor_node_get_orientation(node)",
                         "wb_supervisor_field_get_count(members)!=7",
                         "A5_ALIAS_%c_CUE_ARM", "A5_ALIAS_%c_TERMINAL"):
            self.assertIn(required,cpp)
        for required in ("__real_wb_robot_step(duration)",
                         "wb_supervisor_node_get_contact_points(craft,true,&n)",
                         "WBEEBLOCKS_A5_ALIAS_MOTOR_NATIVE_FLOOR",
                         "WEBEEBLOCKS_A5_ALIAS_MOTOR_OBSTACLE_CONTACT"):
            # Literal marker must not be confused with a browser ACK.
            self.assertIn(required,trace.replace("WEBEEBLOCKS_","WBEEBLOCKS_")
                          if required.startswith("WBEE") else trace)
        for token in ("const savedClue=await backend.readRange('left')",
                      "const goLeft=savedClue<.84;",
                      "await backend.turn(goLeft?90:-90)",
                      "await backend.land()",
                      "decision_source:'retained_early_sensor'"):
            self.assertIn(token,js)
        for token in ("native_loader_env()",
                      'env["LD_LIBRARY_PATH"]=str(qt_lib)+":"+str(controller_lib)',
                      'controller_lib/"libController.so"',
                      '"native-loader-dependencies.txt"',
                      '"native-loader-dynamic.txt"',
                      'subprocess.run(["ldd",str(executable)]',
                      'subprocess.run(["readelf","-d",str(executable)]',
                      'str(qt_lib) not in dynamic.stdout',
                      'str(controller_lib) not in dynamic.stdout',
                      'check.returncode!=0 or "not found"',
                      "native_floor_contact",
                      "native_land_ack",
                      "same_pilot_js",
                      "student_blockly_and_mission_oracle_NOT_PROVEN",
                      "no_memory_competitor_NOT_TESTED"):
            self.assertIn(token,runner)
        self.assertNotIn("variables_set",js)
        self.assertNotIn("pupil_project",js)

    def test_physics_monitor_checks_each_motor_step_and_obstacle_sides(self):
        trace=(ROOT/"controllers/progression_reactive_L_alias_motor_pilot"/
               "alias_motor_trace.c").read_text()
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_alias_motor.py").read_text()
        for required in (
            "__real_wb_robot_step(duration)",
            "wb_supervisor_node_enable_contact_points_tracking(craft,32,true)",
            "wb_supervisor_node_enable_contact_points_tracking(obstacles[i],32,false)",
            "wb_supervisor_node_get_contact_points(obstacles[i],false,&n)",
            "wb_supervisor_node_get_contact_points(craft,true,&n)",
            "segment_hits(start,position,center,half)",
            'fatal("native_obstacle_contact",t)',
            'fatal("unknown_nonfloor_contact",t)',
            'fatal("premature_floor_contact",t)',
            'fatal("craft_contact_stream_unavailable",t)',
            'fatal("native_sample_gap",t)',
            "WEBEEBLOCKS_A5_ALIAS_MOTOR_MONITOR_COMPLETE",
            "swept_boxes_checked=3",
        ):
            self.assertIn(required,trace)
        self.assertNotIn("if(p[2]>=.08||floor_emitted||t<1.0)return result",trace)
        self.assertIn("native_collision_coverage(text,variant)",runner)
        self.assertIn("native_coverage is not None",runner)
        self.assertIn("full_native_contact_monitoring",runner)
        self.assertIn("conservative_swept_aabb_proof_not_full_craft_kinematics",runner)

    def test_native_collision_coverage_rejects_missing_and_colliding_frames(self):
        import run_classroom_reactive_L_alias_motor as monitor
        self.assertIsNone(monitor.native_collision_coverage("", "A"))
        self.assertIsNone(monitor.native_collision_coverage("", "C"))
        good="".join(
            f"WEBEEBLOCKS_A5_ALIAS_MOTOR_MONITOR variant=A "
            f"ticks={n} t={n*.032:.6f} no_obstacle_contacts=true\n"
            for n in (16,32,48,64,80))
        good+=("WEBEEBLOCKS_A5_ALIAS_MOTOR_MONITOR_COMPLETE "
               "variant=A native_ticks=83 all_contacts_checked=true "
               "swept_boxes_checked=3\n")
        coverage=monitor.native_collision_coverage(good,"A")
        self.assertIsNotNone(coverage)
        self.assertEqual(coverage["continuous_native_steps"],83)
        # Native Webots keeps generating observations after first Floor
        # contact while LAND and the browser finish. Their presence is not
        # evidence of a gap or of an absent touchdown.
        continued=good+''.join(
            f"WEBEEBLOCKS_A5_ALIAS_MOTOR_MONITOR variant=A "
            f"ticks={n} t={n*.032:.6f} no_obstacle_contacts=true\n"
            for n in (96,112))
        self.assertEqual(
            monitor.native_collision_coverage(continued,"A"),
            coverage)
        negatives=(
            good.replace("ticks=48","ticks=47"),
            good.replace("t=1.536000","t=1.700000"),
            good.replace("variant=A native_ticks=83",
                         "variant=B native_ticks=83"),
            good.replace("native_ticks=83","native_ticks=100"),
            good.replace("swept_boxes_checked=3","swept_boxes_checked=0"),
            good+"WEBEEBLOCKS_A5_ALIAS_MOTOR_FATAL reason=invalid_sample\n",
            good+"WEBEEBLOCKS_A5_ALIAS_MOTOR_OBSTACLE_CONTACT collider=CUE_ARM\n",
            good+"WEBEEBLOCKS_A5_ALIAS_MOTOR_SWEPT_COLLISION collider=TERMINAL\n",
        )
        for i,bad in enumerate(negatives):
            with self.subTest(case=i):
                self.assertIsNone(monitor.native_collision_coverage(bad,"A"))

if __name__=="__main__":
    unittest.main()
