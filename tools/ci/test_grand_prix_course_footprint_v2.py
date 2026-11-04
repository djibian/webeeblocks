"""Full-course adversarial geometry; no claim of native or GUI acceptance."""
import itertools
import math
import unittest
from tools.grand_prix.route_v2 import build_route
from tools.grand_prix.route_terminal_v2 import landing_footprint
from tools.grand_prix.course_footprint_v2 import (
    course_rectangles, course_boundary_edges, swept_course_clearance,
    swept_capsule_inside_course, red_boundary_marks,
)
from tools.grand_prix.corridor_sweep_v2 import swept_capsule_inside_corridors


class CompleteCourseFootprintTests(unittest.TestCase):
    def routes(self):
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                yield build_route(17, lengths, turns)

    def test_108_routes_allow_all_targets_but_never_a_pass_behind_final_h(self):
        for route in self.routes():
            with self.subTest(route=route.identifier):
                last = route.legs[-1]
                center = route.landing_target(1)
                self.assertEqual(len(course_rectangles(route)), 4)
                for count in (1, 2, 3):
                    target = route.landing_target(count)
                    self.assertTrue(swept_capsule_inside_course(route, center, target))
                # The former primitive deliberately excludes side targets.
                self.assertFalse(swept_capsule_inside_corridors(
                    route, center, route.landing_target(2)))
                behind = last.at(last.length+.15)
                self.assertTrue(swept_capsule_inside_corridors(route, behind, behind))
                self.assertFalse(swept_capsule_inside_course(route, behind, behind))
                self.assertFalse(swept_capsule_inside_course(route, center, behind))
                for point in landing_footprint(route):
                    self.assertFalse(swept_capsule_inside_course(route, point, point))

    def test_no_radius_reduction_at_every_boundary_or_terminal_widening(self):
        for route in self.routes():
            with self.subTest(route=route.identifier):
                for a, b in course_boundary_edges(route):
                    midpoint = ((a[0]+b[0])/2, (a[1]+b[1])/2)
                    self.assertFalse(swept_capsule_inside_course(route, midpoint, midpoint))
                last = route.legs[-1]
                for side in (-1, 1):
                    safe = last.at(last.length-.70, side*.809)
                    edge = last.at(last.length-.70, side*.811)
                    self.assertTrue(swept_capsule_inside_course(route, safe, safe))
                    self.assertFalse(swept_capsule_inside_course(route, edge, edge))
                safe = last.at(last.length-.091)
                edge = last.at(last.length-.089)
                self.assertTrue(swept_capsule_inside_course(route, safe, safe))
                self.assertFalse(swept_capsule_inside_course(route, edge, edge))

    def test_concave_chords_fail_and_ordered_centreline_remains_available(self):
        for route in self.routes():
            with self.subTest(route=route.identifier):
                for first, second in zip(route.legs, route.legs[1:]):
                    a = first.at(first.length-.50)
                    b = second.at(.50)
                    self.assertTrue(swept_capsule_inside_course(route, a, a))
                    self.assertTrue(swept_capsule_inside_course(route, b, b))
                    # The chord cuts within one radius of the concave vertex.
                    self.assertFalse(swept_capsule_inside_course(route, a, b))
                    self.assertFalse(swept_capsule_inside_course(route, b, a))
                    self.assertTrue(swept_capsule_inside_course(route, a, first.end))
                    self.assertTrue(swept_capsule_inside_course(route, first.end, b))
                # At the widening, both endpoints are valid but their diagonal
                # can leave the narrow corridor before reaching the wide area.
                last = route.legs[-1]
                a, b = last.at(last.length-1.2), last.at(last.length-.7, .65)
                self.assertTrue(swept_capsule_inside_course(route, a, a))
                self.assertTrue(swept_capsule_inside_course(route, b, b))
                self.assertFalse(swept_capsule_inside_course(route, a, b))

    def test_visible_tape_is_on_the_enforced_exterior_with_no_internal_seams(self):
        for route in self.routes():
            with self.subTest(route=route.identifier):
                marks = red_boundary_marks(route)
                self.assertTrue(marks)
                self.assertEqual(marks, red_boundary_marks(route))
                for x, y, sx, sy in marks:
                    self.assertGreater(sx, 0.)
                    self.assertGreater(sy, 0.)
                    self.assertAlmostEqual(swept_course_clearance(route, (x,y), (x,y)), 0.)
                # An internal seam at the beginning of the widened area is
                # free floor, not a red or enforced boundary.
                last = route.legs[-1]
                seam = last.at(last.length-.95)
                self.assertGreater(swept_course_clearance(route, seam, seam), .20)

    def test_directed_gate_cursor_adversarial_suite_is_canonical(self):
        from tools.ci.test_grand_prix_gate_progress_v2 import DirectedGateProgressTests
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            DirectedGateProgressTests)
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.testsRun, 6)
        if result.failures or result.errors:
            self.fail('directed H gate progression: ' +
                      repr(result.failures + result.errors))

    def test_coupled_leg_and_h_progress_is_canonical(self):
        from tools.ci.test_grand_prix_course_progress_v2 import CoupledCourseProgressTests
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            CoupledCourseProgressTests)
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.testsRun, 5)
        if result.failures or result.errors:
            self.fail('coupled segment / directed H progression: ' +
                      repr(result.failures + result.errors))

    def test_invalid_inputs_fail_closed(self):
        route = build_route(0, (2., 2.5, 3.), ('G','D'))
        for value in (None, (), True):
            with self.assertRaises(ValueError):
                course_rectangles(value)
        for p in ((True, 0.), (math.nan, 0.), (0., math.inf), (0.,)):
            with self.assertRaises(ValueError):
                swept_course_clearance(route, p, (0.,0.))


if __name__ == '__main__':
    unittest.main()
