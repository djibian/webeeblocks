"""Pure directed terminal dwell counterexamples, not native/mission acceptance."""
from dataclasses import replace
import unittest

from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.oracle_course_progress_v2 import (
    advance_course_progress, start_course_progress,
)
from tools.grand_prix.oracle_terminal_dwell_v2 import (
    TerminalDwellError, start_terminal_dwell, advance_terminal_dwell,
)


def _pose(leg, along, lateral=0., z=.35):
    return (*leg.at(along, lateral), z)


def _terminal_progress(course):
    """Reach a target through the actual coupled route/H cursors, not a forged count."""
    state = start_course_progress(course, .35)
    for leg in course.route.legs:
        for gate in (g for g in course.gates if g.leg_index == leg.index):
            for delta in (-.40, -.34, -.20, .12, .35):
                state = advance_course_progress(state, _pose(leg, gate.along + delta))
        if leg.index < 2:
            following = course.route.legs[leg.index + 1]
            for point in (_pose(leg, leg.length - .20),
                          _pose(leg, leg.length),
                          _pose(following, .12),
                          _pose(following, .42)):
                state = advance_course_progress(state, point)
    last = course.route.legs[-1]
    state = advance_course_progress(state, _pose(last, last.length - .70))
    x, y = course.route.landing_target(course.count)
    state = advance_course_progress(state, (x, y, .35))
    return advance_course_progress(state, (x, y, .05))


class VariableTerminalDwellTests(unittest.TestCase):
    def step(self, state, progress, ms, *, velocity=(0., 0., 0.),
             airborne=True, completed=False):
        return advance_terminal_dwell(
            state, state.attempt, ms, progress, velocity,
            airborne=airborne, completed=completed)

    def test_twelve_reference_courses_terminal_orientation_and_exact_dwell(self):
        for index in range(12):
            course = reference_course(index)
            progress = _terminal_progress(course)
            with self.subTest(course=course.identifier):
                self.assertEqual(progress.leg.active_leg, 2)
                self.assertEqual(progress.count, course.count)
                witness = start_terminal_dwell(course, 11, 0., 0)
                witness = self.step(witness, progress, 100)
                self.assertIsNone(witness.completion_ms)
                witness = self.step(witness, progress, 200, completed=True)
                self.assertEqual(witness.state, 'open')
                witness = self.step(witness, progress, 699)
                self.assertEqual(witness.state, 'open')
                witness = self.step(witness, progress, 700)
                self.assertEqual(witness.state, 'stable-window')
                self.assertEqual(witness.completion_ms, 200)
                self.assertEqual(self.step(witness, progress, 1000,
                                           velocity=(1., 0., 0.)).state,
                                 'stable-window')
                self.assertFalse(hasattr(witness, 'status'))
                self.assertFalse(hasattr(witness, 'result'))

    def test_dwell_restarts_after_speed_or_wrong_target(self):
        course = reference_course(9)
        progress = _terminal_progress(course)
        state = start_terminal_dwell(course, 1, 0., 0)
        state = self.step(state, progress, 0, completed=True)
        state = self.step(state, progress, 400)
        self.assertEqual(state.state, 'open')
        state = self.step(state, progress, 401, velocity=(.13, 0., 0.))
        self.assertIsNone(state.stationary_since_ms)
        state = self.step(state, progress, 600)
        self.assertEqual(state.state, 'open')
        state = self.step(state, progress, 1099)
        self.assertEqual(state.state, 'open')
        self.assertEqual(self.step(state, progress, 1100).state, 'stable-window')
        target = course.route.landing_target(1)
        self.assertNotEqual(target, course.route.landing_target(course.count))
        wrong = replace(progress, pose=(*target, .05),
                        leg=replace(progress.leg, xy=target))
        self.assertEqual(self.step(start_terminal_dwell(course, 2, 0., 0),
                                   wrong, 0, completed=True).stationary_since_ms,
                         None)

    def test_expiration_is_irreversible_and_not_a_mission_result(self):
        course = reference_course(2)
        progress = _terminal_progress(course)
        state = start_terminal_dwell(course, 1, 0., 0)
        state = self.step(state, progress, 50, velocity=(.2, 0., 0.), completed=True)
        state = self.step(state, progress, 1549, velocity=(.2, 0., 0.))
        self.assertEqual(state.state, 'open')
        state = self.step(state, progress, 1550, velocity=(.2, 0., 0.))
        self.assertEqual(state.state, 'expired-window')
        self.assertEqual(self.step(state, progress, 2100).state, 'expired-window')

    def test_incomplete_h_or_nonterminal_leg_cannot_acquire_dwell(self):
        course = reference_course(10)
        progress = _terminal_progress(course)
        missing = replace(progress, gates=replace(progress.gates,
                                                 cursor=course.count-1))
        previous = replace(progress, leg=replace(progress.leg, active_leg=1),
                           gates=replace(progress.gates, active_leg=1))
        for variant in (missing, previous):
            with self.subTest(variant=variant):
                state = start_terminal_dwell(course, 1, 0., 0)
                self.assertEqual(self.step(state, variant, 0,
                                           completed=True).stationary_since_ms, None)
        self.assertIsNone(self.step(start_terminal_dwell(course, 1, 0., 0),
                                     progress, 0, airborne=False,
                                     completed=True).stationary_since_ms)

    def test_stale_attempt_clock_and_malformed_samples_fail_closed(self):
        course = reference_course(0)
        progress = _terminal_progress(course)
        state = start_terminal_dwell(course, 3, 0., 10)
        for attempt, ms in ((2, 10), (True, 10), (3, 9), (3, True)):
            with self.subTest(attempt=attempt, ms=ms), self.assertRaises(TerminalDwellError):
                advance_terminal_dwell(state, attempt, ms, progress, (0., 0., 0.),
                                       airborne=True, completed=True)
        for speed in (None, (0., 0.), (0., 0., float('nan')), (False, 0., 0.)):
            with self.assertRaises(TerminalDwellError):
                self.step(state, progress, 10, velocity=speed, completed=True)
        with self.assertRaises(TerminalDwellError):
            self.step(state, replace(progress, leg=replace(
                progress.leg, xy=(99., 99.))), 10, completed=True)
        for args in ((course, True, 0., 0), (course, 1, float('nan'), 0),
                     (course, 1, 0., True)):
            with self.assertRaises(TerminalDwellError):
                start_terminal_dwell(*args)


if __name__ == '__main__':
    unittest.main()
