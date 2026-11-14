#!/usr/bin/env python3
"""Reject false native A6 motor-flight evidence before the physical CI run."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_count_h_motor_flight as motor

class CountHMotorFlightTests(unittest.TestCase):
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
        self.assertIn("wb_supervisor_node_get_field(solid",adapter)
        self.assertIn("wb_supervisor_field_import_mf_node_from_string",adapter)
        self.assertIn("DEF WEBEEBLOCKS_A6_MOTOR_OBSERVER Robot",adapter)
        self.assertIn("realObserver()",adapter)
        self.assertIn('strcmp(scene,"count-h-1-v1")',adapter)
        self.assertIn("wb_supervisor_field_get_count(children)!=24",adapter)
        self.assertIn("simulationScenes:true",browser)
        self.assertIn("await backend.takeoff(0.40)",browser)
        self.assertIn("await backend.move('forward',0.48)",browser)
        self.assertIn("for(let i=0;i<6;i++)",browser)
        self.assertIn("await backend.land()",browser)
        self.assertIn("['SCENE','count-h-1-v1']",browser)
        self.assertNotIn("Blockly.Workspace",browser)
        self.assertNotIn("backend.completeActivityMission",browser)
        self.assertIn("responses==[str(i) for i in range(1,11)]",native)
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
