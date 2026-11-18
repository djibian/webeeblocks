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
        self.assertEqual(a.count(" Solid {"),7)
        self.assertEqual(b.count(" Solid {"),7)
        self.assertEqual(a.count("boundingObject Box"),7)
        self.assertEqual(b.count("boundingObject Box"),7)
        changed=a.replace("3.200 0.450","3.200 -0.450").replace(
            "2.850 1.050","2.850 -1.050").replace(
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

    def test_no_common_fixed_lane_through_opposite_L_openings(self):
        # ANALYTICAL ONLY: no motorized trajectory, no pupil .wbb, no oracle.
        # Radius-inflated lateral spans must block every SAME-Y passage
        # at x=2.5 across both A and B within the collision corridor.
        import re
        def solid_box(source, name):
            section=source.split(f"DEF {name} Solid {{",1)
            self.assertEqual(len(section),2,name)
            part=section[1].split("boundingObject Box { size ",1)
            self.assertEqual(len(part),2,name)
            pos=re.search(r"translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)",part[0])
            size=re.match(r"([0-9.]+) ([0-9.]+) ([0-9.]+)",part[1])
            self.assertIsNotNone(pos,name)
            self.assertIsNotNone(size,name)
            return tuple(float(x) for x in pos.groups()+size.groups())
        scenes={v:probe.scene_file(v).read_text() for v in ("A","B")}
        posts={v:solid_box(scene,"A5_SEQ_L2_POST") for v,scene in scenes.items()}
        self.assertEqual(posts["A"][0],posts["B"][0])
        self.assertEqual(posts["A"][0],3.2)
        self.assertEqual(posts["A"][1],.45)
        self.assertEqual(posts["B"][1],-.45)
        # A possible pre-L1 lateral peek at x <= 1.05 remains beyond
        # the ideal 2 m forward sensor range after this displacement.
        # Native R2025a must independently falsify that approximation.
        self.assertGreater(posts["A"][0]-posts["A"][3]/2-1.05,2.05)
        for source in scenes.values():
            self.assertEqual(solid_box(source,"A5_SEQ_CORRIDOR_POS"),
                             (1.8,1.26,.55,4.3,.08,1.1))
            self.assertEqual(solid_box(source,"A5_SEQ_CORRIDOR_NEG"),
                             (1.8,-1.26,.55,4.3,.08,1.1))
            self.assertEqual(solid_box(source,"A5_SEQ_TERMINAL"),
                             (3.92,0,.55,.08,2.3,1.1))
        radius=.09
        corridor_max_y=1.26-.08/2-radius
        def blocked(post):
            return post[1]-post[4]/2-radius,post[1]+post[4]/2+radius
        a_low,a_high=blocked(posts["A"])
        b_low,b_high=blocked(posts["B"])
        self.assertLessEqual(b_low,-corridor_max_y)
        self.assertGreaterEqual(a_high,corridor_max_y)
        self.assertLessEqual(a_low,b_high)
        self.assertEqual((round(a_low,2),round(a_high,2)),(-.24,1.14))
        self.assertEqual((round(b_low,2),round(b_high,2)),(-1.14,.24))
        # No single fixed lane exists. Other approaches, overhead flight
        # and actual Crazyflie dynamics remain unqualified.

    def test_any_early_leak_or_late_ambiguity_is_red(self):
        # Fake arrays exercise only validator rejection, not physical evidence.
        good={v:{phase:dict.fromkeys(probe.CHANNELS,1.)
                 for phase,_,_ in probe.PHASES} for v in ("A","B")}
        for phase in ("after_far","after_near"):good["B"][phase]["front"]=1.5
        self.assertTrue(probe.validate_observations(good))
        for phase in ("before_far","before_near","before_peek"):
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
        self.assertIn('"before_peek",.60,.45,step',source)
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
