"""Host-only composition of variable-route and directed-H observations.

This composes two independent pure validators without making either a mission
oracle. It grants no native sample provenance, speed, altitude, contact, landing,
RESET, attempt READY or independent 210000-ms LAND authority. Never expose
CoursePlan or these cursors to the pupil AST / Blockly environment.
"""
from dataclasses import dataclass, replace
import math

from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier
from tools.grand_prix.oracle_leg_cursor_v2 import (
    LegCursor, start_leg_cursor, advance_leg_cursor,
)
from tools.grand_prix.oracle_gate_progress_v2 import (
    DirectedGateProgress, start_directed_gates, advance_directed_gates,
)

START_RADIUS = 0.14


class CourseProgressError(ValueError):
    """Host progression state or sample provenance precondition is invalid."""


@dataclass(frozen=True)
class ObservedCourseProgress:
    course: CoursePlan
    leg: LegCursor
    gates: DirectedGateProgress
    xyz: tuple[float, float, float]

    @property
    def count(self):
        return self.gates.count


def _canonical(course):
    if type(course) is not CoursePlan:
        raise CourseProgressError('canonical CoursePlan required')
    try:
        if course_from_identifier(course.identifier) != course:
            raise CourseProgressError('forged CoursePlan')
    except (TypeError, ValueError, AttributeError) as exc:
        raise CourseProgressError('canonical CoursePlan required') from exc


def _xyz(point):
    if (type(point) not in (tuple, list) or len(point) != 3 or
            any(type(x) not in (float, int) or not math.isfinite(x)
                for x in point)):
        raise CourseProgressError('finite host-owned XYZ required')
    return tuple(float(x) for x in point)


def start_observed_course(course, observed_xyz):
    """Bind both immutable cursors to one host course and observed start pose.

    The caller must establish the actual native sample and RESET freshness.
    This host-only 0.14-m start envelope is necessary, never sufficient, for
    mission admission. The Z coordinate is only retained for later H checks.
    """
    _canonical(course)
    xyz = _xyz(observed_xyz)
    origin = course.route.legs[0].start
    if math.dist(xyz[:2], origin) > START_RADIUS:
        raise CourseProgressError('outside start disc')
    leg = advance_leg_cursor(start_leg_cursor(course), xyz[:2])
    if leg.active_leg != 0:
        raise CourseProgressError('start leg not established')
    gates = start_directed_gates(course)
    return ObservedCourseProgress(course, leg, gates, xyz)


def advance_observed_course(progress, observed_xyz):
    """Atomically validate an ordered pair of host observations.

    Leg promotion is derived from the swept craft footprint, not asserted by
    a pupil, then passed into directed-H validation. A gate left uncounted on
    a completed leg therefore rejects the transition; any failure returns
    no updated state. Native collision, sampling interval, speed, low flight,
    terminal landing and clock obligations remain separate and mandatory.
    """
    if (type(progress) is not ObservedCourseProgress or
            type(progress.leg) is not LegCursor or
            type(progress.gates) is not DirectedGateProgress):
        raise CourseProgressError('bound host progress state required')
    _canonical(progress.course)
    if (progress.leg.course != progress.course or
            progress.gates.course != progress.course or
            progress.leg.xy != progress.xyz[:2] or
            progress.leg.active_leg != progress.gates.active_leg):
        raise CourseProgressError('inconsistent leg/gate observation binding')
    before = _xyz(progress.xyz)
    after = _xyz(observed_xyz)
    leg = advance_leg_cursor(progress.leg, after[:2])
    gates = advance_directed_gates(progress.gates, leg.active_leg, before, after)
    return replace(progress, leg=leg, gates=gates, xyz=after)
