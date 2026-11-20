"""Host-only variable-course attempt composition tests, never Webots PASS."""
import math
import unittest

from tools.grand_prix.oracle_attempt_v2 import (
    fail_pure_attempt, observe_pure_attempt, start_pure_attempt,
    _hits_mission_body,
)
from tools.grand_prix.progression_courses import progression_course
from tools.grand_prix.route_courses_v2 import reference_course


def observe(state, attempt, now_ms, pose, velocity, **kwargs):
    # The harness explicitly supplies native-contact evidence, even when empty.
    kwargs.setdefault('contacts', ())
    return observe_pure_attempt(state, attempt, now_ms, pose, velocity, **kwargs)


def travel(state, target):
    """Trace a synthetic, speed-bounded straight segment at 8-ms aligned time."""
    before = state.progress.pose
    distance = math.dist(before, target)
    n = max(1, math.ceil(distance/.04))
    for i in range(1, n+1):
        point = tuple(a+(b-a)*i/n for a, b in zip(before, target))
        velocity = tuple((b-a)/(.160*n) for a, b in zip(before, target))
        state = observe(state, state.attempt, state.last_ms+160,
                                     point, velocity)
        if state.result is not None:
            raise AssertionError((state.course.identifier, state.result,
                                  state.progress.leg.active_leg, point))
    return state


def follow_course(course, pad=None):
    """Drive the shared host oracles with synthetic positions, never actuators."""
    state = start_pure_attempt(course, 41, .015, 0)
    state = travel(state, (*course.route.legs[0].start, .75))
    terminal = course.route.legs[-1]
    for leg in course.route.legs:
        gate = next((g for g in course.gates if g.leg_index == leg.index), None)
        if gate:
            state = travel(state, (*leg.at(gate.along-.35), .75))
            state = travel(state, (*leg.at(gate.along-.35), .35))
            state = travel(state, (*leg.at(gate.along+.35), .35))
            state = travel(state, (*leg.at(gate.along+.35), .75))
        if leg != terminal:
            state = travel(state, (*leg.end, .75))
    target = course.landing_goal() if pad is None else course.landing_position(pad)
    # Enter the wider terminal area via the centreline; a diagonal chord
    # would cut across the concave boundary.
    state = travel(state, (*terminal.at(terminal.length-course.pad_distance_from_h), .75))
    state = travel(state, (*target, .75))
    return travel(state, (*target, .05))


def dwell(state, duration_ms):
    state = observe(state, state.attempt, state.last_ms+8,
                    state.progress.pose, (0., 0., 0.), completed=True)
    for _ in range(math.ceil(duration_ms / 8)):
        state = observe(state, state.attempt, state.last_ms+8,
                        state.progress.pose, (0., 0., 0.))
    return state


class PureVariableAttemptTests(unittest.TestCase):
    def test_progression_attempts_require_their_directed_legs_gates_and_pad(self):
        for activity, count in enumerate((1, 1, 1, 3, 5, 5, 7), start=1):
            for variant in range(1, count+1):
                course = progression_course(activity, variant)
                with self.subTest(course=course.identifier):
                    state = follow_course(course)
                    self.assertEqual(state.progress.count, course.count)
                    self.assertEqual(state.progress.leg.active_leg, len(course.route.legs)-1)
                    state = dwell(state, 504)
                    self.assertEqual(state.result.status, 'achieved')
                    self.assertEqual(state.result.crossings, course.count)
                    self.assertLess(state.result.elapsed_ms, 210000)

    def test_short_a4_cannot_use_terminal_low_exception_across_corridor(self):
        # A4's only leg is also the final leg, with no H at all. Merely
        # having the required (zero) crossing count must not make a flight
        # at 0.60 m lawful far from its lateral landing tile.
        course = progression_course(4, 1)
        state = start_pure_attempt(course, 41, .015, 0)
        state = travel(state, (0., 0., .75))
        state = travel(state, (.20, 0., .75))
        self.assertTrue(state.takeoff_done)
        result = observe(state, state.attempt, state.last_ms + 160,
                         (.20, 0., .60), (0., 0., -.9375))
        self.assertEqual(result.result.reason, 'low-outside-zone')
        # A centered final descent remains authorized and is exercised by
        # the 23 positive activity traces in the preceding test.

    def test_progression_pad_requires_whole_collider(self):
        """Reproduce the native A4 border overhang; do not change A8 rules."""
        course = progression_course(4, 1)
        x, y = course.landing_goal()
        for axis in (0, 1):
            with self.subTest(axis=axis):
                state = follow_course(course)
                # The 28-cm green tile contains the centre but NOT the full
                # 9-cm Grand Prix safety envelope at a 6-cm centre offset.
                near_edge = (x + (.06 if axis == 0 else 0.),
                             y + (.06 if axis == 1 else 0.), .05)
                state = travel(state, near_edge)
                state = dwell(state, 1504)
                self.assertEqual(state.result.status, 'not-achieved')
                self.assertEqual(state.result.reason, 'wrong-landing')

        # A genuinely contained circular footprint still completes the same
        # independent native-clock dwell when the body stays inside the tile.
        state = follow_course(course)
        state = travel(state, (x + .04, y + .04, .05))
        state = dwell(state, 504)
        self.assertEqual(state.result.status, 'achieved')

    def test_a5_wrong_visible_pad_fails_for_both_turn_directions(self):
        for variant in (1, 2):
            course = progression_course(5, variant)
            wrong_pad, = set(course.pads) - {course.required_pad}
            state = dwell(follow_course(course, wrong_pad), 1504)
            self.assertEqual(state.result.status, 'not-achieved')
            self.assertEqual(state.result.reason, 'wrong-landing')

    def test_progression_refuses_closed_h_contact_and_deadline(self):
        course = progression_course(1)
        state = start_pure_attempt(course, 41, .015, 0)
        state = travel(state, (0., 0., .75))
        for leg in course.route.legs[:-1]:
            state = travel(state, (*leg.end, .75))
        leg = course.route.legs[-1]
        state = travel(state, (*leg.at(leg.length-.16), .75))
        ended = observe(state, 41, state.last_ms+160,
                        (*leg.at(leg.length-.105), .75), (0., 0., 0.))
        self.assertEqual(ended.result.reason, 'envelope-contact')
        ended = observe(state, 41, 210000, state.progress.pose, (0., 0., 0.))
        self.assertEqual(ended.result.reason, 'time-limit')

    def test_reference_courses_can_reach_landing_dwell_without_any_ready_grant(self):
        """Only an ideal synthetic host trace, never a native pupil solution."""
        for index in range(12):
            course = reference_course(index)
            with self.subTest(course=course.identifier):
                state = follow_course(course)
                self.assertEqual(state.progress.count, course.count)
                self.assertEqual(state.progress.leg.active_leg, 2)
                state = dwell(state, 504)
                self.assertIsNotNone(state.result)
                self.assertEqual(state.result.status, 'achieved')
                self.assertEqual(state.result.crossings, course.count)
                self.assertLess(state.result.elapsed_ms, 210000)
                self.assertFalse(hasattr(state, 'ready'))
                self.assertFalse(hasattr(state, 'land_command'))

    def test_terminal_low_exception_requires_all_open_h_crossed(self):
        """Entering the last leg does not license low flight near the landing pad."""
        from dataclasses import replace
        from unittest.mock import patch

        course = reference_course(8)  # Three directed H, including leg 2.
        self.assertEqual(course.count, 3)
        self.assertEqual(tuple(gate.leg_index for gate in course.gates), (0, 1, 2))
        initial = start_pure_attempt(course, 4, .015, 0)
        xy = tuple(course.route.legs[2].at(course.route.legs[2].length - .5))
        pose = (*xy, .75)
        leg = replace(initial.progress.leg, active_leg=2, xy=xy)
        pending = replace(initial.progress, leg=leg,
                          gates=replace(initial.progress.gates, active_leg=2,
                                        cursor=course.count - 1),
                          pose=pose)
        complete = replace(pending, gates=replace(pending.gates, cursor=course.count))
        self.assertEqual(pending.count, course.count - 1)
        self.assertEqual(complete.count, course.count)

        for progress, allowed in ((pending, False), (complete, True)):
            with self.subTest(crossings=progress.count):
                sample = replace(initial, progress=progress, last_ms=160,
                                 airborne=True, takeoff_done=True)
                # Isolate the low-band *authorization* argument, not a
                # synthetic mission PASS or a substitute for Webots contacts.
                with patch('tools.grand_prix.oracle_attempt_v2._hits_mission_body',
                           return_value=False), \
                     patch('tools.grand_prix.oracle_attempt_v2.low_segment_allowed_v2',
                           return_value=True) as low:
                    observe(sample, 4, 168, pose, (0., 0., 0.))
                low.assert_called_once()
                self.assertIs(low.call_args.kwargs['final'], allowed)

    def test_only_swept_course_boundary_gets_a_public_reason(self):
        from unittest.mock import patch
        from tools.grand_prix.oracle_leg_cursor_v2 import LegCursorError
        course = reference_course(5)
        for diagnostic, expected in (
            ('swept-course-boundary', 'course-boundary'),
            ('skipped or reversed segment', 'invalid-route-observation'),
        ):
            with self.subTest(diagnostic=diagnostic):
                fresh = start_pure_attempt(course, 2, .015, 0)
                with patch('tools.grand_prix.oracle_attempt_v2.advance_course_progress',
                           side_effect=LegCursorError(diagnostic)):
                    ended = observe(fresh, 2, 8, fresh.progress.pose, (0.,0.,0.))
                self.assertEqual(ended.result.status, 'not-achieved')
                self.assertEqual(ended.result.reason, expected)

    def test_irreversible_timeout_and_identity(self):
        course = reference_course(1)
        original = start_pure_attempt(course, 1, .015, 0)
        expired = observe(original, 1, 210000, original.progress.pose,
                                       (0.,0.,0.))
        self.assertEqual(expired.result.reason, 'time-limit')
        self.assertIs(observe(expired, 1, 210008,
                      original.progress.pose, (0.,0.,0.), completed=True), expired)
        wrong_id = observe(original, 2, 8, original.progress.pose,
                                        (0.,0.,0.))
        self.assertEqual(wrong_id.result.reason, 'invalid-attempt-clock')
        self.assertEqual(observe(original, 1, -1,
                         original.progress.pose, (0.,0.,0.)).result.reason,
                         'invalid-attempt-clock')
        failed = fail_pure_attempt(original, 7, 'contact')
        self.assertEqual(failed.result.reason, 'contact')
        self.assertIs(fail_pure_attempt(failed, 9, 'anything'), failed)

    def test_duplicate_native_timestamp_refuses_phantom_progress(self):
        """No lateral or longitudinal progress can accrue without fresh native time."""
        course = reference_course(5)
        initial = start_pure_attempt(course, 7, .015, 1000)
        # Before the fix, a repeated timestamp could move up to 6 cm because
        # displacement was bounded by max(.06, dt/500) even when dt == 0.
        same_start = observe(initial, 7, 1000, (.05, 0., .015),
                             (0., 0., 0.))
        self.assertEqual(same_start.result.reason, 'invalid-attempt-clock')
        self.assertEqual(same_start.progress, initial.progress)
        fresh = observe(initial, 7, 1008, initial.progress.pose,
                        (0., 0., 0.))
        self.assertIsNone(fresh.result)
        duplicate = observe(fresh, 7, 1008, (.05, 0., .015),
                            (0., 0., 0.))
        self.assertEqual(duplicate.result.reason, 'invalid-attempt-clock')
        self.assertEqual(duplicate.progress, fresh.progress)
        self.assertIs(observe(duplicate, 7, 1016, (.06, 0., .015),
                              (0., 0., 0.)), duplicate)

    def test_contact_altitude_sample_and_low_safety_rejections(self):
        course = reference_course(0)
        s = start_pure_attempt(course, 3, .015, 0)
        missing = observe_pure_attempt(s, 3, 8, s.progress.pose, (0.,0.,0.))
        self.assertEqual(missing.result.reason, 'device-contact')
        self.assertEqual(observe(s, 3, 160, (.40,0.,.015),
                                              (0.,0.,0.)).result.reason,
                         'sample-displacement')
        self.assertEqual(observe(s, 3, 160, (0.,0.,.015),
                                              (0.,0.,0.),
                                              contacts=[(0.,0.,.1)]).result.reason,
                         'device-contact')
        self.assertEqual(observe(s, 3, 160, (0.,0.,.015),
                                              (0.,0.,float('nan'))).result.reason,
                         'invalid-sample')
        self.assertEqual(observe(s, 3, 160, (0.,0.,1.2),
                                              (0.,0.,0.)).result.reason,
                         'sample-displacement')
        s = observe(s, 3, 160, (.05,0.,.015), (.31,0.,0.))
        s = observe(s, 3, 320, (.10,0.,.015), (.31,0.,0.))
        outside = observe(s, 3, 480, (.15,0.,.015), (.31,0.,0.))
        self.assertEqual(outside.result.reason, 'low-outside-zone')
        self.assertIsNone(s.result)

    def test_high_h_approach_safe_until_actual_beam_contact(self):
        # Real geometry, not the earlier artificial +/-0.33 m H-height veto.
        # The first H on the owner-tested Linux route 5 is 1 m from origin.
        from dataclasses import replace
        course = reference_course(5)
        gate = next(g for g in course.gates if g.leg_index == 0)
        leg = course.route.legs[0]
        self.assertEqual(gate.along, 1.0)
        state = start_pure_attempt(course, 10, .015, 0)
        before = (*leg.at(gate.along-.30), .8)
        approach = (*leg.at(gate.along-.20), .8)
        beam_contact = (*leg.at(gate.along-.10), .8)
        self.assertFalse(_hits_mission_body(before, approach, state.boxes))
        self.assertTrue(_hits_mission_body(approach, beam_contact, state.boxes))
        # The whole-course oracle still irreversibly rejects actual contact,
        # even though the directed H progress cursor no longer invents it.
        state = replace(state, progress=replace(
            state.progress, pose=approach,
            leg=replace(state.progress.leg, xy=approach[:2])),
            last_ms=5000, airborne=True, takeoff_done=True)
        ended = observe(state, 10, 5160, beam_contact, (0.625, 0., 0.))
        self.assertEqual(ended.result.status, 'not-achieved')
        self.assertEqual(ended.result.reason, 'envelope-contact')

    def test_canonical_physical_inventory_catches_gate_or_corner_body(self):
        course = reference_course(9)
        state = start_pure_attempt(course, 1, .015, 0)
        self.assertEqual(len(state.boxes), 8+3*course.count)
        for box in state.boxes:
            self.assertTrue(_hits_mission_body(box.position, box.position,
                                                state.boxes), box.name)
        with self.assertRaises(ValueError):
            start_pure_attempt(course, True, .015, 0)
        with self.assertRaises(ValueError):
            start_pure_attempt(course, 1, .015, True)
        with self.assertRaises(ValueError):
            fail_pure_attempt(state, -1, 'bad')


if __name__ == '__main__':
    unittest.main()
