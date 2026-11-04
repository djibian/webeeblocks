"""Adversarial analytical tests for the GP variable-route swept corridor primitive."""
import itertools
import unittest
from tools.grand_prix.route_v2 import build_route
from tools.grand_prix.corridor_sweep_v2 import (
    RADIUS, boundary_edges, swept_corridor_clearance, swept_capsule_inside_corridors,
)


from tools.ci.test_grand_prix_leg_cursor_v2 import VariableLegCursorTests  # noqa: F401
from tools.ci.test_grand_prix_observed_course_v2 import ObservedCourseProgressTests  # noqa: F401

class VariableCorridorSweepTests(unittest.TestCase):
    def test_108_routes_leg_centres_and_corner_transitions_are_admissible(self):
        count = 0
        for lengths in itertools.product((2, 2.5, 3), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(17, lengths, turns)
                count += 1
                self.assertGreaterEqual(len(boundary_edges(route)), 8)
                self.assertEqual(boundary_edges(route), boundary_edges(route))
                for leg in route.legs:
                    self.assertTrue(swept_capsule_inside_corridors(
                        route, leg.at(.2), leg.at(leg.length-.2)))
                for first, second in zip(route.legs, route.legs[1:]):
                    self.assertTrue(swept_capsule_inside_corridors(
                        route, first.at(first.length-.12), second.at(.12)))
        self.assertEqual(count, 108)

    def test_shortcut_endpoints_inside_but_swept_middle_exits(self):
        route = build_route(0, (2., 2., 2.), ('G', 'G'))
        p, q = route.legs[0].at(1), route.legs[2].at(1)
        self.assertLess(swept_corridor_clearance(route, p, q), RADIUS)
        self.assertFalse(swept_capsule_inside_corridors(route, p, q))
        self.assertFalse(swept_capsule_inside_corridors(route, q, p))

    def test_tangency_risk_and_wrong_turns_rejected(self):
        route = build_route(0, (2., 2., 2.), ('G', 'G'))
        self.assertTrue(swept_capsule_inside_corridors(route, (1., .20), (1.5, .20)))
        self.assertFalse(swept_capsule_inside_corridors(route, (1., .21), (1.5, .21)))
        self.assertFalse(swept_capsule_inside_corridors(route, (1., 0), (1., .5)))
        for a, b in boundary_edges(route):
            point = ((a[0]+b[0])/2, (a[1]+b[1])/2)
            self.assertFalse(swept_capsule_inside_corridors(route, point, point))

    def test_input_refusals(self):
        route = build_route(0, (2., 2., 2.), ('G', 'D'))
        for invalid in (None, (), (1.,), (0., float('nan')),
                        (float('inf'), 0.), (True, 0.), (0., 'a')):
            with self.assertRaises(ValueError):
                swept_corridor_clearance(route, invalid, (0., 0.))
        with self.assertRaises(ValueError):
            swept_corridor_clearance(None, (0.,0.), (1., 0.))

    def test_observed_leg_cursor_suite_is_selected(self):
        # This class is imported by the canonical Grand Prix geometry
        # entry point; an import alone would NOT execute the nested tests.
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(VariableLegCursorTests)
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.testsRun, 3)
        if result.failures or result.errors:
            self.fail('observed leg cursor: ' + repr(result.failures + result.errors))


    def test_observed_course_composition_suite_is_selected(self):
        # Both pure cursors are exercised together; no native READY claim.
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ObservedCourseProgressTests)
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.testsRun, 4)
        if result.failures or result.errors:
            self.fail('observed course composition: ' + repr(result.failures + result.errors))

if __name__ == '__main__':
    unittest.main()
