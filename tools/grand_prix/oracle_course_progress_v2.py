"""Pure host-only coupling of variable GP leg and directed-gate observations.

This helper has no native admission, RESET identity, mission-result or flight
authority. The independent evaluator must still verify actual pose/contact,
low-altitude windows, velocity, collision, landing and irreversible 210000 ms
LAND; never pass its CoursePlan into Blockly or the pupil AST.
"""
from dataclasses import dataclass
import math

from tools.grand_prix.oracle_gate_progress_v2 import (
    DirectedGateProgress, advance_directed_gates, start_directed_gates,
)
from tools.grand_prix.oracle_leg_cursor_v2 import (
    LegCursor, advance_leg_cursor, start_leg_cursor,
)
from tools.grand_prix.route_courses_v2 import CoursePlan


class CourseProgressError(ValueError):
    """Missing/contradictory host observation or uncompleted previous H."""


@dataclass(frozen=True)
class CoupledCourseProgress:
    course: CoursePlan
    leg: LegCursor
    gates: DirectedGateProgress
    pose: tuple[float, float, float]
    next_gates: DirectedGateProgress | None = None

    @property
    def count(self):
        return self.gates.count


def _finite_pose(value):
    if (not isinstance(value, (tuple, list)) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in value)):
        raise CourseProgressError('finite native XYZ observation required')
    return tuple(float(v) for v in value)


def start_course_progress(course, initial_z):
    """Pure initial state. The caller separately establishes RESET freshness."""
    if type(initial_z) not in (int, float) or not math.isfinite(initial_z):
        raise CourseProgressError('finite initial height required')
    leg = start_leg_cursor(course)
    gates = start_directed_gates(course)
    return CoupledCourseProgress(course, leg, gates,
                                 (leg.xy[0], leg.xy[1], float(initial_z)))


def advance_course_progress(state, observed_pose):
    """Advance both cursors atomically from one trusted host observation.

    The old leg consumes the full observed sweep before any promotion. The
    next leg may consume that same sweep ONLY after all previous-leg H are
    counted, preventing a route-only promotion from skipping an H. Upstream
    observations of its H inside the shared corner are retained separately:
    exclusive leg attribution must not discard a real arming observation.
    This witness cannot advance a count or justify promotion by itself.
    Neither the returned count nor active_leg is an outcome or actuator grant.
    """
    if (type(state) is not CoupledCourseProgress or
            type(state.leg) is not LegCursor or
            type(state.gates) is not DirectedGateProgress or
            type(state.course) is not CoursePlan):
        raise CourseProgressError('fresh coupled host state required')
    previous = _finite_pose(state.pose)
    if (state.leg.course != state.course or
            state.gates.course != state.course or
            state.leg.xy != previous[:2] or
            state.gates.active_leg != state.leg.active_leg or
            type(state.gates.cursor) is not int or
            not 0 <= state.gates.cursor <= len(state.course.gates) or
            type(state.leg.active_leg) is not int or
            state.leg.active_leg not in (0, 1, 2)):
        raise CourseProgressError('incoherent host cursors or sample')
    pending = state.next_gates
    if pending is not None:
        if (type(pending) is not DirectedGateProgress or
                pending.course != state.course or
                pending.active_leg != state.leg.active_leg + 1 or
                pending.cursor != state.gates.cursor or pending.crossed or
                type(pending.armed) is not bool or
                state.leg.active_leg >= 2):
            raise CourseProgressError('incoherent next-leg gate witness')
        box = state.course.route.legs[pending.active_leg].bounds()
        if not (box[0] <= previous[0] <= box[2] and box[1] <= previous[1] <= box[3]):
            raise CourseProgressError('next-leg witness outside shared junction')
    observed = _finite_pose(observed_pose)
    new_leg = advance_leg_cursor(state.leg, observed[:2])
    new_gates = advance_directed_gates(
        state.gates, state.leg.active_leg, previous, observed)
    if new_leg.active_leg != state.leg.active_leg:
        if any(g.leg_index <= state.leg.active_leg
               for g in state.course.gates[new_gates.count:]):
            raise CourseProgressError('uncompleted H before leg promotion')
        new_gates = advance_directed_gates(
            pending if pending is not None else new_gates,
            new_leg.active_leg, previous, observed)
        pending = None
    else:
        # A short terminal-leg H can have its upstream arming plane INSIDE
        # the shared corner. Keep the actual observation while the leg cursor
        # correctly waits for exclusive entry. Do not invent arm authority at
        # promotion, and never count a gate or promote a leg in this overlap.
        next_index = new_leg.active_leg + 1
        if next_index < 3:
            box = state.course.route.legs[next_index].bounds()
            in_next = box[0] <= observed[0] <= box[2] and box[1] <= observed[1] <= box[3]
        else:
            in_next = False
        if in_next and not any(g.leg_index <= new_leg.active_leg
                               for g in state.course.gates[new_gates.count:]):
            witness = advance_directed_gates(
                pending if pending is not None else new_gates,
                next_index, previous, observed)
            if witness.count != new_gates.count or witness.crossed:
                raise CourseProgressError('gate crossing before proven leg promotion')
            pending = witness
        else:
            pending = None
    return CoupledCourseProgress(state.course, new_leg, new_gates, observed, pending)
