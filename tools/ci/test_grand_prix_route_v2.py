"""Pure geometry invariants (no claim of native Webots validation)."""
import itertools
import math
import unittest
from tools.grand_prix.route_v2 import WIDTH, VERSION, build_route


class VariableRouteTests(unittest.TestCase):
    def test_entire_length_turn_matrix(self):
        identifiers = set()
        for lengths in itertools.product((2, 2.5, 3), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(17, lengths, turns)
                self.assertEqual(route.identifier, build_route(17, lengths, turns).identifier)
                identifiers.add(route.identifier)
                self.assertEqual(route.lengths, tuple(float(v) for v in lengths))
                self.assertEqual(route.turns, turns)
                self.assertEqual(len(route.corners), 2)
                for i, leg in enumerate(route.legs):
                    self.assertAlmostEqual(math.dist(leg.start, leg.end), lengths[i])
                    self.assertEqual(leg.at(0), leg.start)
                    self.assertEqual(leg.at(leg.length), leg.end)
                    self.assertEqual(leg.local(leg.at(leg.length/2, .25)), (leg.length/2, .25))
                    if i < 2:
                        self.assertEqual(leg.end, route.legs[i+1].start)
                for i, corner in enumerate(route.corners):
                    self.assertEqual(corner.junction, route.legs[i].end)
                    for start, end in corner.arms:
                        self.assertEqual(start, corner.outer)
                        self.assertAlmostEqual(math.dist(start, end), WIDTH)
                    # Face of L is outside both incoming and outgoing half-width bands.
                    inc, out = route.legs[i:i+2]
                    self.assertAlmostEqual(abs(inc.local(corner.outer)[1]), WIDTH/2)
                    self.assertAlmostEqual(abs(out.local(corner.outer)[1]), WIDTH/2)
                center = route.landing_target(1)
                left = route.landing_target(2)
                right = route.landing_target(3)
                self.assertAlmostEqual(math.dist(center, left), .5)
                self.assertAlmostEqual(math.dist(center, right), .5)
                self.assertEqual(route.legs[-1].local(left)[1], .5)
                self.assertEqual(route.legs[-1].local(right)[1], -.5)
                self.assertLess(route.legs[-1].local(center)[0], route.legs[-1].length)
        self.assertEqual(len(identifiers), 3**3 * 2**2)

    def test_reproducible_identity_and_fail_closed_inputs(self):
        a = build_route(0, (2, 2.5, 3), ('G', 'D'))
        self.assertEqual(a.identifier, 'gp-route-v2-L2000-2500-3000-TGD-s0')
        self.assertEqual(a, build_route(0, [2., 2.5, 3.], ['G', 'D']))
        self.assertNotEqual(a.identifier, build_route(1, (2, 2.5, 3), ('G', 'D')).identifier)
        for seed in (True, -1, 65536, 1.2):
            with self.assertRaises(ValueError): build_route(seed, (2, 2, 2), ('G', 'G'))
        for lengths in ((2, 2), (2, 2, 2, 2), (2, float('nan'), 3), (True, 2, 3),
                        (2, 2.0001, 3), (1.5, 2, 3)):
            with self.assertRaises(ValueError): build_route(0, lengths, ('G', 'G'))
        for turns in (('G',), ('G', 'G', 'G'), ('G', 'X'), ('g', 'D'), (True, 'D')):
            with self.assertRaises(ValueError): build_route(0, (2, 2, 2), turns)
        for count in (0, 4, 2.0, True):
            with self.assertRaises(ValueError): a.landing_target(count)
        for value in (float('nan'), float('inf'), True):
            with self.assertRaises(ValueError): a.legs[0].at(value)
        with self.assertRaises(ValueError): a.legs[0].local((0., float('nan')))


if __name__ == '__main__':
    unittest.main()
