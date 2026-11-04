"""Pure adversarial cursor tests. No Webots, mission READY or pupil PASS."""
from dataclasses import replace
import itertools
import math
import unittest

from tools.grand_prix.route_courses_v2 import plan_course
from tools.grand_prix.oracle_leg_cursor_v2 import (
    LegCursorError, start_leg_cursor, advance_leg_cursor,
)


class VariableLegCursorTests(unittest.TestCase):
    def test_all_108_routes_prove_both_turns_and_terminal_pad(self):
        seen = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                course = plan_course(17, lengths, turns, 1)
                route = course.route
                with self.subTest(id=course.identifier):
                    state = start_leg_cursor(course)
                    self.assertEqual(state.xy, route.legs[0].start)
                    for i in range(2):
                        before, after = route.legs[i:i+2]
                        state = advance_leg_cursor(state, before.at(before.length-.2))
                        self.assertEqual(state.active_leg, i)
                        state = advance_leg_cursor(state, before.end)
                        # Junction is ambiguous: no unproven early promotion.
                        self.assertEqual(state.active_leg, i)
                        state = advance_leg_cursor(state, after.at(.12))
                        self.assertEqual(state.active_leg, i)
                        state = advance_leg_cursor(state, after.at(.42))
                        self.assertEqual(state.active_leg, i+1)
                    terminal = route.legs[-1]
                    state = advance_leg_cursor(state, terminal.at(terminal.length-.78))
                    state = advance_leg_cursor(state, route.landing_target(2))
                    self.assertEqual(state.active_leg, 2)
                    self.assertEqual(state.xy, route.landing_target(2))
                    seen += 1
        self.assertEqual(seen, 108)

    def test_concave_shortcut_wrong_turn_skip_and_backward_return_fail(self):
        for turns in itertools.product(('G', 'D'), repeat=2):
            course = plan_course(11, (2.,2.5,3.), turns, 2)
            a, b, c = course.route.legs
            with self.subTest(turns=turns):
                fresh = start_leg_cursor(course)
                to_corner = advance_leg_cursor(fresh, a.at(a.length-.5))
                with self.assertRaisesRegex(LegCursorError, 'swept'):
                    advance_leg_cursor(to_corner, b.at(.5))
                with self.assertRaises(LegCursorError):
                    advance_leg_cursor(fresh, c.at(1.))
                state = advance_leg_cursor(to_corner, a.end)
                state = advance_leg_cursor(state, b.at(.42))
                self.assertEqual(state.active_leg, 1)
                # Return via the genuine junction, then try to re-enter the
                # previous segment beyond its corner-overlap footprint.
                state = advance_leg_cursor(state, a.end)
                with self.assertRaisesRegex(LegCursorError, 'skipped or reversed'):
                    advance_leg_cursor(state, a.at(a.length-.42))

    def test_terminal_closed_h_and_invalid_inputs_fail_closed(self):
        from tools.grand_prix.route_courses_v2 import reference_course
        course = reference_course(5)
        route = course.route
        state = start_leg_cursor(course)
        for invalid in (None, (), (0.,), (0., math.nan), (math.inf, 0.),
                        (0., True), ('0', 0.), (0., 0., .5)):
            with self.subTest(invalid=invalid), self.assertRaises(LegCursorError):
                advance_leg_cursor(state, invalid)
        with self.assertRaises(LegCursorError):
            start_leg_cursor(replace(course, count=course.count+1))
        for invalid in (None, 1, replace(state, active_leg=-1),
                        replace(state, active_leg=3),
                        replace(state, active_leg=True)):
            with self.assertRaises(LegCursorError):
                advance_leg_cursor(invalid, (0.,0.))
        with self.assertRaises(LegCursorError):
            advance_leg_cursor(replace(state, course=replace(course, count=0)), (0.,0.))
        # The full footprint includes the terminal pad, but not behind the H.
        state = replace(state, active_leg=2, xy=route.legs[-1].at(route.legs[-1].length-.7))
        with self.assertRaisesRegex(LegCursorError, 'swept'):
            advance_leg_cursor(state, route.legs[-1].at(route.legs[-1].length+.15))


if __name__ == '__main__':
    unittest.main()
