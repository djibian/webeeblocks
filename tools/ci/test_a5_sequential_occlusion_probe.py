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
        self.assertEqual(a.count(" Solid {"),9)
        self.assertEqual(b.count(" Solid {"),9)
        self.assertEqual(a.count("boundingObject Box"),9)
        self.assertEqual(b.count("boundingObject Box"),9)
        changed=a.replace("3.200 0.450","3.200 -0.450").replace(
            "2.850 1.125","2.850 -1.125").replace(
            "experiment A:","experiment B:").replace(
            "WEBEEBLOCKS_A5_SEQ_OCC_A_SCENE",
            "WEBEEBLOCKS_A5_SEQ_OCC_B_SCENE")
        self.assertEqual(changed,b)
        for v in probe.VARIANTS:
            w=probe.compose(v)
            self.assertEqual(w.count('controller "progression_a5_seq_occ_probe"'),1)
            self.assertEqual(w.count("Floor { size 8 4 }"),1)
            self.assertNotIn('controller "crazyflie_runtime_v2"',w)
        for bad in ("E","",None,"A+B"):
            with self.assertRaises(ValueError):probe.compose(bad)
        with self.assertRaises(ValueError):
            probe.compose("A",scene=a.replace(" Solid {"," Robot {",1))
        with self.assertRaises(ValueError):probe.compose("B",scene=b+b)

    def test_two_independent_L_choices_have_four_noncolliding_worlds(self):
        scenes={v:probe.scene_file(v).read_text() for v in probe.VARIANTS}
        for v in probe.VARIANTS:
            self.assertEqual(scenes[v].count(" Solid {"),9)
            self.assertEqual(scenes[v].count("boundingObject Box"),9)
            self.assertIn(f"DEF WEBEEBLOCKS_A5_SEQ_OCC_{v}_SCENE Group",scenes[v])
            first_y=" -0.480 " if v in ("A","B") else " 0.480 "
            first_arm=" 0.275 " if v in ("A","B") else " -0.275 "
            second_y=" 0.450 " if v in ("A","C") else " -0.450 "
            second_arm=" 1.125 " if v in ("A","C") else " -1.125 "
            self.assertIn("translation 1.000"+first_y+"0.550",scenes[v])
            self.assertIn("translation 0.650"+first_arm+"0.550",scenes[v])
            self.assertIn("translation 3.200"+second_y+"0.550",scenes[v])
            self.assertIn("translation 2.850"+second_arm+"0.550",scenes[v])
            phases=probe.phases_for(v)
            self.assertEqual(len(phases),6)
            self.assertEqual(phases[0],("before_far",.40,0.))
            self.assertEqual(phases[1],("before_near",.70,0.))
            self.assertEqual(phases[3],("before_corner",.98,
                                       .45 if v in ("A","B") else -.45))
            self.assertEqual(phases[4],("after_far",2.00,
                                       .60 if v in ("A","B") else -.60))
        # The only A->C / B->D geometry changes are two L1 positions:
        # the second L, roof, sidewalls and terminal stay identical.
        for original,mirrored in (("A","C"),("B","D")):
            expected=scenes[original].replace(
                "experiment "+original+":","experiment "+mirrored+":").replace(
                f"WEBEEBLOCKS_A5_SEQ_OCC_{original}_SCENE",
                f"WEBEEBLOCKS_A5_SEQ_OCC_{mirrored}_SCENE").replace(
                "translation 1.000 -0.480 0.550",
                "translation 1.000 0.480 0.550").replace(
                "translation 0.650 0.275 0.550",
                "translation 0.650 -0.275 0.550")
            self.assertEqual(expected,scenes[mirrored])
        self.assertNotEqual(scenes["A"],scenes["B"])
        self.assertNotEqual(scenes["A"],scenes["C"])
        for bad in ("E",None,"A+D"):
            with self.assertRaises(ValueError):probe.phases_for(bad)

    def test_first_L_outer_bypass_closed_by_real_overlapping_boxes(self):
        # Source-level geometry: the previous L1 post did not reach the
        # sidewall, allowing a common fixed corridor in opposite L1 worlds.
        # No motor/PID or pupil-completion claim is made by this inequality.
        import re
        limits={}
        inner_wall=1.26-.08/2
        for v in probe.VARIANTS:
            src=probe.scene_file(v).read_text()
            part=src.split("DEF A5_SEQ_L1_POST Solid {",1)[1].split(
                "DEF A5_SEQ_L1_ARM Solid {",1)[0]
            m=re.search(r"translation 1\.000 (-?[0-9.]+) 0\.550",part)
            size=re.search(
                r"boundingObject Box \{ size 0\.080 ([0-9.]+) 1\.100 \}",part)
            self.assertIsNotNone(m,v)
            self.assertIsNotNone(size,v)
            y=float(m[1]);width=float(size[1])
            self.assertAlmostEqual(abs(y),.480)
            self.assertAlmostEqual(width,1.520)
            self.assertGreaterEqual(abs(y)+width/2-inner_wall,.015)
            # Negative mutant: narrowing the post to the previous 1.150 m
            # would reopen a gap, even with the new centre position.
            self.assertLess(abs(y)+1.150/2,inner_wall)
            limits[v]=(y-width/2,y+width/2)
        for positive,negative in (("A","C"),("B","D")):
            left,right=limits[positive],limits[negative]
            self.assertLessEqual(left[0],-inner_wall)
            self.assertGreaterEqual(right[1],inner_wall)
            self.assertGreaterEqual(left[1],right[0])
            self.assertLess(left[1],inner_wall)
            self.assertGreater(right[0],-inner_wall)

    def test_no_common_fixed_lane_through_opposite_L_openings(self):
        # ANALYTICAL ONLY: no motorized trajectory, no pupil .wbb, no oracle.
        # The solid post and arm must reach the wall at a shared X section,
        # without assuming an inflated lateral size for the drone.
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
            roof=solid_box(source,"A5_SEQ_CORRIDOR_ROOF")
            rear=solid_box(source,"A5_SEQ_CORRIDOR_BACK")
            self.assertEqual(roof,(1.79,0,1.14,4.4,2.6,.12))
            self.assertEqual(rear,(-.35,0,.55,.08,2.6,1.1))
            # This only refutes the documented straight overflight inside
            # the closed corridor, not arbitrary Webots motorized strategies.
            top_of_L=.55+1.1/2
            roof_underside=roof[2]-roof[5]/2
            # Solid vertical overlap: no nonzero clearance slot exists,
            # independent of the exact rotor/body vertical envelope.
            self.assertLess(roof_underside,top_of_L)
            self.assertGreaterEqual(top_of_L-roof_underside,.015)
            # Roof overlaps both ends and both sidewalls of the tunnel.
            self.assertLessEqual(roof[0]-roof[3]/2,rear[0]-rear[3]/2)
            self.assertGreaterEqual(roof[0]+roof[3]/2,3.92+.08/2)
            self.assertGreaterEqual(roof[4]/2,1.26+.08/2)
        section_x = 3.18
        for variant, sign, wall_name in (("A", 1, "POS"), ("B", -1, "NEG")):
            with self.subTest(variant=variant):
                post = posts[variant]
                arm = solid_box(scenes[variant], "A5_SEQ_L2_ARM")
                wall = solid_box(scenes[variant], f"A5_SEQ_CORRIDOR_{wall_name}")
                for box in (post, arm, wall):
                    self.assertLess(abs(box[0] - section_x), box[3] / 2)
                post_inner, post_outer = (sign * post[1] + edge * post[4] / 2 for edge in (-1, 1))
                arm_inner, arm_outer = (sign * arm[1] + edge * arm[4] / 2 for edge in (-1, 1))
                wall_inner = sign * wall[1] - wall[4] / 2
                self.assertLess(post_inner, 0)
                self.assertLess(arm_inner, post_outer)
                self.assertGreaterEqual(arm_outer - wall_inner, .015)
                self.assertLess(arm_inner, 1.155)
                self.assertGreater(arm_outer, 1.155)
        # The blocked intervals overlap across variants. The historical
        # +/-1.155 m bypass intersects an actual arm, even at zero radius.

    def test_four_worlds_need_different_fixed_height_paths(self):
        # Geometric research witness only. A blind, unchanged XY path would
        # have to avoid the UNION of colliders from all four variants. Each
        # world individually must nevertheless admit a passage: otherwise
        # a negative universal path would just certify an impossible lesson.
        # Neither grid reachability nor a particular path is a PID/Blockly
        # flight or a proof that a loop/variable is required.
        import math
        import re
        from collections import deque

        names = (
            "L1_POST", "L1_ARM", "L2_POST", "L2_ARM",
            "CORRIDOR_POS", "CORRIDOR_NEG", "CORRIDOR_BACK",
            "CORRIDOR_ROOF", "TERMINAL",
        )

        def physical_boxes(variant):
            source = probe.scene_file(variant).read_text()
            boxes = []
            for name in names:
                parts = source.split(f"DEF A5_SEQ_{name} Solid {{", 1)
                self.assertEqual(len(parts), 2, (variant, name))
                body = parts[1].split("boundingObject Box { size ", 1)
                self.assertEqual(len(body), 2, (variant, name))
                position = re.search(
                    r"translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)",
                    body[0],
                )
                dimensions = re.match(
                    r"([0-9.]+) ([0-9.]+) ([0-9.]+)", body[1],
                )
                self.assertIsNotNone(position, (variant, name))
                self.assertIsNotNone(dimensions, (variant, name))
                boxes.append(tuple(float(v) for v in
                                   position.groups() + dimensions.groups()))
            return boxes

        # XY grid at nominal flying centre height 0.50 m; 2 cm spacing.
        # Search stays inside the physical sidewalls, from common blue
        # takeoff (0,0) to x=3.50 before the terminal wall.
        step = 0.02
        nx, ny = 176, 119
        start = (0, 59)
        goal = (175, 59)

        def reachable(boxes, radius):
            blocked = set()
            for ix in range(nx):
                x = ix * step
                for iy in range(ny):
                    y = (iy - 59) * step
                    for bx, by, bz, sx, sy, sz in boxes:
                        # Vertical overlap with the tested flight plane.
                        if not (bz - sz / 2 <= .50 <= bz + sz / 2):
                            continue
                        dx = max(abs(x - bx) - sx / 2, 0.)
                        dy = max(abs(y - by) - sy / 2, 0.)
                        if math.hypot(dx, dy) <= radius:
                            blocked.add((ix, iy))
                            break
            self.assertNotIn(start, blocked)
            self.assertNotIn(goal, blocked)
            queue = deque([start])
            seen = {start}
            while queue:
                x, y = queue.popleft()
                if (x, y) == goal:
                    return True
                for point in ((x-1,y), (x+1,y), (x,y-1), (x,y+1)):
                    px, py = point
                    if (0 <= px < nx and 0 <= py < ny and
                            point not in blocked and point not in seen):
                        seen.add(point)
                        queue.append(point)
            return False

        worlds = {v: physical_boxes(v) for v in probe.VARIANTS}
        self.assertEqual(set(worlds), {"A", "B", "C", "D"})
        for v, boxes in worlds.items():
            self.assertEqual(len(boxes), 9)
            with self.subTest(variant=v):
                self.assertTrue(reachable(boxes, .07),
                                "individual world cannot be traversed")
        union = [box for boxes in worlds.values() for box in boxes]
        # Even a point centre (zero-radius) has no universal fixed XY
        # route: the mirrored L1 blockers overlap in opposite worlds.
        self.assertFalse(reachable(union, 0.0))
        self.assertFalse(reachable(union, .07))
        # Adversarial control: collapsing all four choices to A MUST admit
        # a common path. This proves the union test really uses variants.
        self.assertTrue(reachable(worlds["A"] * 4, .07))

    def test_any_early_leak_or_late_ambiguity_is_red(self):
        # Fake arrays exercise only validator rejection, not physical evidence.
        good={v:{phase:dict.fromkeys(probe.CHANNELS,1.)
                 for phase,_,_ in probe.PHASES} for v in probe.VARIANTS}
        for phase in ("after_far","after_near"):
            good["B"][phase]["front"]=1.5
            good["D"][phase]["front"]=.5
        for v in ("C","D"):good[v]["before_near"]["left"]=1.5
        self.assertTrue(probe.validate_observations(good))
        for first,second in (("A","B"),("C","D")):
            for phase in ("before_far","before_near","before_peek","before_corner"):
                for ch in probe.CHANNELS:
                    bad=copy.deepcopy(good);bad[second][phase][ch]+=.05
                    with self.subTest(pair=first+second,phase=phase,ch=ch),self.assertRaisesRegex(
                        AssertionError,"information leaks"):
                        probe.validate_observations(bad)
        for phase in ("after_far","after_near"):
            bad=copy.deepcopy(good);bad["B"][phase]["front"]=1.1
            with self.assertRaisesRegex(AssertionError,"not discriminable"):
                probe.validate_observations(bad)
        bad=copy.deepcopy(good)
        for v in ("C","D"):bad[v]["before_near"]["left"]=1.
        with self.assertRaisesRegex(AssertionError,"L1 not discriminable"):
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
        self.assertIn('"before_peek",.60,sample_side,step',source)
        self.assertIn('"before_corner",.98,sample_side,step',source)
        self.assertIn('"after_far",2.00,sample_late,step',source)
        self.assertIn('!!C',source)
        self.assertIn('!!D',source)
        self.assertIn('1.,first_y,.55,.08,1.52,1.1',source)
        self.assertIn("wb_supervisor_node_enable_contact_points_tracking",source)
        self.assertIn("wb_supervisor_node_get_contact_points",source)
        self.assertIn("contacts!=0",source)
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
