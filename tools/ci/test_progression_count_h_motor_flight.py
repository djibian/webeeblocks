#!/usr/bin/env python3
"""Reject false native A6 motor-flight evidence before the physical CI run."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_count_h_motor_flight as motor

class CountHMotorFlightTests(unittest.TestCase):
    def test_genuine_32ms_motor_ray_parser_and_adversarial_missing_H(self):
        from analyze_count_h_up_motor_evidence import attest_up_motor_trace
        import math
        def synthetic(n,miss=None,step=32,altitude=.415):
            lines=[]
            for i in range(321):
                x=-1.40+i*.009
                center=any(abs(x-(-.85+.85*k))<.032
                           for k in range(n) if k!=miss)
                up=.2 if center else 2.
                lines.append(
                    f"WEBEEBLOCKS_A6_UP_MOTOR t={(i+1)*.032:.6f} "
                    f"x={x:.9f} y=0.000000000 z={altitude:.9f} "
                    f"up={up:.9f} step={step}")
            return "\n".join(lines)
        for n in (1,2,3):
            with self.subTest(n=n):
                good=attest_up_motor_trace(synthetic(n),n)
                self.assertTrue(good["native_motor_ray_observed"])
                self.assertEqual(len(good["gates"]),n)
                self.assertEqual(good["total_32ms_samples"],321)
                for missing in range(n):
                    with self.assertRaisesRegex(ValueError,"far/near/far"):
                        attest_up_motor_trace(synthetic(n,miss=missing),n)
                with self.assertRaisesRegex(ValueError,"invalid native"):
                    attest_up_motor_trace(synthetic(n,step=64),n)
                with self.assertRaisesRegex(ValueError,"never sampled"):
                    attest_up_motor_trace(synthetic(n,altitude=.95),n)
                with self.assertRaisesRegex(ValueError,"missing/duplicating"):
                    altered=synthetic(n).split("\n")
                    del altered[30]
                    attest_up_motor_trace("\n".join(altered),n)
        # Real R2025a starts with a brief floor-settling physics contact:
        # z=-0.005 m before takeoff is NOT a low-altitude H passage.
        first=("WEBEEBLOCKS_A6_UP_MOTOR t=0.000000 x=-1.400000000 "
               "y=0.000000000 z=-0.005272640 up=0.000272640 step=32")
        good=attest_up_motor_trace(first+"\n"+synthetic(1),1)
        self.assertEqual(len(good["gates"]),1)
        invalid=first.replace("-0.005272640","-0.055272640")
        with self.assertRaisesRegex(ValueError,"invalid native"):
            attest_up_motor_trace(invalid+"\n"+synthetic(1),1)
        for n in (0,4,True):
            with self.assertRaisesRegex(ValueError,"invalid bounded"):
                attest_up_motor_trace(synthetic(1),n)
        with self.assertRaisesRegex(ValueError,"missing consecutive"):
            attest_up_motor_trace("",1)

    def test_motor_runner_requires_real_range_up_evidence_not_just_land(self):
        source=(ROOT/"tools/ci/run_classroom_count_h_motor_flight.py").read_text(
            encoding="utf-8")
        self.assertIn("attest_up_motor_trace(txt,variant)",source)
        self.assertIn('up_motor["native_motor_ray_observed"] and',source)
        self.assertIn("up-motor-evidence.json",source)
        self.assertIn("native_up_during_motor_flight",source)
        self.assertIn("WEBEEBLOCKS_A6_UP_MOTOR_OBSERVED",source)
        self.assertNotIn("backend.readRange('up')",source)

    def test_private_sensor_probe_does_not_read_scene_variant_or_supervisor(self):
        source=(ROOT/"plugins/robot_windows/count_h_flight_probe/"
                "count_h_sensor_only_probe.js").read_text(encoding="utf-8")
        page=(ROOT/"plugins/robot_windows/count_h_flight_probe/"
              "count_h_flight_probe.js").read_text(encoding="utf-8")
        runner=(ROOT/"tools/ci/run_classroom_count_h_motor_flight.py").read_text()
        for token in ("variant","count-h-","SCENE","Blockly","GPS",
                      "supervisor","window.","wb_supervisor"):
            # The standalone pilot has neither world-selection nor
            # synthetic mission/grading authority.
            if token in ("Blockly","GPS","supervisor"):
                self.assertNotIn(token,source.split("export async function",1)[1])
            else:
                self.assertNotIn(token,source.split("export async function",1)[1])
        for token in ("backend.readRange('front')",
                      "backend.readRange('up')",
                      "backend.move('forward',0.08)",
                      "A6_SENSOR_COUNT",
                      "await backend.land()"):
            self.assertIn(token,source)
        self.assertIn("if(mode==='sensor')",page)
        self.assertIn("await pilot.runSensorOnly(backend,report)",page)
        self.assertIn('"mode":self.mode',runner)
        self.assertIn('mode = "reference"',runner)

    def test_native_up_motor_trace_is_school_only_and_single_step(self):
        trace=(ROOT/"controllers/progression_count_h_school_pilot/"
               "a6_native_up_motor_trace.c").read_text(encoding="utf-8")
        make=(ROOT/"controllers/progression_count_h_school_pilot/"
              "Makefile").read_text(encoding="utf-8")
        physical=(ROOT/"controllers/crazyflie_runtime_v2/Makefile").read_text(
            encoding="utf-8")
        self.assertIn("C_SOURCES += a6_native_up_motor_trace.c",make)
        self.assertIn("LFLAGS += -Wl,--wrap=wb_robot_step",make)
        self.assertIn("extern int __real_wb_robot_step(int duration)",trace)
        self.assertEqual(trace.count("__real_wb_robot_step(duration)"),1)
        self.assertIn('wb_robot_get_device("range_up")',trace)
        self.assertIn('wb_robot_get_device("range_front")',trace)
        self.assertIn("wb_distance_sensor_get_value(native_front)/1000.0",trace)
        self.assertIn('step=%d front=%.9f',trace)
        self.assertIn("wb_distance_sensor_get_value(native_up)/1000.0",trace)
        self.assertIn("wb_gps_get_values(native_gps)",trace)
        self.assertIn("WEBEEBLOCKS_A6_UP_MOTOR t=",trace)
        for token in ("wb_motor_set_", "wb_supervisor_field_set_",
                      "wb_robot_wwi_send_text", "wb_robot_wwi_receive_text"):
            self.assertNotIn(token,trace)
        self.assertNotIn("a6_native_up_motor_trace.c",physical)
        self.assertNotIn("--wrap=wb_robot_step",physical)

    def test_webots_gui_project_cleanup_is_bounded_and_audited(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            generated=folder/"school.wbt"
            gui=folder/".school.wbproj"
            evidence=folder/"evidence"
            with mock.patch.object(motor,"WORLD",generated), mock.patch.object(
                    motor,"PROJECT",gui):
                motor.prepare()
                # Canonical generated files delete without a false alarm.
                motor.cleanup(artifacts=evidence)
                self.assertFalse(generated.exists())
                self.assertFalse(gui.exists())
                motor.prepare()
                # Ordinary GUI perspective records may append to .wbproj.
                gui.write_text(motor.PROJECT_BYTES+"viewpoint: 1 2 3\n",
                               encoding="utf-8")
                motor.cleanup(artifacts=evidence)
                self.assertFalse(gui.exists())
                self.assertIn(b"viewpoint: 1 2 3",
                              (evidence/"postrun-webots-project.wbproj").read_bytes())
                self.assertTrue(__import__("json").loads(
                    (evidence/"postrun-webots-project.json").read_text()
                    )["valid_gui_metadata"])
                motor.prepare()
                gui.write_text("UNKNOWN PROJECT\n",encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"unrecognized"):
                    motor.cleanup(artifacts=evidence)
                self.assertTrue(gui.exists())
                self.assertTrue(generated.exists())
                gui.write_text(motor.PROJECT_BYTES,encoding="utf-8")
                motor.cleanup(artifacts=evidence)
                motor.prepare()
                gui.unlink()
                gui.symlink_to(folder/"untrusted")
                with self.assertRaisesRegex(ValueError,"redirected"):
                    motor.cleanup(artifacts=evidence)
                self.assertTrue(generated.exists())
                gui.unlink()
                gui.write_text(motor.PROJECT_BYTES,encoding="utf-8")
                motor.cleanup(artifacts=evidence)

    def test_native_land_ack_must_be_logged_before_simulator_teardown(self):
        import run_classroom_count_h_motor_flight as native
        for variant in (1,2,3):
            final_id=11+(1 if variant!=1 else 0)
            prefix=f"WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved n={variant} crossed={variant}\n"
            completed="WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1\n"
            ack=f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE {final_id} OK\n"
            self.assertFalse(native.terminal_native_ack_logged(prefix,variant))
            self.assertFalse(native.terminal_native_ack_logged(prefix+completed,variant))
            self.assertTrue(native.terminal_native_ack_logged(
                prefix+completed+ack,variant))
            self.assertFalse(native.terminal_native_ack_logged(
                prefix+completed+f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE {final_id+1} OK\n",
                variant))
        self.assertFalse(native.terminal_native_ack_logged("",4))

    def test_sensor_command_mode_keeps_its_own_ack_and_artifact_boundary(self):
        import run_classroom_count_h_motor_flight as native
        prefix="WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved n=1 crossed=1\n"
        land="WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1\n"
        self.assertFalse(native.terminal_native_ack_logged(prefix+land,1,"sensor"))
        self.assertFalse(native.terminal_native_ack_logged(
            prefix+land+"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 10 OK\n",1,"sensor"))
        self.assertTrue(native.terminal_native_ack_logged(
            prefix+land+"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 80 OK\n",1,"sensor"))
        self.assertFalse(native.terminal_native_ack_logged(
            prefix+land+"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 80 OK\n",2,"sensor"))
        source=(ROOT/"tools/ci/run_classroom_count_h_motor_flight.py").read_text()
        for token in ('mode=="reference"','mode=="sensor"',
                      'f"sensor-n{variant}"','"A6_SENSOR_COUNT"',
                      "sensor_protocol",'"all_native_ack_ids"',
                      '"--mode"'):
            self.assertIn(token,source)
        script=(ROOT/"plugins/robot_windows/count_h_flight_probe/"
                "count_h_sensor_only_probe.js").read_text()
        self.assertNotIn("variant",script.split("export async function",1)[1])

    def test_world_is_authentic_with_single_count_and_independent_observer(self):
        w=motor.compose()
        self.assertEqual(w.count(motor.MARKER),1)
        self.assertEqual(w.count('controller "progression_count_h_school_pilot"'),1)
        # At Webots startup there must be exactly ONE Robot. The independent
        # observer is created only by the first accepted SCENE request.
        self.assertEqual(w.count('controller "progression_count_h_flight_observer"'),0)
        self.assertEqual(w.count('Robot {'),0)
        self.assertEqual(w.count('window "count_h_flight_probe"'),1)
        self.assertEqual(w.count('translation -1.40 0 0.055'),1)
        self.assertEqual(w.count('DEF WEBEEBLOCKS_COUNT_1_SCENE Group'),1)
        self.assertEqual(w.count("boundingObject Box"),5)
        self.assertEqual(w.count('name "Crazyflie WebeeBlocks"'),1)
        self.assertNotIn('controller "crazyflie_runtime_v2"',w)
        self.assertNotIn('controller "crazyflie_classroom_v2"',w)
        self.assertNotIn('WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN',w)
        self.assertNotIn("WEBEEBLOCKS_COUNT_2_SCENE",w)
        self.assertNotIn("WEBEEBLOCKS_COUNT_3_SCENE",w)

    def test_all_three_native_worlds_are_distinct_and_exactly_one_scene(self):
        hashes=set()
        import hashlib
        for variant in (1,2,3):
            with self.subTest(variant=variant):
                composed=motor.compose(variant=variant)
                hashes.add(hashlib.sha256(composed.encode("utf-8")).hexdigest())
                self.assertIn(f"DEF WEBEEBLOCKS_COUNT_{variant}_SCENE Group",composed)
                self.assertEqual(composed.count("boundingObject Box"),3*variant+2)
                for other in (1,2,3):
                    if other!=variant:
                        self.assertNotIn(f"DEF WEBEEBLOCKS_COUNT_{other}_SCENE",composed)
                scene=motor.SCENES[variant].read_text(encoding="utf-8")
                with self.assertRaises(ValueError):
                    motor.compose(variant=variant,scene=scene.replace(
                        "boundingObject Box","boundingObject Sphere",1))
                with self.assertRaises(ValueError):
                    motor.compose(variant=variant,scene=scene+'Robot { controller "foreign" }')
        self.assertEqual(len(hashes),3)
        for value in (0,4,-1,1.0,True):
            with self.assertRaises(ValueError):
                motor.compose(variant=value)

    def test_rotation_negative_preserves_physics_and_bounded_gui_metadata(self):
        source=(ROOT/"tools/ci/run_classroom_count_h_rotation_mutant.py").read_text()
        self.assertIn('WORLD.read_text(encoding="utf-8")!=source',source)
        self.assertIn("rotated physical world modified",source)
        self.assertIn("native.validate_project_preferences(gui)",source)
        self.assertIn("postrun-webots-project.wbproj",source)
        self.assertIn("altered-physical-world.json",source)
        self.assertIn("unrecognized rotated-test GUI preferences",source)

    def test_rotated_native_H_mutant_has_one_physical_change_and_independent_observer(self):
        import run_classroom_count_h_rotation_mutant as rotation
        witness=rotation.mutant()
        self.assertEqual(witness.count(rotation.ROTATION),1)
        self.assertEqual(witness.count(rotation.MARKER),1)
        self.assertEqual(witness.count("boundingObject Box"),8)
        self.assertEqual(witness.count('name "Crazyflie WebeeBlocks"'),1)
        self.assertEqual(witness.count(rotation.OBSERVER),1)
        self.assertIn(rotation.FATAL,
                      (ROOT/"tools/ci/run_classroom_count_h_rotation_mutant.py").read_text())

    def test_refuse_missing_native_collider_and_altered_base(self):
        scene=motor.SCENE.read_text(encoding="utf-8")
        base=motor.SOURCE.read_text(encoding="utf-8")
        alterations=[
            scene.replace("boundingObject Box","boundingObject Sphere",1),
            scene.replace("DEF WEBEEBLOCKS_COUNT_1_SCENE Group","DEF FOREIGN Group",1),
            scene+'Robot { controller "unsafe" }',
        ]
        for v in alterations:
            with self.subTest(scene=v[-50:]),self.assertRaises(ValueError):
                motor.compose(scene=v)
        with self.assertRaises(ValueError):
            motor.compose(start=base.replace(
                'name "Crazyflie WebeeBlocks"','name "foreign robot"'))

    def test_flight_runtime_and_observer_independence(self):
        source=(ROOT/"controllers/progression_count_h_flight_observer/"
                "progression_count_h_flight_observer.c").read_text()
        adapter=(ROOT/"controllers/progression_count_h_school_pilot/"
                 "classroom_count_h_scene.cpp").read_text()
        browser=(ROOT/"plugins/robot_windows/count_h_flight_probe/"
                 "count_h_flight_probe.js").read_text()
        native=(ROOT/"tools/ci/run_classroom_count_h_motor_flight.py").read_text()
        for fragment in (
            "wb_supervisor_node_get_contact_points",
            "wb_count_sample_mission(&m,&sample)",
            "WB_COUNT_ACHIEVED",
            "WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved",
            "screen_seen=1",
        ):
            if fragment=="screen_seen=1":
                self.assertIn("screen_seen=1",source)
            else:
                self.assertIn(fragment,source)
        self.assertIn("origin[2]<0.012||origin[2]>0.075",source)
        self.assertIn("hypot(start_velocity[0],start_velocity[1])>.12",source)
        self.assertNotIn("origin[2]<0.025",source)
        self.assertIn("wb_supervisor_node_get_field(solid",adapter)
        self.assertIn("wb_supervisor_node_get_orientation(solid)",adapter)
        self.assertIn("wb_supervisor_node_get_orientation(solid)",source)
        self.assertIn("wb_supervisor_field_import_mf_node_from_string",adapter)
        self.assertIn("DEF WEBEEBLOCKS_A6_MOTOR_OBSERVER Robot",adapter)
        self.assertIn("realObserver()",adapter)
        self.assertIn("if(!requested||!actual_scene(requested))",adapter)
        self.assertIn("admittedVariant=admitted?requested:0;",adapter)
        self.assertIn("const int expected=24+4*(n-1);",adapter)
        self.assertIn("wb_supervisor_field_get_count(children)!=expected",adapter)
        self.assertIn("for(int i=1;i<=variant;++i)",adapter)
        self.assertIn("simulationScenes:true",browser)
        self.assertIn("await backend.takeoff(0.40)",browser)
        self.assertIn("await backend.move('forward',0.48)",browser)
        self.assertIn("for(let i=0;i<6;i++)",browser)
        self.assertIn("await backend.move('forward',0.12)",browser)
        self.assertIn("A6_CORRIDOR_DONE',{moves:7,distance_m:3.00,variant}",browser)
        self.assertIn("await backend.land()",browser)
        self.assertIn("['SCENE','count-h-'+variant+'-v1']",browser)
        self.assertIn("await backend.move('left',0.55)",browser)
        self.assertIn("await backend.move('right',0.55)",browser)
        self.assertIn("Number.isInteger(variant)",browser)
        self.assertIn('self.path != "/a6-variant"',native)
        self.assertNotIn("Blockly.Workspace",browser)
        self.assertNotIn("backend.completeActivityMission",browser)
        self.assertIn("responses==[str(i) for i in range(1,expected_responses+1)]",native)
        self.assertIn('expected_moves=[("forward","0.480000000")]*6',native)
        self.assertIn("native_achieved=(",native)
        self.assertIn('abs(float(true_flight[5])-pad_y)<=.06',native)
        self.assertIn('"WEBEEBLOCKS_A6_MOTOR_FATAL" not in txt',native)
        self.assertIn('env["WEBEEBLOCKS_CI_ARTIFACT_DIR"]=str(ARTIFACT)',native)
        self.assertIn('timeout","-k","5s","390s"',native)
        self.assertIn("WEBEEBLOCKS_A6_MOTOR_WINDOW_REFUSED",native)
        self.assertIn("robot-window-http-diagnostic.json",native)
        self.assertIn("browser_only_proven_by_launch_and_events",native)
        self.assertIn("time.monotonic()-ready_since>=60",native)
        self.assertIn("diagnose_webots_window_http()",native)
        self.assertIn("WEBEEBLOCKS_A6_MOTOR_WINDOW_MANUAL_CI",native)
        self.assertIn('["bash","/workspace/tools/ci/webots_runtime_v2_browser.sh",page]',native)
        self.assertIn("manual_external_window",native)
        self.assertIn('"product_window_autolaunch_qualified":False',native)
        self.assertIn('get("status")==200',native)
        self.assertIn("manual_browser_no_html_event",native)
        self.assertIn("browser_only_proven_by_launch_and_events",native)

    def test_observer_attests_all_three_native_H_footprints_without_student_AST(self):
        source=(ROOT/"controllers/progression_count_h_flight_observer/"
                "progression_count_h_flight_observer.c").read_text(encoding="utf-8")
        self.assertIn("for(int n=1;n<=3;++n)",source)
        self.assertIn('"WEBEEBLOCKS_COUNT_%d_SCENE"',source)
        self.assertIn("if(variant)return fail(",source)
        self.assertIn("WbNodeRef obstacle[11]",source)
        self.assertIn("for(int n=1;n<=variant;++n)",source)
        for suffix in ("LEFT","RIGHT","BAR"):
            self.assertIn(f'"ACTIVITY6_%d_H_%d_{suffix}"',source)
        for suffix in ("FINISH_SCREEN","TERMINAL"):
            self.assertIn(f'"ACTIVITY6_%d_{suffix}"',source)
        self.assertIn("collider_count!=3*variant+2",source)
        self.assertIn("for(int i=0;i<collider_count;++i)",source)
        self.assertIn("wb_count_target_y((unsigned)variant)",source)
        self.assertIn("wb_count_reset(&m,1,(unsigned)variant,origin_z)",source)
        self.assertIn("step!=32",source)
        core=(ROOT/"controllers/progression_count_h_v1/count_core.h").read_text()
        self.assertIn("WB_COUNT_LAND_MAX_SAMPLE_GAP_SEC 0.048",core)
        self.assertIn("m->stable_since_valid = 0;",core)
        self.assertIn("reported_cross!=variant",source)
        self.assertNotIn("Blockly.",source)
        self.assertNotIn("wb_motor_set_",source)
        self.assertNotIn("wb_supervisor_field_set_sf_vec3f",source)

    def test_scene_admission_requires_exact_variant_identity_and_native_colliders(self):
        adapter=(ROOT/"controllers/progression_count_h_school_pilot/"
                 "classroom_count_h_scene.cpp").read_text(encoding="utf-8")
        self.assertIn('"count-h-%d-v1"',adapter)
        self.assertIn('"WEBEEBLOCKS_COUNT_%d_SCENE"',adapter)
        self.assertIn("if(n!=variant) {",adapter)
        self.assertIn("if(group)return false;",adapter)
        for kind in ("LEFT","RIGHT","BAR"):
            self.assertIn(f'"ACTIVITY6_%d_H_%d_{kind}"',adapter)
        for kind in ("FINISH_SCREEN","TERMINAL"):
            self.assertIn(f'"ACTIVITY6_%d_{kind}"',adapter)
        self.assertIn("const int expected=24+4*(n-1);",adapter)
        self.assertIn("if(!requested||!actual_scene(requested))",adapter)
        self.assertIn("admittedVariant=0;",adapter)
        self.assertIn("actual_scene(admittedVariant)&&realObserver()",adapter)
        self.assertNotIn('std::strcmp(scene,"count-h-1-v1")',adapter)

    def test_ci_browser_preparation_is_the_verified_a3_native_preparation(self):
        workflow=(ROOT/".github/workflows/ci-progression-a6-draft.yml").read_text()
        reference=(ROOT/"tools/ci/run_classroom_neutral_start.py").read_text()
        for requirement in (
            "python3 /workspace/tools/test_prepare_webots_apt.py",
            "python3 /workspace/tools/prepare_webots_apt.py",
            "apt-get update >/dev/null",
            "wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb",
            "DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null",
            "chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh",
            '"browser=/workspace/tools/ci/webots_runtime_v2_browser.sh"',
            '"newBrowserWindow=false"',
        ):
            self.assertIn(requirement,workflow)
            self.assertIn(requirement,reference)
        self.assertIn("run_classroom_count_h_motor_flight.py",workflow)
        self.assertIn("for n in 1 2 3",workflow)
        self.assertIn("run_classroom_count_h_rotation_mutant.py",workflow)
        self.assertIn("python3 /workspace/tools/ci/run_classroom_count_h_motor_flight.py --variant ${n}",workflow)

    def test_native_school_loader_reuses_qualified_webots_qt_runtime_ini(self):
        school=(ROOT/"controllers/progression_count_h_school_pilot/runtime.ini").read_bytes()
        reference=(ROOT/"controllers/crazyflie_classroom_v2/runtime.ini").read_bytes()
        physical=(ROOT/"controllers/crazyflie_runtime_v2/runtime.ini").read_bytes()
        self.assertEqual(school,reference)
        self.assertEqual(school,physical)
        self.assertIn(b"WEBOTS_LIBRARY_PATH = $(WEBOTS_HOME)/lib/webots",school)
        self.assertIn(b"QT_PLUGIN_PATH = $(WEBOTS_HOME)/lib/webots/qt/plugins",school)

    def test_native_build_reuses_existing_pid_without_physical_product_mutation(self):
        make=(ROOT/"controllers/progression_count_h_school_pilot/Makefile").read_text()
        self.assertIn("../crazyflie_runtime_v2/crazyflie_runtime_v2.c",make)
        self.assertIn("../crazyflie_square/pid_controller.c",make)
        self.assertIn("classroom_count_h_scene.cpp",make)
        self.assertNotIn("classroom_scene.cpp",make)
        self.assertIn("../crazyflie_runtime_v2/qt_file_dialog_provider.cpp",make)
        self.assertIn("webots_runtime_v2_browser.sh",
                      (ROOT/"tools/ci/run_classroom_count_h_motor_flight.py").read_text())
        self.assertNotIn("wb_supervisor_field_set_sf_vec3f",
                         (ROOT/"controllers/progression_count_h_flight_observer/"
                          "progression_count_h_flight_observer.c").read_text())

if __name__=="__main__":
    unittest.main()
