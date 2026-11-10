"""Adversarial pure directed-H progression tests; not native flight proof."""
from dataclasses import replace
import math
import unittest

from tools.grand_prix.route_courses_v2 import plan_course, reference_course
from tools.grand_prix.oracle_gate_progress_v2 import (
    CRAFT_RADIUS, FRAME_CLEAR, CROSSING_PLANE,
    DirectedGateProgress, GateProgressError, start_directed_gates,
    advance_directed_gates,
)


def pose(leg, along, lateral=0., z=.35):
    return (*leg.at(along, lateral), z)


class DirectedGateProgressTests(unittest.TestCase):
    def advance(self, state, leg, before, after):
        return advance_directed_gates(state, leg.index, before, after)

    def pass_gate(self, state, leg, gate):
        samples = (
            pose(leg, gate.along - .40),
            pose(leg, gate.along - .34),
            pose(leg, gate.along - .20),
            pose(leg, gate.along + .12),
            pose(leg, gate.along + .35),
        )
        for a, b in zip(samples, samples[1:]):
            state = self.advance(state, leg, a, b)
        return state

    def test_twelve_references_keep_order_and_all_cardinal_turns(self):
        for number in range(12):
            course = reference_course(number)
            with self.subTest(course=course.identifier):
                state = start_directed_gates(course)
                self.assertEqual(state.count, 0)
                for leg in course.route.legs:
                    before = pose(leg, .01)
                    after = pose(leg, .02)
                    state = self.advance(state, leg, before, after)
                    gates = [g for g in course.gates if g.leg_index == leg.index]
                    for gate in gates:
                        state = self.pass_gate(state, leg, gate)
                self.assertEqual(state.count, course.count)
                self.assertEqual(state.course.identifier, course.identifier)

    def test_wrong_direction_and_unarmed_forward_shortcut_rejected(self):
        course = plan_course(17, (2., 2.5, 3.), ('G', 'D'), 3)
        leg, gate = course.route.legs[0], course.gates[0]
        fresh = start_directed_gates(course)
        with self.assertRaisesRegex(GateProgressError, 'reverse'):
            self.advance(fresh, leg, pose(leg, gate.along+.20),
                         pose(leg, gate.along-.20))
        # Returning just behind the *directed crossing plane* is also reverse.
        with self.assertRaisesRegex(GateProgressError, 'reverse'):
            self.advance(fresh, leg, pose(leg, gate.along+.35),
                         pose(leg, gate.along+.05))
        with self.assertRaisesRegex(GateProgressError, 'armed'):
            self.advance(fresh, leg, pose(leg, gate.along-.05),
                         pose(leg, gate.along+.36))
        self.assertEqual(fresh.count, 0)

    def test_approach_is_not_an_early_collision_or_height_veto(self):
        # This component only proves directed H progression. The full-course
        # swept physical Box oracle in oracle_attempt_v2 is the collision guard.
        course = plan_course(17, (2., 2.5, 3.), ('D', 'G'), 3)
        leg, gate = course.route.legs[0], course.gates[0]
        for z in (.35, .53, .70, .80):
            with self.subTest(height=z):
                state = self.advance(
                    start_directed_gates(course), leg,
                    pose(leg, gate.along - .40, z=z),
                    pose(leg, gate.along - .20, z=z))
                self.assertTrue(state.armed)
                self.assertEqual(state.count, 0)
                self.assertFalse(state.crossed)
        # A high approach must be possible even at the edge of the arming
        # window; a crash with the actual beam is rejected by the outer oracle.
        front = start_directed_gates(course)
        state = self.advance(front, leg, pose(leg, gate.along-.34, z=.8),
                             pose(leg, gate.along-.32, z=.8))
        self.assertTrue(state.armed)
        self.assertEqual(state.count, 0)

    def test_missing_gate_and_past_gate_reversal_fail(self):
        course = plan_course(17, (2., 2.5, 3.), ('G', 'D'), 3)
        first, second = course.route.legs[:2]
        gate = course.gates[0]
        start = start_directed_gates(course)
        with self.assertRaisesRegex(GateProgressError, 'missed-gate'):
            self.advance(start, second, pose(second, .01), pose(second, .02))
        counted = self.pass_gate(start, first, gate)
        self.assertEqual(counted.count, 1)
        with self.assertRaisesRegex(GateProgressError, 'reverse-crossing'):
            self.advance(counted, first, pose(first, gate.along+.35),
                         pose(first, gate.along-.20))
        # The previous implementation silently accepted a reverse recrossing
        # at +0.05 m because it incorrectly compared against -0.11 m.
        with self.assertRaisesRegex(GateProgressError, 'reverse-crossing'):
            self.advance(counted, first, pose(first, gate.along+.35),
                         pose(first, gate.along+.05))
        # Also refuse a reversal after crossing but before the whole H clears.
        armed = self.advance(start, first, pose(first, gate.along-.40),
                             pose(first, gate.along-.20))
        crossing = self.advance(armed, first, pose(first, gate.along-.20),
                                pose(first, gate.along+.12))
        self.assertTrue(crossing.crossed)
        self.assertEqual(crossing.count, 0)
        with self.assertRaisesRegex(GateProgressError, 'reverse-crossing'):
            self.advance(crossing, first, pose(first, gate.along+.12),
                         pose(first, gate.along+.05))
        self.assertEqual(counted.count, 1)

    def test_monotonic_leg_and_invalid_native_input(self):
        course = plan_course(9, (3., 2.5, 2.), ('D', 'D'), 2)
        state = start_directed_gates(course)
        zero = pose(course.route.legs[0], .1)
        for bad in (None, (0., 1.), (0., math.inf, .35),
                    (True, 0., .35), 'invalid'):
            with self.subTest(bad=bad), self.assertRaises(GateProgressError):
                advance_directed_gates(state, 0, bad, zero)
        for leg_index in (-1, 3, True, 2):
            with self.subTest(index=leg_index), self.assertRaises(GateProgressError):
                advance_directed_gates(state, leg_index, zero, zero)
        with self.assertRaises(GateProgressError):
            advance_directed_gates(None, 0, zero, zero)

    def test_canonical_binding_and_no_result_authority(self):
        course = plan_course(13, (2., 3., 2.5), ('G', 'G'), 2)
        state = start_directed_gates(course)
        self.assertTrue(hasattr(state, 'count'))
        self.assertFalse(hasattr(state, 'status'))
        self.assertFalse(hasattr(state, 'ready'))
        self.assertAlmostEqual(CRAFT_RADIUS, .09)
        self.assertAlmostEqual(FRAME_CLEAR, .33)
        self.assertAlmostEqual(CROSSING_PLANE, .11)
        with self.assertRaises(GateProgressError):
            start_directed_gates(replace(course, count=1))


if __name__ == '__main__':
    unittest.main()
