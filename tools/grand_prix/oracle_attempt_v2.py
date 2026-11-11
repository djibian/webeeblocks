"""Pure, fail-closed variable Grand Prix attempt composition (no native READY).

Combines existing geometric, directed-gate, low-flight and terminal-dwell
oracles around a single host-owned observation. Not a Webots evaluator, reset
attestation, deadline actuator, launch permission or pedagogical PASS: a native
controller must independently enforce admission, samples and 210000-ms LAND.
"""
from dataclasses import dataclass, replace
import math
from types import SimpleNamespace

from tools.grand_prix.native_collider_contract_v2 import canonical_native_boxes
from tools.grand_prix.oracle_course_progress_v2 import (
    CourseProgressError, advance_course_progress, start_course_progress,
)
from tools.grand_prix.oracle_gate_progress_v2 import GateProgressError
from tools.grand_prix.oracle_leg_cursor_v2 import LegCursorError
from tools.grand_prix.oracle_low_v2 import low_segment_allowed_v2
from tools.grand_prix.oracle_terminal_dwell_v2 import (
    TerminalDwellError, advance_terminal_dwell, start_terminal_dwell,
)
from tools.grand_prix.oracle_u import DEADLINE_MS, RADIUS, swept_gap
from tools.grand_prix.route_courses_v2 import CoursePlan


@dataclass(frozen=True)
class PureResult:
    status: str
    configuration: str
    attempt: int
    elapsed_ms: int
    reason: str | None
    crossings: int


@dataclass(frozen=True)
class PureAttempt:
    course: CoursePlan
    attempt: int
    origin_z: float
    started_ms: int
    last_ms: int
    progress: object
    terminal: object
    boxes: tuple
    airborne: bool = False
    takeoff_done: bool = False
    result: PureResult | None = None


def start_pure_attempt(course, attempt, origin_z, now_ms):
    """Bind one fresh canonical route and monotonic native simulation epoch."""
    if (type(attempt) is not int or attempt < 1 or
            type(now_ms) is not int or now_ms < 0 or
            type(origin_z) not in (int, float) or not math.isfinite(origin_z)):
        raise ValueError('canonical attempt identity/clock/origin required')
    progress = start_course_progress(course, float(origin_z))
    terminal = start_terminal_dwell(course, attempt, origin_z, now_ms)
    return PureAttempt(course, attempt, float(origin_z), now_ms, now_ms,
                       progress, terminal, canonical_native_boxes(course))


def _end(state, now_ms, reason):
    if state.result is not None:
        return state
    return replace(state, result=PureResult(
        'not-achieved', state.course.identifier, state.attempt,
        max(0, now_ms - state.started_ms), reason, state.progress.count))


def fail_pure_attempt(state, now_ms, reason):
    """Latch a host-only failure. No physical LAND command is issued here."""
    if type(state) is not PureAttempt:
        raise ValueError('valid pure attempt required')
    if state.result is not None:
        return state
    if (type(now_ms) is not int or now_ms < state.last_ms or
            type(reason) is not str or not reason or len(reason) > 128):
        raise ValueError('monotonic failure observation and reason required')
    return _end(state, now_ms, reason)


def _xyz(value):
    if (not isinstance(value, (tuple, list)) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in value)):
        raise ValueError('finite native xyz required')
    return tuple(float(v) for v in value)


def _valid_contacts(contacts):
    if not isinstance(contacts, (tuple, list)) or len(contacts) > 64:
        return False
    try:
        return all(_xyz(c)[2] <= .012 for c in contacts)
    except ValueError:
        return False


def _hits_mission_body(before, after, boxes):
    """Continuous capsule against the full canonical native physical inventory."""
    for box in boxes:
        x, y, z = box.position
        sx, sy, sz = box.size
        collider = SimpleNamespace(x=x, y=y, z=z, sx=sx, sy=sy, sz=sz)
        if swept_gap(before, after, collider) < RADIUS:
            return True
    return False


def observe_pure_attempt(state, attempt, now_ms, pose, velocity,
                         *, contacts=None, completed=False):
    """Consume one independently sourced observation; latch failure or success.

    A missing contact observation fails closed; the caller must explicitly
    supply the native contact snapshot, including an observed empty one.
    Geometry checked here never creates evaluator readiness or a native motion
    command. The real evaluator must additionally attest RESET, contact/sensor
    provenance, observation cadence, command outcome and independent LAND.
    """
    if type(state) is not PureAttempt:
        raise ValueError('valid pure attempt required')
    if state.result is not None:
        return state
    if (type(attempt) is not int or attempt != state.attempt or
            type(now_ms) is not int or now_ms <= state.last_ms or
            type(completed) is not bool):
        return _end(state, state.last_ms, 'invalid-attempt-clock')
    if now_ms - state.started_ms >= DEADLINE_MS:
        return _end(state, now_ms, 'time-limit')
    try:
        observed = _xyz(pose)
        speed = _xyz(velocity)
    except ValueError:
        return _end(state, now_ms, 'invalid-sample')
    if not _valid_contacts(contacts):
        return _end(state, now_ms, 'device-contact')
    before = state.progress.pose
    if math.dist(observed, before) > max(.06, (now_ms - state.last_ms) / 500):
        return _end(state, now_ms, 'sample-displacement')
    if observed[2] < state.origin_z - .02 or observed[2] > state.origin_z + 1.15:
        return _end(state, now_ms, 'altitude')
    # The same full-course swept radius oracle used for leg advancement is
    # checked before any count, completion or terminal-state update.
    try:
        if _hits_mission_body(before, observed, state.boxes):
            return _end(state, now_ms, 'envelope-contact')
        dt = now_ms - state.last_ms
        until = None
        if not state.takeoff_done:
            remaining = state.started_ms + 15000 - state.last_ms
            until = remaining / dt if dt else (1. if remaining >= 0 else -1.)
        if not low_segment_allowed_v2(
                before, observed, state.course.route, state.course.gates,
                # The terminal low-flight exception is earned only after
                # every directed H has been counted, not on leg-3 entry alone.
                final=(state.progress.leg.active_leg == 2 and
                       state.progress.count == state.course.count),
                takeoff_until=until):
            return _end(state, now_ms, 'low-outside-zone')
        progress = advance_course_progress(state.progress, observed)
        airborne = state.airborne or observed[2] > state.origin_z + .20
        terminal = advance_terminal_dwell(
            state.terminal, state.attempt, now_ms, progress, speed,
            airborne=airborne, completed=completed)
    except LegCursorError as error:
        # Only the precise swept-boundary witness proves an off-course flight.
        # Other cursor/progression exceptions remain non-diagnostic.
        return _end(state, now_ms, 'course-boundary'
                    if str(error) == 'swept-course-boundary'
                    else 'invalid-route-observation')
    except (CourseProgressError, GateProgressError,
            TerminalDwellError, ValueError, TypeError):
        return _end(state, now_ms, 'invalid-route-observation')
    start = state.course.route.legs[0].start
    takeoff_done = (state.takeoff_done or
                    math.dist(observed[:2], start) > .14 or
                    now_ms - state.started_ms > 15000)
    new_state = replace(state, last_ms=now_ms, progress=progress,
                        terminal=terminal, airborne=airborne,
                        takeoff_done=takeoff_done)
    if terminal.state == 'expired-window':
        return _end(new_state, now_ms, 'wrong-landing')
    if terminal.state == 'stable-window':
        return replace(new_state, result=PureResult(
            'achieved', state.course.identifier, state.attempt,
            now_ms - state.started_ms, None, progress.count))
    return new_state
