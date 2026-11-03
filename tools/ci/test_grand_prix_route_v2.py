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


    def test_provisional_gate_placements_are_directed_and_reproducible(self):
        from tools.grand_prix.route_courses_v2 import (
            LOW_BEFORE, LOW_AFTER, plan_course,
        )
        for lengths in itertools.product((2, 2.5, 3), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                for count in (1, 2, 3):
                    course = plan_course(17, lengths, turns, count)
                    self.assertEqual(course, plan_course(17, lengths, turns, count))
                    self.assertEqual(len(course.gates), count)
                    self.assertEqual(len({g.leg_index for g in course.gates}), count)
                    self.assertEqual(tuple(g.leg_index for g in course.gates),
                                     tuple(sorted(g.leg_index for g in course.gates)))
                    self.assertTrue(course.identifier.endswith('-H'+str(count)))
                    for g in course.gates:
                        leg = course.route.legs[g.leg_index]
                        self.assertEqual(g.direction, leg.direction)
                        self.assertEqual(g.position, leg.at(g.along))
                        self.assertEqual(leg.local(g.position), (g.along, 0.0))
                        self.assertGreater(g.along, LOW_BEFORE)
                        self.assertLess(g.along + LOW_AFTER, leg.length)
                        if g.leg_index < 2:
                            self.assertGreaterEqual(g.along - LOW_BEFORE, 0.35 - 1e-9)
                            self.assertGreaterEqual(leg.length - g.along - LOW_AFTER,
                                                    0.35 - 1e-9)
                        else:
                            # At least one band edge remains before the final
                            # nominal centre, but no swept clearance is claimed.
                            self.assertLess(g.along + LOW_AFTER,
                                            leg.length - 0.70)

    def test_twelve_pure_course_examples_cover_turns_counts_and_mixed_legs(self):
        from tools.grand_prix.route_courses_v2 import reference_course
        examples = [reference_course(i) for i in range(12)]
        self.assertEqual(len({c.identifier for c in examples}), 12)
        self.assertEqual({c.route.turns for c in examples},
                         {('G','G'), ('G','D'), ('D','G'), ('D','D')})
        self.assertEqual({c.count for c in examples}, {1, 2, 3})
        self.assertTrue(any(len(set(c.route.lengths)) > 1 for c in examples))
        for turns in {('G','G'), ('G','D'), ('D','G'), ('D','D')}:
            self.assertEqual({c.count for c in examples if c.route.turns == turns},
                             {1, 2, 3})
        for bad in (-1, 12, 1.2, True):
            with self.assertRaises(ValueError): reference_course(bad)

    def test_plan_rejects_out_of_domain_gate_counts(self):
        from tools.grand_prix.route_courses_v2 import plan_course
        for count in (-1, 0, 4, 1.0, True, "2"):
            with self.assertRaises(ValueError):
                plan_course(0, (2, 2, 2), ('G', 'D'), count)



if __name__ == '__main__':
    unittest.main()
