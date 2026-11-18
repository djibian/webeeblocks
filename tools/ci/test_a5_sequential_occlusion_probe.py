"""A5 private native two-L occlusion: adversarial source and comparator tests."""
from pathlib import Path
import copy,sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_a5_sequential_occlusion_probe as probe

class A5SequentialTest(unittest.TestCase):
    def test_only_second_L_differs_and_original_drone_retained(self):
        a=probe.scene_file("A").read_text()
        b=probe.scene_file("B").read_text()
        self.assertEqual(a.count(" Solid {"),4)
        self.assertEqual(b.count(" Solid {"),4)
        self.assertEqual(a.count("boundingObject Box"),4)
        self.assertEqual(b.count("boundingObject Box"),4)
        changed=a.replace("2.500 0.450","3.000 0.450").replace(
            "2.150 1.050","2.650 1.050").replace(
            "experiment A:","experiment B:").replace(
            "WEBEEBLOCKS_A5_SEQ_OCC_A_SCENE",
            "WEBEEBLOCKS_A5_SEQ_OCC_B_SCENE")
        self.assertEqual(changed,b)
        for v in ("A","B"):
            w=probe.compose(v)
            self.assertEqual(w.count('controller "progression_a5_seq_occ_probe"'),1)
            self.assertEqual(w.count("Floor { size 8 4 }"),1)
            self.assertNotIn('controller "crazyflie_runtime_v2"',w)
        for bad in ("C","",None,"A+B"):
            with self.assertRaises(ValueError):probe.compose(bad)
        with self.assertRaises(ValueError):
            probe.compose("A",scene=a.replace(" Solid {"," Robot {",1))
        with self.assertRaises(ValueError):probe.compose("B",scene=b+b)

    def test_any_early_leak_or_late_ambiguity_is_red(self):
        # Fake arrays exercise only validator rejection, not physical evidence.
        good={v:{phase:dict.fromkeys(probe.CHANNELS,1.)
                 for phase,_,_ in probe.PHASES} for v in ("A","B")}
        for phase in ("after_far","after_near"):good["B"][phase]["front"]=1.5
        self.assertTrue(probe.validate_observations(good))
        for phase in ("before_far","before_near"):
            for ch in probe.CHANNELS:
                bad=copy.deepcopy(good);bad["B"][phase][ch]+=.05
                with self.subTest(phase=phase,ch=ch),self.assertRaisesRegex(
                    AssertionError,"information leaks"):
                    probe.validate_observations(bad)
        for phase in ("after_far","after_near"):
            bad=copy.deepcopy(good);bad["B"][phase]["front"]=1.1
            with self.assertRaisesRegex(AssertionError,"not discriminable"):
                probe.validate_observations(bad)
        for modify in (
            lambda x:x["A"].pop("after_far"),
            lambda x:x["B"]["before_far"].pop("up"),
            lambda x:x["A"]["before_near"].update({"left":float("nan")})
        ):
            bad=copy.deepcopy(good);modify(bad)
            with self.assertRaises(AssertionError):
                probe.validate_observations(bad)

    def test_actual_C_sensors_and_draft_only_CI(self):
        source=(ROOT/"controllers/progression_a5_seq_occ_probe/"
                "progression_a5_seq_occ_probe.c").read_text()
        make=(ROOT/"controllers/progression_a5_seq_occ_probe/Makefile").read_text()
        workflow=(ROOT/".github/workflows/"
                  "ci-a5-sequential-occlusion-draft.yml").read_text()
        for device in ("range_front","range_back","range_left",
                       "range_right","range_up"):
            self.assertIn('"'+device+'"',source)
        for requirement in ("wb_distance_sensor_enable",
                            "wb_distance_sensor_get_value",
                            "wb_supervisor_node_reset_physics",
                            "wb_supervisor_node_get_orientation",
                            "physical_colliders_or_dimensions_modified",
                            "A5_SEQ_OCC_RAYS"):
            self.assertIn(requirement,source)
        self.assertNotIn("wb_motor_set_",source)
        self.assertNotIn("file_broker_runtime",make)
        self.assertIn("github.event.pull_request.draft == true",workflow)
        self.assertNotIn("name: CI Gate",workflow)
        self.assertIn("cyberbotics/webots@sha256:",workflow)
        self.assertIn("run_a5_sequential_occlusion_probe.py",workflow)
        self.assertIn("if-no-files-found: error",workflow)

if __name__=="__main__":unittest.main()
