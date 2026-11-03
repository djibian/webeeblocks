"""Static geometry tests: no claim of native R2025a flight, sensor or oracle PASS."""
import itertools
import math
import unittest
from tools.grand_prix.route_v2 import WIDTH, build_route
from tools.grand_prix.route_solid_v2 import corner_boxes, static_world, visual_guides, THICKNESS, HEIGHT


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
