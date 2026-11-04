"""Pure host-only observed-segment cursor for the variable Grand Prix (#811).

Do not treat this as a mission oracle, segment transition permission from the
pupil, or readiness. The native evaluator alone owns pose provenance, gate
completion, collision/contact, speed, altitude, RESET and 210000-ms LAND.
This cursor only proves that each XY observation has a continuous radius-aware
footprint and belongs to the current or immediately following route corridor.
"""
from dataclasses import dataclass, replace
import math

from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier
from tools.grand_prix.course_footprint_v2 import swept_capsule_inside_course


class LegCursorError(ValueError):
    """A route observation cannot justify the proposed segment progression."""


@dataclass(frozen=True)
class LegCursor:
    course: CoursePlan
    active_leg: int
    xy: tuple[float, float]


def _canonical(course):
    if type(course) is not CoursePlan:
        raise LegCursorError('canonical host CoursePlan required')
    try:
        if course_from_identifier(course.identifier) != course:
            raise LegCursorError('forged CoursePlan')
    except (TypeError, ValueError, AttributeError) as error:
        raise LegCursorError('forged CoursePlan') from error
    return course


def _xy(value):
    if (not isinstance(value, (tuple, list)) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in value)):
        raise LegCursorError('finite native XY required')
    return tuple(float(v) for v in value)


def _in_box(box, p):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def start_leg_cursor(course):
    """Start at the canonical route origin; no start/RESET admission granted."""
    course = _canonical(course)
    return LegCursor(course, 0, tuple(course.route.legs[0].start))


def advance_leg_cursor(cursor, observed_xy):
    """Observe one native sample; return an immutable cursor or refuse it.

    A segment is promoted only on **exclusive** entry into the next corridor:
    while the craft is still in the common corner overlap its attribution is
    deliberately unchanged. A return into that overlap is allowed, but not
    a retreat into an already completed corridor's exclusive region. Full
    swept containment rejects concave chords and non-physical shortcuts even
    when both endpoints are inside the course. The caller must separately
    prove gate completion *before* accepting any promotion, and must verify
    the native sensor/sample and velocity limits. This function cannot do so.
    """
    if type(cursor) is not LegCursor or type(cursor.active_leg) is not int or not 0 <= cursor.active_leg <= 2:
        raise LegCursorError('valid host segment cursor required')
    _canonical(cursor.course)
    previous, current = _xy(cursor.xy), _xy(observed_xy)
    route = cursor.course.route
    if not swept_capsule_inside_course(route, previous, current):
        raise LegCursorError('swept-course-boundary')
    active = cursor.active_leg
    if _in_box(route.legs[active].bounds(), current):
        return replace(cursor, xy=current)
    if active == 2:
        # The terminal pad is wider than the final 0.60 m corridor. It is not
        # a fourth segment; the complete swept footprint is checked above.
        from tools.grand_prix.course_footprint_v2 import course_rectangles
        if _in_box(course_rectangles(route)[3], current):
            return replace(cursor, xy=current)
        raise LegCursorError('backtrack or unowned terminal position')
    if not _in_box(route.legs[active + 1].bounds(), current):
        raise LegCursorError('skipped or reversed segment')
    # With cardinal equal-width corridors, the next-only region is strictly
    # beyond the shared corner overlap. A bogus pose in a non-adjacent leg
    # cannot advance the cursor, even if it is somewhere inside the course.
    return replace(cursor, active_leg=active + 1, xy=current)
