"""Static geometry and fail-closed tests, not native Webots R2025a evidence."""
import itertools
import math
import unittest
from tools.grand_prix.route_v2 import build_route
from tools.grand_prix.route_terminal_v2 import (
    ARRIVAL_LENGTH, ARRIVAL_WIDTH, CLOSURE_SPAN, HEIGHT, LANDING_TILE,
    landing_footprint, landing_targets, terminal_boxes,
)


class VariableTerminalTests(unittest.TestCase):
    def test_108_routes_have_four_visible_physical_terminal_parts(self):
        cases = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(17, lengths, turns)
                leg = route.legs[-1]
                cases += 1
                boxes = terminal_boxes(route)
                self.assertEqual(len(boxes), 4)
                self.assertEqual(len({b.name for b in boxes}), 4)
                self.assertEqual([b.name for b in boxes], [
                    'GP_V2_FINAL_LEFT', 'GP_V2_FINAL_RIGHT',
                    'GP_V2_FINAL_BEAM', 'GP_V2_FINAL_PANEL',
                ])
                for b in boxes:
                    node = b.vrml()
                    self.assertIn(f'DEF {b.name} Solid', node)
                    self.assertIn('locked TRUE', node)
                    self.assertIn('boundingObject Box', node)
                    self.assertIn('geometry Box', node)
                    self.assertAlmostEqual(b.z-b.sz/2, 0. if b.name !=
                        'GP_V2_FINAL_BEAM' else .69)
                    self.assertLessEqual(b.z+b.sz/2, HEIGHT)
                panel = boxes[-1]
                self.assertTrue(panel.translucent)
                self.assertIn('transparency .65', panel.vrml())
                self.assertEqual((panel.x, panel.y), leg.end)
                self.assertEqual(panel.sz, HEIGHT)
                if leg.direction % 2 == 0:
                    self.assertEqual((panel.sx, panel.sy), (.04, CLOSURE_SPAN))
                else:
                    self.assertEqual((panel.sx, panel.sy), (CLOSURE_SPAN, .04))
                self.assertEqual(boxes[2].sz, .12)
                for sign, box in ((-1, boxes[0]), (1, boxes[1])):
                    self.assertEqual((box.x, box.y), leg.at(leg.length, sign*.87))
        self.assertEqual(cases, 108)

    def test_108_routes_keep_all_three_tiles_inside_widened_arrival(self):
        cases = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(18, lengths, turns)
                leg = route.legs[-1]
                cases += 1
                footprint = landing_footprint(route)
                self.assertEqual(footprint, tuple(leg.at(a, b) for a, b in (
                    (leg.length-ARRIVAL_LENGTH, -ARRIVAL_WIDTH/2),
                    (leg.length, -ARRIVAL_WIDTH/2),
                    (leg.length, ARRIVAL_WIDTH/2),
                    (leg.length-ARRIVAL_LENGTH, ARRIVAL_WIDTH/2),
                )))
                targets = landing_targets(route)
                self.assertEqual(targets, tuple(route.landing_target(n)
                                                 for n in (1, 2, 3)))
                for n, target in enumerate(targets, start=1):
                    along, lateral = leg.local(target)
                    self.assertAlmostEqual(along, leg.length-.70)
                    self.assertAlmostEqual(lateral, {1: 0., 2: .50, 3: -.50}[n])
                    # The entire 28cm landing tile fits, not only its centre.
                    self.assertGreaterEqual(along-LANDING_TILE/2,
                                            leg.length-ARRIVAL_LENGTH)
                    self.assertLessEqual(along+LANDING_TILE/2, leg.length)
                    self.assertLessEqual(abs(lateral)+LANDING_TILE/2,
                                         ARRIVAL_WIDTH/2)
        self.assertEqual(cases, 108)

    def test_unrelated_objects_cannot_be_mistaken_for_routes(self):
        for value in (None, False, (), object()):
            with self.assertRaises(TypeError):
                terminal_boxes(value)
            with self.assertRaises(TypeError):
                landing_footprint(value)
            with self.assertRaises(TypeError):
                landing_targets(value)


if __name__ == '__main__':
    unittest.main()
