"""A7 PRIVATE terminal-information experiment; mocks cannot certify Webots."""
from pathlib import Path
import copy
import math
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/ci"))
import run_a7_terminal_info_probe as probe


class A7TerminalInformation(unittest.TestCase):
    def test_test_only_shift_preserves_source_and_all_nine_colliders(self):
        original = probe.ORIGINAL.read_text(encoding="utf8")
        self.assertEqual(original.count(" Solid {"), 9)
        for variant, y, pad in (("N",1.22,.75),("F",1.62,1.15)):
            scene = probe.transform_scene(variant)
            self.assertEqual(scene.count(" Solid {"), 9)
            self.assertEqual(scene.count("boundingObject Box"), 9)
            self.assertIn(f"translation 0.200 {pad:.3f} 0.002",scene)
            self.assertIn(f"translation 0.200 {y:.3f} 0.65",scene)
            self.assertNotEqual(scene,original)
            world = probe.compose(variant)
            self.assertEqual(world.count('controller "a7_terminal_info_probe"'),1)
            self.assertNotIn('controller "progression_mini_grand_prix_v1"',world)
            self.assertNotIn('controller "crazyflie_runtime_v2"',world)
            self.assertIn(probe.MARKER,world)
            self.assertEqual(world.count(" Solid {"),9)
        for bad in ("", "A", "L", "R", "NF", None):
            with self.assertRaises(ValueError):
                probe.transform_scene(bad)
        self.assertEqual(probe.ORIGINAL.read_text(encoding="utf8"),original)

    def test_fail_closed_early_five_ray_and_late_front_comparator(self):
        data = {v:{stage:dict.fromkeys(probe.CHANNELS,1.)
                   for stage,_,_,_ in probe.STAGES} for v in ("N","F")}
        for stage in ("late_far","late_near"):
            data["N"][stage]["front"] = .60
            data["F"][stage]["front"] = 1.00
        self.assertTrue(probe.validate(data))
        for stage in ("early_far","early_near"):
            for channel in probe.CHANNELS:
                wrong=copy.deepcopy(data)
                wrong["F"][stage][channel] += .05
                with self.subTest(stage=stage,channel=channel),self.assertRaisesRegex(
                        AssertionError,"information leaks early"):
                    probe.validate(wrong)
        for stage in ("late_far","late_near"):
            wrong=copy.deepcopy(data)
            wrong["F"][stage]["front"] = .65
            with self.assertRaisesRegex(AssertionError,"not discriminable late"):
                probe.validate(wrong)
        for change in (
            lambda d:d["N"].pop("early_near"),
            lambda d:d["F"]["early_far"].pop("back"),
            lambda d:d["F"]["late_near"].update({"front":float("nan")}),
            lambda d:d.update({"X":copy.deepcopy(d["N"])}),
            lambda d:d["N"]["early_near"].update({"left":-1.})
        ):
            wrong=copy.deepcopy(data)
            change(wrong)
            with self.assertRaises(AssertionError):
                probe.validate(wrong)

    def test_native_original_crazyflie_sensor_and_isolation(self):
        native = (ROOT/"controllers/a7_terminal_info_probe/"
                  "a7_terminal_info_probe.c").read_text(encoding="utf8")
        make = (ROOT/"controllers/a7_terminal_info_probe/Makefile").read_text()
        workflow = (ROOT/".github/workflows/"
                    "ci-a7-terminal-info-draft.yml").read_text()
        for name in ("range_front","range_back","range_left","range_right","range_up"):
            self.assertIn('"'+name+'"',native)
        for token in ("wb_supervisor_node_reset_physics",
                      "wb_supervisor_node_get_contact_points",
                      "wb_distance_sensor_get_value",
                      "WBEEBLOCKS_MINI_GP_L_SCENE",
                      "A7_TERMINAL_INFO_SAMPLE",
                      "supervisor_only=true motorized=false pupil_wbb=false"):
            if token=="WBEEBLOCKS_MINI_GP_L_SCENE":
                token="WEBEEBLOCKS_MINI_GP_L_SCENE"
            self.assertIn(token,native)
        self.assertNotIn("wb_motor_set_",native)
        self.assertNotIn("crazyflie_runtime_v2",make)
        self.assertNotIn("name: CI Gate",workflow)
        self.assertIn("github.event.pull_request.draft == true",workflow)
        self.assertIn("cyberbotics/webots@sha256:",workflow)
        self.assertIn("run_a7_terminal_info_probe.py",workflow)
        self.assertIn("if-no-files-found: error",workflow)


if __name__=="__main__":
    unittest.main()
