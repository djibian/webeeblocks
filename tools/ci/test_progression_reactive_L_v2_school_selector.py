#!/usr/bin/env python3
"""A5 V2 staged native school selection regression source contracts."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_reactive_L_v2_scene_ack as stage

class A5NativeSchoolSelection(unittest.TestCase):
    def test_derived_world_starts_empty_not_prefilled_with_a5(self):
        body=stage.compose()
        self.assertEqual(body.count(stage.MARKER),1)
        self.assertEqual(body.count('window "reactive_l_v2_scene_ack_probe"'),1)
        self.assertEqual(body.count('controller "crazyflie_classroom_v2"'),1)
        self.assertEqual(body.count('name "Crazyflie WebeeBlocks"'),1)
        self.assertNotIn("WEBEEBLOCKS_REACTIVE_L_V2_A_SCENE",body)
        self.assertNotIn("WEBEEBLOCKS_REACTIVE_L_V2_B_SCENE",body)
        self.assertNotIn("WEBEEBLOCKS_REACTIVE_L_V2_C_SCENE",body)
        self.assertNotIn("WEBEEBLOCKS_REACTIVE_L_V2_EVALUATOR",body)
        with self.assertRaises(ValueError):
            stage.compose("DEF WEBEEBLOCKS_REACTIVE_L_V2_A_SCENE Group {}")

    def test_selector_explicit_tokens_and_native_physical_qualities(self):
        s=(ROOT/"controllers/crazyflie_classroom_v2/classroom_scene.cpp").read_text(
            encoding="utf-8")
        for token in ("reactive-L-a-v2","reactive-L-b-v2","reactive-L-c-v2"):
            self.assertIn(token,s)
        for required in (
            "reactiveV2Selection(reactiveV2Token(scene))",
            "reactiveV2Colliders(reactiveV2Token(scene))",
            "wb_supervisor_node_get_orientation(solid)",
            "wb_supervisor_field_get_sf_node(boundary)",
            "wb_supervisor_node_get_field(observer,\"controller\")",
            "wb_supervisor_field_get_sf_bool(supervisor)",
            "wb_supervisor_field_get_sf_bool(sync)",
            'removeDef("WEBEEBLOCKS_REACTIVE_L_V2_EVALUATOR")',
            'removeDef("WEBEEBLOCKS_REACTIVE_L_V2_A_SCENE")',
            'removeDef("WEBEEBLOCKS_REACTIVE_L_V2_B_SCENE")',
            'removeDef("WEBEEBLOCKS_REACTIVE_L_V2_C_SCENE")',
            "if (reactiveV2Present()) return false;",
            "if (!ready) return 0;",
            "reactiveV2Token(scene)",
        ):
            with self.subTest(required=required):
                self.assertIn(required,s)
        # Staging must never touch the hardware-locked scene selector.
        physical=(ROOT/"controllers/crazyflie_runtime_v2/activity_scene.cpp"
                  ).read_text(encoding="utf-8")
        self.assertNotIn("reactive-L-a-v2",physical)
        self.assertNotIn("reactive-L-b-v2",physical)
        self.assertNotIn("reactive-L-c-v2",physical)

    def test_browser_uses_nonce_backend_and_untampered_crazyflie_sensor(self):
        js=(ROOT/"plugins/robot_windows/reactive_l_v2_scene_ack_probe/"
            "reactive_l_v2_scene_ack_probe.js").read_text(encoding="utf-8")
        runner=(ROOT/"tools/ci/run_classroom_reactive_L_v2_scene_ack.py"
                ).read_text(encoding="utf-8")
        for frag in (
            "await backend.prepareActivity(profile(token))",
            "await backend.readRange('front')",
            "await backend.prepareActivity(profile('legacy-v1'))",
            "await backend.prepareActivity(profile('reactive-L-a-v2'))",
            "new WebeeBlocksWwiBackend",
            "simulationScenes:true",
        ):self.assertIn(frag,js)
        for forbidden in ("backend.takeoff(","backend.move(","backend.turn(",
                          "backend.completeActivityMission(",".wbb"):
            self.assertNotIn(forbidden,js)
        self.assertIn('response==[str(i) for i in range(1,10)]',runner)
        self.assertIn('native=={"A":2,"B":1,"C":1}',runner)
        self.assertIn("student_wbb_tested=False",runner)

if __name__=="__main__":
    unittest.main()
