"""Pure counterexamples for directed Grand Prix low-flight zones (#811).

These tests do not claim native Webots, collision or route progress evidence.
"""
import itertools
import unittest
from dataclasses import dataclass

from tools.grand_prix.route_v2 import build_route
from tools.grand_prix.oracle_low_v2 import low_segment_allowed_v2


@dataclass(frozen=True)
class Gate:
    leg_index: int
    along: float
    direction: int


def point(leg, along, lateral, z=.35):
    # No 1e-6 rounding: strict epsilon-outside counterexamples are meaningful.
    fx, fy = leg.forward
    x, y = leg.start
    return (x + fx * along - fy * lateral,
            y + fy * along + fx * lateral, z)


class VariableLowZoneTests(unittest.TestCase):
    def test_all_directed_gate_bands_and_strict_radius_boundaries(self):
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(17, lengths, turns)
                for leg in route.legs:
                    along = leg.length / 2 if leg.index < 2 else .65
                    gate = Gate(leg.index, along, leg.direction)
                    allowed = lambda a, b: low_segment_allowed_v2(
                        a, b, route, (gate,))
                    self.assertTrue(allowed(point(leg, along-.30, 0),
                                            point(leg, along+.30, 0)))
                    self.assertTrue(allowed(point(leg, along-.4599, 0),
                                            point(leg, along+.4599, 0)))
                    self.assertFalse(allowed(point(leg, along-.460001, 0),
                                             point(leg, along+.30, 0)))
                    self.assertFalse(allowed(point(leg, along-.20, .2100001),
                                             point(leg, along+.20, .2100001)))
                    self.assertTrue(allowed(point(leg, along-.20, .2099999),
                                            point(leg, along+.20, .2099999)))
                    self.assertFalse(allowed(point(leg, along-.20, 0),
                                             point(leg, along+.460001, 0)))
                    self.assertFalse(allowed(point(leg, along-.30, .22),
                                             point(leg, along+.30, -.22)))
                    reversed_gate = Gate(leg.index, along, (leg.direction+2)%4)
                    self.assertFalse(low_segment_allowed_v2(
                        point(leg, along, 0), point(leg, along, 0),
                        route, (reversed_gate,)))

    def test_terminal_exception_rotates_with_final_heading(self):
        for turns in itertools.product(('G', 'D'), repeat=2):
            for length in (2., 2.5, 3.):
                route = build_route(25, (2., 2.5, length), turns)
                leg = route.legs[2]
                a = point(leg, length-.70, .5, .1)
                self.assertTrue(low_segment_allowed_v2(a, a, route, (), final=True))
                self.assertFalse(low_segment_allowed_v2(a, a, route, (), final=False))
                for along, lateral in ((length-.860001, 0),
                                       (length-.109999, 0),
                                       (length-.7, .810001),
                                       (length-.7, -.810001)):
                    p = point(leg, along, lateral, .1)
                    self.assertFalse(low_segment_allowed_v2(p, p, route, (), final=True))
                self.assertTrue(low_segment_allowed_v2(
                    a, point(leg, length-.70, .5, .6), route, (), final=True))

    def test_takeoff_exception_uses_exact_initial_disk_and_fraction(self):
        route = build_route(0, (2., 2., 2.), ('G','G'))
        first = route.legs[0]
        start = point(first, 0, 0, .1)
        within = point(first, .10, 0, .1)
        outside = point(first, .15, 0, .1)
        self.assertTrue(low_segment_allowed_v2(start, within, route, (),
                                                takeoff_until=1.))
        self.assertFalse(low_segment_allowed_v2(start, within, route, (),
                                                 takeoff_until=.5))
        self.assertFalse(low_segment_allowed_v2(start, outside, route, (),
                                                 takeoff_until=1.))
        self.assertFalse(low_segment_allowed_v2(start, start, route, (),
                                                 takeoff_until=-1.))
        self.assertFalse(low_segment_allowed_v2(start, start, route, ()))
        self.assertTrue(low_segment_allowed_v2(point(first, .7, 0, .62),
                                                point(first, 1.4, 0, .62), route, ()))

    def test_variable_beam_height_and_unchanged_yellow_envelope(self):
        # The historical gp-u-v1 low threshold remains 0.60 m. Only the
        # variable Grand Prix matches the 0.62 m physical beam underside.
        from tools.grand_prix.oracle_low_v2 import LOW_THRESHOLD
        from tools.grand_prix.oracle_u import LOW_THRESHOLD as HISTORICAL
        from tools.grand_prix.route_open_h_v2 import BEAM_BOTTOM
        from tools.grand_prix.oracle_gate_progress_v2 import BEAM_BOTTOM as GATE_HEIGHT
        self.assertEqual(HISTORICAL, .60)
        self.assertEqual(LOW_THRESHOLD, BEAM_BOTTOM)
        self.assertEqual(GATE_HEIGHT, BEAM_BOTTOM)
        self.assertEqual(LOW_THRESHOLD, .62)
        route = build_route(17, (2., 2.5, 3.), ('G','D'))
        leg = route.legs[0]
        gate = Gate(0, 1.0, leg.direction)
        for z in (.60, .61, .619999):
            with self.subTest(height=z):
                self.assertFalse(low_segment_allowed_v2(
                    point(leg, .40, 0, z), point(leg, .40, 0, z), route, (gate,)))
                self.assertTrue(low_segment_allowed_v2(
                    point(leg, 1.0, 0, z), point(leg, 1.0, 0, z), route, (gate,)))
        for z in (.62, .620001, .80):
            self.assertTrue(low_segment_allowed_v2(
                point(leg, .40, 0, z), point(leg, .40, 0, z), route, (gate,)))
        # Lines remain at H +/- .55; the *whole* 9-cm-radius craft must
        # be inside them. Moving the painted lines is not authorized.
        self.assertFalse(low_segment_allowed_v2(
            point(leg, .50, 0, .5), point(leg, .50, 0, .5), route, (gate,)))
        self.assertTrue(low_segment_allowed_v2(
            point(leg, .54, 0, .5), point(leg, .54, 0, .5), route, (gate,)))
        self.assertFalse(low_segment_allowed_v2(
            point(leg, 1.50, 0, .5), point(leg, 1.50, 0, .5), route, (gate,)))
        self.assertTrue(low_segment_allowed_v2(
            point(leg, 1.46, 0, .5), point(leg, 1.46, 0, .5), route, (gate,)))
        self.assertFalse(low_segment_allowed_v2(
            point(leg, 1.0, .211, .5), point(leg, 1.0, .211, .5),
            route, (gate,)))

    def test_invalid_samples_or_frames_fail_closed(self):
        route = build_route(0, (2., 2.5, 3.), ('G','D'))
        leg = route.legs[0]
        p = point(leg, .8, 0)
        for sample in ((0., 0., float('nan')), (0., 0., float('inf')),
                       (True, 0., .35), (0., .35)):
            self.assertFalse(low_segment_allowed_v2(sample, p, route, ()))
        self.assertFalse(low_segment_allowed_v2(p, p, route,
                                                 (Gate(3, .8, 0),)))
        self.assertFalse(low_segment_allowed_v2(p, p, route,
                                                 (Gate(0, float('nan'), 0),)))
        self.assertFalse(low_segment_allowed_v2(p, p, route, (),
                                                 takeoff_until=float('nan')))


if __name__ == '__main__':
    unittest.main()
