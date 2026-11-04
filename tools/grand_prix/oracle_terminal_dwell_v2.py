"""Pure terminal landing dwell evidence for variable Grand Prix routes (#811).

Host-only, non-authoritative input: the native evaluator must independently
attest every observation, contact, velocity, RESET/attempt provenance, clock,
continuous swept geometry, H crossing, altitude and the irreversible 210000-ms
LAND/failure boundary. A stable-window observation is NOT mission success.
The student AST and Blockly must never receive CoursePlan or landing targets.
"""
from dataclasses import dataclass, replace
import math

from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier
from tools.grand_prix.oracle_course_progress_v2 import CoupledCourseProgress
from tools.grand_prix.oracle_gate_progress_v2 import DirectedGateProgress
from tools.grand_prix.oracle_leg_cursor_v2 import LegCursor

LANDING_TOL = .14
DWELL_MS = 500
COMPLETION_WINDOW_MS = 1500


class TerminalDwellError(ValueError):
    """Invalid attempt identity, host evidence or elapsed observation."""


@dataclass(frozen=True)
class TerminalDwell:
    course: CoursePlan
    attempt: int
    origin_z: float
    last_ms: int
    completion_ms: int | None = None
    stationary_since_ms: int | None = None
    state: str = 'open'


def _canonical(course):
    if type(course) is not CoursePlan:
        raise TerminalDwellError('canonical host CoursePlan required')
    try:
        if course_from_identifier(course.identifier) != course:
            raise TerminalDwellError('forged CoursePlan')
    except (TypeError, ValueError, AttributeError) as error:
        raise TerminalDwellError('forged CoursePlan') from error
    return course


def _finite_xyz(value, name):
    if (not isinstance(value, (tuple, list)) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in value)):
        raise TerminalDwellError('finite native ' + name + ' required')
    return tuple(float(v) for v in value)


def start_terminal_dwell(course, attempt, origin_z, start_ms):
    """Create attempt-scoped pure observation state, never a RESET grant."""
    _canonical(course)
    if (type(attempt) is not int or attempt < 1 or
            type(origin_z) not in (int, float) or not math.isfinite(origin_z) or
            type(start_ms) is not int or start_ms < 0):
        raise TerminalDwellError('valid attempt, origin and clock required')
    return TerminalDwell(course, attempt, float(origin_z), start_ms)


def _eligible(state, progress, velocity, airborne):
    pose = _finite_xyz(progress.pose, 'position')
    speed = _finite_xyz(velocity, 'velocity')
    if (progress.leg.course != state.course or
            progress.gates.course != state.course or
            progress.leg.active_leg != progress.gates.active_leg or
            progress.leg.xy != pose[:2] or
            type(progress.leg.active_leg) is not int or
            progress.leg.active_leg not in (0, 1, 2) or
            type(progress.gates.cursor) is not int or
            not 0 <= progress.gates.cursor <= state.course.count):
        raise TerminalDwellError('incoherent native course progression')
    target = state.course.route.landing_target(state.course.count)
    return (airborne and progress.leg.active_leg == 2 and
            progress.gates.cursor == state.course.count and
            state.origin_z - .02 <= pose[2] <= state.origin_z + .07 and
            abs(pose[0] - target[0]) <= LANDING_TOL and
            abs(pose[1] - target[1]) <= LANDING_TOL and
            math.hypot(speed[0], speed[1]) <= .12 and
            abs(speed[2]) <= .12)


def advance_terminal_dwell(state, attempt, now_ms, progress, velocity,
                           *, airborne, completed):
    """Observe a host sample; never signal mission achieved or command LAND.

    Only the *first* trusted completion begins the 1500-ms window. Evidence
    must remain eligible for 500 consecutive simulation milliseconds; a
    discontinuity resets that dwell. Expiration is irreversible even if a
    subsequent pose would be eligible. The outer native evaluator remains
    responsible for deadline and all independent safety checks.
    """
    if (type(state) is not TerminalDwell or
            type(state.attempt) is not int or state.attempt < 1 or
            type(state.last_ms) is not int or state.last_ms < 0 or
            type(state.origin_z) is not float or
            not math.isfinite(state.origin_z) or
            type(attempt) is not int or attempt != state.attempt or
            type(now_ms) is not int or now_ms < state.last_ms or
            type(airborne) is not bool or type(completed) is not bool or
            state.state not in ('open', 'stable-window', 'expired-window') or
            type(progress) is not CoupledCourseProgress or
            type(progress.leg) is not LegCursor or
            type(progress.gates) is not DirectedGateProgress or
            progress.course != state.course):
        raise TerminalDwellError('fresh consistent host landing observation required')
    _canonical(state.course)
    eligible = _eligible(state, progress, velocity, airborne)
    if state.state != 'open':
        return state
    completion = state.completion_ms
    if completion is not None and (type(completion) is not int or
                                   completion > state.last_ms):
        raise TerminalDwellError('invalid completion timestamp')
    if completion is None:
        completion = now_ms if completed else None
    if completion is None:
        return replace(state, last_ms=now_ms, stationary_since_ms=None)
    since = state.stationary_since_ms if eligible else None
    if eligible and since is None:
        since = now_ms
    if since is not None and (type(since) is not int or
                              since < completion or since > now_ms):
        raise TerminalDwellError('invalid stationary timestamp')
    observed = ('stable-window' if since is not None and now_ms - since >= DWELL_MS
                else 'expired-window' if now_ms - completion >= COMPLETION_WINDOW_MS
                else 'open')
    return replace(state, last_ms=now_ms, completion_ms=completion,
                   stationary_since_ms=since, state=observed)
