"""Compositional host counterexamples; not R2025a or mission qualification."""
from dataclasses import replace
import itertools
import math
import unittest

from tools.grand_prix.route_courses_v2 import plan_course, reference_course
from tools.grand_prix.oracle_gate_progress_v2 import GateProgressError
from tools.grand_prix.oracle_leg_cursor_v2 import LegCursorError
from tools.grand_prix.oracle_observed_course_v2 import (
    START_RADIUS, CourseProgressError,
    start_observed_course, advance_observed_course,
)


def pose(leg, along, z=.35):
    return (*leg.at(along), z)


class ObservedCourseProgressTests(unittest.TestCase):
    def test_twelve_reference_courses_compose_ordered_gates_and_both_turns(self):
        for index in range(12):
            course = reference_course(index)
            route = course.route
            with self.subTest(course=course.identifier):
                state = start_observed_course(course, (*route.legs[0].start, .35))
                self.assertEqual(state.count, 0)
                for leg in route.legs:
                    for gate in course.gates:
                        if gate.leg_index != leg.index:
                            continue
                        for along in (gate.along-.40, gate.along-.34,
                                      gate.along-.20, gate.along+.12,
                                      gate.along+.35):
                            state = advance_observed_course(state, pose(leg, along))
                    if leg.index < 2:
                        next_leg = route.legs[leg.index+1]
                        for point in (pose(leg, leg.length-.20),
                                      (*leg.end, .35),
                                      pose(next_leg, .12),
                                      pose(next_leg, .42)):
                            state = advance_observed_course(state, point)
                        self.assertEqual(state.leg.active_leg, leg.index+1)
                        self.assertEqual(state.gates.active_leg, leg.index+1)
                state = advance_observed_course(
                    state, (*route.landing_target(1), .35))
                self.assertEqual(state.count, course.count)
                self.assertEqual(state.leg.active_leg, 2)
                self.assertFalse(hasattr(state, 'ready'))
                self.assertFalse(hasattr(state, 'status'))

    def test_high_gate_and_reverse_recrossing_are_rejected_without_mutation(self):
        course = plan_course(17, (2., 2.5, 3.), ('G', 'D'), 3)
        leg, gate = course.route.legs[0], course.gates[0]
        start = start_observed_course(course, (*leg.start, .75))
        before = advance_observed_course(start, pose(leg, gate.along-.40, .75))
        with self.assertRaisesRegex(GateProgressError, 'gate-envelope'):
            advance_observed_course(before, pose(leg, gate.along+.35, .75))
        self.assertEqual(before.count, 0)
        low = start_observed_course(course, (*leg.start, .35))
        for along in (gate.along-.40, gate.along-.20, gate.along+.12,
                      gate.along+.35):
            low = advance_observed_course(low, pose(leg, along))
        self.assertEqual(low.count, 1)
        with self.assertRaisesRegex(GateProgressError, 'reverse-crossing'):
            advance_observed_course(low, pose(leg, gate.along+.05))
        self.assertEqual(low.count, 1)

    def test_swept_off_course_and_forged_cursor_bindings_fail(self):
        for turns in itertools.product(('G', 'D'), repeat=2):
            course = plan_course(17, (2., 2.5, 3.), turns, 3)
            first = course.route.legs[0]
            initial = start_observed_course(course, (*first.start, .35))
            with self.subTest(turns=turns):
                with self.assertRaises(LegCursorError):
                    advance_observed_course(initial, (first.start[0], 9., .35))
                self.assertEqual(initial.count, 0)
                broken = replace(initial, gates=replace(initial.gates, active_leg=1))
                with self.assertRaisesRegex(CourseProgressError, 'inconsistent'):
                    advance_observed_course(broken, (*first.start, .35))
                broken = replace(initial, leg=replace(initial.leg, xy=(8., 9.)))
                with self.assertRaisesRegex(CourseProgressError, 'inconsistent'):
                    advance_observed_course(broken, (*first.start, .35))

    def test_canonical_identity_start_bound_and_new_attempt(self):
        course = reference_course(8)
        first = course.route.legs[0]
        start = (*first.start, .35)
        fresh = start_observed_course(course, start)
        self.assertEqual(fresh.count, 0)
        self.assertEqual(fresh.xyz, start)
        self.assertEqual(START_RADIUS, .14)
        with self.assertRaises(CourseProgressError):
            start_observed_course(replace(course, count=1), start)
        with self.assertRaisesRegex(CourseProgressError, 'start disc'):
            start_observed_course(course, (*first.at(.20), .35))
        for invalid in (None, (), (0.,), (0., 0., math.nan),
                        (0., 0., math.inf), (True, 0., .35),
                        (0., 0., '0'), 'bad'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(CourseProgressError):
                    advance_observed_course(fresh, invalid)
        advanced = advance_observed_course(fresh, pose(first, .20))
        restarted = start_observed_course(course, start)
        self.assertEqual(restarted.count, 0)
        self.assertEqual(restarted.leg.active_leg, 0)
        self.assertNotEqual(advanced.xyz, restarted.xyz)


if __name__ == '__main__':
    unittest.main()
