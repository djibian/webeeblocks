"""Host-only directed H progression for variable Grand Prix routes (#811).

This is not a mission oracle, collision sensor, native admission or PASS.
The caller must independently enforce continuous course containment, segment
transitions, sample displacement, contacts, low-flight rules, clock/RESET and
irreversible 210000-ms LAND authority. Never expose CoursePlan to Blockly.
"""
from dataclasses import dataclass, replace
import math

from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier

CRAFT_RADIUS = .09
FRAME_CLEAR = .24 + CRAFT_RADIUS
CROSSING_PLANE = .11
HALF_OPENING = .28
BEAM_BOTTOM = .62
FLOOR_CLEARANCE = .10


class GateProgressError(ValueError):
    """Invalid directed crossing or broken host progression precondition."""


@dataclass(frozen=True)
class DirectedGateProgress:
    course: CoursePlan
    cursor: int = 0
    active_leg: int = 0
    armed: bool = False
    crossed: bool = False

    @property
    def count(self):
        return self.cursor


def start_directed_gates(course):
    """Bind an immutable fresh cursor to one canonical, host-only CoursePlan."""
    if type(course) is not CoursePlan:
        raise GateProgressError('canonical CoursePlan required')
    try:
        if course_from_identifier(course.identifier) != course:
            raise GateProgressError('forged or inconsistent CoursePlan')
    except (TypeError, ValueError) as error:
        raise GateProgressError('canonical CoursePlan required') from error
    return DirectedGateProgress(course)


def _point(value):
    if (not isinstance(value, (tuple, list)) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in value)):
        raise GateProgressError('finite native 3D position required')
    return value


def _relative(gate, leg, point):
    """Unrounded directed coordinates; never use rounded Leg.local here."""
    dx, dy = point[0] - gate.position[0], point[1] - gate.position[1]
    fx, fy = leg.forward
    return dx * fx + dy * fy, -dx * fy + dy * fx


def _check_frame_sweep(gate, leg, before, after, start, end):
    """Check every point of the observed *frame-overlapping* linear sweep.

    Values vary affinely: testing the clipped interval endpoints covers the
    lateral craft envelope and vertical envelope, not just sampled endpoints.
    Geometry, solid contacts and speed remain mandatory separate checks.
    """
    if start == end:
        if abs(start) > FRAME_CLEAR:
            return
        low, high = 0., 1.
    else:
        t0 = (-FRAME_CLEAR - start) / (end - start)
        t1 = (FRAME_CLEAR - start) / (end - start)
        low, high = max(0., min(t0, t1)), min(1., max(t0, t1))
        if low > high:
            return
    for fraction in (low, high):
        point = tuple(a + (b - a) * fraction for a, b in zip(before, after))
        _, lateral = _relative(gate, leg, point)
        z = point[2]
        if (abs(lateral) + CRAFT_RADIUS > HALF_OPENING or
                z + CRAFT_RADIUS > BEAM_BOTTOM or
                z - CRAFT_RADIUS < FLOOR_CLEARANCE):
            raise GateProgressError('gate-envelope')


def advance_directed_gates(progress, leg_index, before, after):
    """Return a fresh cursor or reject a gate event; never mutate prior state.

    leg_index must come from the independently validated route progression,
    NOT from a browser or AST. This function by itself cannot authorize that
    leg change, mission completion or a flight command.
    """
    if type(progress) is not DirectedGateProgress:
        raise GateProgressError('fresh gate cursor required')
    _point(before)
    _point(after)
    if (type(leg_index) is not int or leg_index not in (0, 1, 2) or
            leg_index < progress.active_leg or
            leg_index > progress.active_leg + 1):
        raise GateProgressError('non-monotonic or unproven leg transition')
    course = progress.course
    if (type(course) is not CoursePlan or
            type(progress.cursor) is not int or
            not 0 <= progress.cursor <= len(course.gates)):
        raise GateProgressError('invalid host cursor')
    # A previously counted H can never be crossed backwards on its own leg.
    for gate in course.gates[:progress.cursor]:
        if gate.leg_index == leg_index:
            prior_leg = course.route.legs[gate.leg_index]
            if _relative(gate, prior_leg, after)[0] < -CROSSING_PLANE:
                raise GateProgressError('reverse-crossing')
    if progress.cursor == len(course.gates):
        return replace(progress, active_leg=leg_index, armed=False, crossed=False)
    gate = course.gates[progress.cursor]
    if leg_index > gate.leg_index:
        raise GateProgressError('missed-gate')
    if leg_index < gate.leg_index:
        return replace(progress, active_leg=leg_index, armed=False, crossed=False)
    leg = course.route.legs[leg_index]
    start = _relative(gate, leg, before)[0]
    end = _relative(gate, leg, after)[0]
    if start >= CROSSING_PLANE and end < -CROSSING_PLANE:
        raise GateProgressError('reverse-crossing')
    _check_frame_sweep(gate, leg, before, after, start, end)
    armed = progress.armed or start <= -FRAME_CLEAR or end <= -FRAME_CLEAR
    crossed = progress.crossed
    if crossed and end < -CROSSING_PLANE:
        raise GateProgressError('reverse-crossing')
    if start < CROSSING_PLANE <= end:
        if not armed:
            raise GateProgressError('gate-not-armed')
        crossed = True
    if end >= FRAME_CLEAR:
        if not (armed and crossed):
            raise GateProgressError('missed-gate')
        return replace(progress, cursor=progress.cursor + 1,
                       active_leg=leg_index, armed=False, crossed=False)
    return replace(progress, active_leg=leg_index, armed=armed, crossed=crossed)
