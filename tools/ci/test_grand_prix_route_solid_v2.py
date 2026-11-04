"""Static geometry tests: no claim of native R2025a flight, sensor or oracle PASS."""
import itertools
import math
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.grand_prix.route_v2 import WIDTH, build_route
from tools.grand_prix.route_solid_v2 import corner_boxes, static_world, visual_guides, THICKNESS, HEIGHT
from tools.ci.test_grand_prix_static_l_terminal_probe_v2 import StaticLTerminalProbeTests  # noqa: F401


class CornerSolidTests(unittest.TestCase):
    def test_108_route_matrix_and_outside_clearances(self):
        cases=set()
        for lengths in itertools.product((2.,2.5,3.), repeat=3):
            for turns in itertools.product(('G','D'), repeat=2):
                route=build_route(0,lengths,turns)
                cases.add(route.identifier)
                boxes=corner_boxes(route)
                self.assertEqual(len(boxes),4)
                self.assertEqual(len({b.name for b in boxes}),4)
                for box in boxes:
                    self.assertEqual(sorted((box.sx,box.sy)),[.04,.60])
                    self.assertIn('locked TRUE',box.vrml())
                    self.assertIn('boundingObject Box',box.vrml())
                    self.assertIn(f'{HEIGHT:.6f}',box.vrml())
                for leg in route.legs:
                    for distance in (0.,leg.length/2,leg.length):
                        x,y=leg.at(distance)
                        gap=min(math.hypot(max(abs(x-b.x)-b.sx/2,0),
                                           max(abs(y-b.y)-b.sy/2,0)) for b in boxes)
                        self.assertGreater(gap,WIDTH/2-THICKNESS/2-.001)
                guides=visual_guides(route)
                self.assertEqual(sum('GP_V2_WHITE_' in x for x in guides),3)
                self.assertTrue(all('boundingObject' not in x for x in guides))
        self.assertEqual(len(cases),108)

    def test_no_red_mark_is_strictly_inside_any_other_corridor(self):
        from tools.grand_prix.route_solid_v2 import red_dashes
        all_cases = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G','D'), repeat=2):
                route = build_route(0, lengths, turns)
                all_cases += 1
                dashes = red_dashes(route)
                self.assertTrue(dashes)
                for dash in dashes:
                    leg = route.legs[dash.leg_index]
                    self.assertGreater(dash.end-dash.start, .015)
                    self.assertLessEqual(dash.end, leg.length)
                    self.assertEqual(leg.at((dash.start+dash.end)/2,
                                            dash.side*WIDTH/2), (dash.x, dash.y))
                    # Check the whole red segment, not only its midpoint.
                    delta = min(.001, (dash.end-dash.start)/3)
                    for along in (dash.start+delta,
                                  (dash.start+dash.end)/2,
                                  dash.end-delta):
                        x, y = leg.at(along, dash.side*WIDTH/2)
                        for other in route.legs:
                            if other.index == leg.index:
                                continue
                            xmin, ymin, xmax, ymax = other.bounds()
                            self.assertFalse(xmin+1e-8 < x < xmax-1e-8 and
                                             ymin+1e-8 < y < ymax-1e-8,
                                             (route.identifier, dash, other.index))
        self.assertEqual(all_cases, 108)
        # Independent regression: red on an internal overlap is NOT an edge.
        route = build_route(0, (2.,2.5,3.), ('G','D'))
        forbidden = [dash for dash in red_dashes(route)
                     if dash.leg_index == 0 and dash.side == 1 and dash.step == 6]
        self.assertFalse(forbidden)

    def test_world_refuses_executable_pedagogical_claim(self):
        route=build_route(4,(2.,2.5,3.),('G','D'))
        scene=static_world(route)
        self.assertEqual(scene,static_world(route))
        self.assertEqual(scene.count('EXTERNPROTO "webots://'),4)
        self.assertEqual(scene.count('DEF GP_V2_L_'),4)
        self.assertEqual(scene.count('boundingObject Box { size '),4)
        self.assertIn('controller "<none>"',scene)
        self.assertIn('window "<none>"',scene)
        self.assertNotIn('controller "grand_prix_u_evaluator"',scene)
        self.assertNotIn('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/',scene)

    def test_inadmissible_types(self):
        with self.assertRaises(TypeError): corner_boxes(None)
        with self.assertRaises(TypeError): static_world(None)


if __name__=='__main__':
    unittest.main()
