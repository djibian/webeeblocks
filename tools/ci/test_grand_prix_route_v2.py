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

    def test_physical_l_corner_fragments_matrix(self):
        """Pure projected geometry: every L is detectable and stays outside centre paths."""
        from tools.grand_prix.corners_world_v2 import (
            HEIGHT, THICKNESS, make_corner_bars, corner_world_fragment,
        )

        def ray_distance(origin, direction, bars):
            hits = []
            for bar in bars:
                x, y = bar.centre[:2]
                sx, sy = bar.size[:2]
                xmin, xmax = x - sx/2, x + sx/2
                ymin, ymax = y - sy/2, y + sy/2
                px, py = origin
                dx, dy = direction
                if dx == 1 and ymin <= py <= ymax and px <= xmax:
                    hits.append(max(0., xmin - px))
                elif dx == -1 and ymin <= py <= ymax and px >= xmin:
                    hits.append(max(0., px - xmax))
                elif dy == 1 and xmin <= px <= xmax and py <= ymax:
                    hits.append(max(0., ymin - py))
                elif dy == -1 and xmin <= px <= xmax and py >= ymin:
                    hits.append(max(0., py - ymax))
            return min(hits) if hits else None

        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(17, lengths, turns)
                solids = make_corner_bars(route)
                self.assertEqual(len(solids), 4)
                text = corner_world_fragment(route)
                self.assertEqual(text.count(' Solid {'), 4)
                self.assertEqual(text.count('boundingObject Box { size'), 4)
                self.assertEqual(text.count('locked TRUE'), 4)
                for i, corner in enumerate(route.corners):
                    group = solids[2*i:2*i+2]
                    self.assertEqual({bar.corner_index for bar in group}, {i})
                    self.assertEqual({bar.arm_index for bar in group}, {0, 1})
                    for bar, (start, end) in zip(group, corner.arms):
                        self.assertAlmostEqual(math.dist(start, end), .60)
                        self.assertEqual(bar.centre[2], HEIGHT/2)
                        self.assertEqual(bar.size[2], HEIGHT)
                        self.assertAlmostEqual(max(bar.size[:2]), WIDTH)
                        self.assertAlmostEqual(min(bar.size[:2]), THICKNESS)
                        self.assertAlmostEqual(bar.centre[0], (start[0]+end[0])/2)
                        self.assertAlmostEqual(bar.centre[1], (start[1]+end[1])/2)
                    incoming, outgoing = route.legs[i:i+2]
                    forward = incoming.forward
                    left = (-forward[1], forward[0])
                    side = (-left[0], -left[1]) if corner.turn == 'G' else left
                    observed = incoming.at(incoming.length - .25)
                    front_range = ray_distance(observed, forward, group)
                    side_range = ray_distance(observed, side, group)
                    self.assertIsNotNone(front_range)
                    self.assertIsNotNone(side_range)
                    self.assertGreater(front_range, 0)
                    self.assertLess(front_range, 2.)  # Multi-Ranger nominal reach
                    self.assertGreater(side_range, 0)
                    self.assertLess(side_range, 2.)
                    for distance in (.0, .10, .20, .30):
                        for point in (incoming.at(incoming.length-distance),
                                      outgoing.at(distance)):
                            for bar in group:
                                dx = max(0., abs(point[0]-bar.centre[0])-bar.size[0]/2)
                                dy = max(0., abs(point[1]-bar.centre[1])-bar.size[1]/2)
                                self.assertGreater(math.hypot(dx, dy), .09)

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
