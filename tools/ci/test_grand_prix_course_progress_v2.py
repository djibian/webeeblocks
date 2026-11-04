"""Adversarial pure coupling tests; no Webots/native or mission PASS."""
from dataclasses import replace
import math
import unittest

from tools.grand_prix.route_courses_v2 import plan_course, reference_course
from tools.grand_prix.oracle_course_progress_v2 import (
    CoupledCourseProgress, CourseProgressError, advance_course_progress,
    start_course_progress,
)
from tools.grand_prix.oracle_gate_progress_v2 import GateProgressError
from tools.grand_prix.oracle_leg_cursor_v2 import LegCursorError


def pose(leg, along, lateral=0., z=.35):
    return (*leg.at(along, lateral), z)


class CoupledCourseProgressTests(unittest.TestCase):
    def observe(self, state, point):
        return advance_course_progress(state, point)

    def test_twelve_routes_count_directed_h_without_pupil_route_metadata(self):
        for index in range(12):
            course = reference_course(index)
            route = course.route
            with self.subTest(course=course.identifier):
                state = start_course_progress(course, .35)
                self.assertEqual(state.count, 0)
                self.assertEqual(state.leg.active_leg, 0)
                for leg in route.legs:
                    for gate in (g for g in course.gates
                                 if g.leg_index == leg.index):
                        # A low H is traversed in its own directed frame.
                        for delta in (-.40, -.34, -.20, .12, .35):
                            state = self.observe(
                                state, pose(leg, gate.along + delta))
                    if leg.index < 2:
                        following = route.legs[leg.index + 1]
                        for point in (
                                pose(leg, leg.length - .20),
                                pose(leg, leg.length),
                                pose(following, .12),
                                pose(following, .42)):
                            state = self.observe(state, point)
                        self.assertEqual(state.leg.active_leg, leg.index+1)
                self.assertEqual(state.count, course.count)
                self.assertFalse(hasattr(state, 'status'))
                self.assertFalse(hasattr(state, 'ready'))

    def test_stale_uncompleted_h_cannot_promote_a_leg(self):
        course = plan_course(17, (2., 2.5, 3.), ('G', 'D'), 3)
        leg, following = course.route.legs[:2]
        gate = course.gates[0]
        state = start_course_progress(course, .35)
        for delta in (-.40, -.34, -.20, .12, .35):
            state = self.observe(state, pose(leg, gate.along + delta))
        for point in (pose(leg, leg.length - .2),
                      pose(leg, leg.length), pose(following, .12)):
            state = self.observe(state, point)
        self.assertEqual(state.count, 1)
        # A stale H count is not a valid basis for promotion at the junction.
        stale = replace(state, gates=replace(
            state.gates, cursor=0, armed=False, crossed=False))
        with self.assertRaisesRegex(
                (GateProgressError, CourseProgressError), 'missed-gate|uncompleted H'):
            self.observe(stale, pose(following, .42))
        self.assertEqual(stale.count, 0)
        self.assertEqual(state.count, 1)

    def test_wrong_direction_and_invalid_gate_frame_are_refused(self):
        course = plan_course(17, (2., 2.5, 3.), ('D', 'G'), 3)
        state = start_course_progress(course, .35)
        leg, gate = course.route.legs[0], course.gates[0]
        crossed = self.observe(state, pose(leg, gate.along + .20))
        self.assertTrue(crossed.gates.crossed)
        with self.assertRaisesRegex(GateProgressError, 'reverse-crossing'):
            self.observe(crossed, pose(leg, gate.along + .05))
        armed = self.observe(state, pose(leg, gate.along - .40))
        with self.assertRaisesRegex(GateProgressError, 'gate-envelope'):
            self.observe(armed, pose(leg, gate.along + .12, z=.8))

    def test_concave_shortcut_and_bogus_samples_fail_closed(self):
        course = plan_course(11, (2., 2.5, 3.), ('G', 'D'), 1)
        state = start_course_progress(course, .35)
        a, b = course.route.legs[:2]
        state = self.observe(state, pose(a, a.length - .5))
        with self.assertRaises(LegCursorError):
            self.observe(state, pose(b, .5))
        for bad in (None, True, (0., 0.), (0., 0., math.inf),
                    (0., 0., math.nan), (False, 0., .35)):
            with self.subTest(bad=bad), self.assertRaises(CourseProgressError):
                self.observe(state, bad)

    def test_mismatched_state_and_forged_course_fail_closed(self):
        course = reference_course(2)
        state = start_course_progress(course, .35)
        with self.assertRaises(CourseProgressError):
            self.observe(replace(state, pose=(1., 0., .35)), state.pose)
        with self.assertRaises(CourseProgressError):
            self.observe(replace(state, gates=replace(
                state.gates, active_leg=1)), state.pose)
        with self.assertRaises(CourseProgressError):
            self.observe(replace(state, course=reference_course(3)), state.pose)
        with self.assertRaises(CourseProgressError):
            start_course_progress(course, True)
        with self.assertRaises(CourseProgressError):
            start_course_progress(course, math.nan)
        with self.assertRaises(CourseProgressError):
            self.observe(None, (0., 0., .35))
        self.assertIsInstance(state, CoupledCourseProgress)


if __name__ == '__main__':
    unittest.main()
