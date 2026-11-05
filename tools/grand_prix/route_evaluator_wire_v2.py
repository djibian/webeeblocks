"""Strict host-only wire state for the variable Grand Prix native evaluator.

This is NOT an evaluator, native RESET attestation, scene verification or
flight authorization. Only a native Supervisor that has independently checked
the complete scene, devices, contacts, reset and observation freshness may
supply native_validated=True. No pupil/UI input may supply that assertion.
"""
from dataclasses import dataclass
import re

from tools.grand_prix.route_courses_v2 import course_from_identifier

_CONFIG = r"(?P<config>gp-route-v2-[A-Za-z0-9-]+)"
_NUMBER = r"(0|[1-9][0-9]*)"
_CHALLENGE = re.compile(
    r"GP_ROUTE_CHALLENGE_V1 attempt=(?P<attempt>[1-9][0-9]*) config="
    + _CONFIG + r" epoch=(?P<epoch>[0-9a-f]{32})", re.ASCII)
_START = re.compile(
    r"GP_ROUTE_START_V1 attempt=(?P<attempt>[1-9][0-9]*) config="
    + _CONFIG + r" epoch=(?P<epoch>[0-9a-f]{32})"
    r" start_ms=(?P<start>0|[1-9][0-9]*)"
    r" state=(?P<state>admitted|failed|deadline)", re.ASCII)
_MAX_ATTEMPT = (1 << 64) - 1
_MAX_TIME_MS = 10**15


@dataclass(frozen=True)
class Challenge:
    attempt: int
    config: str
    epoch: str


@dataclass(frozen=True)
class Start:
    challenge: Challenge
    start_ms: int
    state: str


def parse_flight_channel(raw, expected_config):
    """Reject aliases, overflow, malformed and cross-configuration messages.

    Empty means no request. Nonempty malformed content is an error, never an
    implied READY. Verify the ID by reconstructing CoursePlan, not by prefix.
    """
    if (type(expected_config) is not str or
            course_from_identifier(expected_config).identifier != expected_config):
        raise ValueError("expected canonical CoursePlan required")
    if type(raw) is not str or len(raw) > 383:
        raise ValueError("invalid native flight wire")
    if raw == "":
        return None
    kind = _CHALLENGE.fullmatch(raw)
    if kind is not None:
        start = False
    else:
        kind = _START.fullmatch(raw)
        start = True
    if kind is None:
        raise ValueError("unknown or malformed native flight wire")
    values = kind.groupdict()
    if values["config"] != expected_config:
        raise ValueError("native course identity mismatch")
    attempt = int(values["attempt"])
    if not 1 <= attempt <= _MAX_ATTEMPT:
        raise ValueError("noncanonical native attempt")
    challenge = Challenge(attempt, expected_config, values["epoch"])
    if not start:
        return challenge
    start_ms = int(values["start"])
    if start_ms > _MAX_TIME_MS:
        raise ValueError("invalid native start timestamp")
    return Start(challenge, start_ms, values["state"])


class EvaluatorHandshake:
    """Fail-closed single-writer description channel, with exact fresh epochs.

    The native evaluator owns description exclusively; the flight owns
    customData exclusively. The caller must independently prove native scene,
    reset, devices, fresh pose/contact and source provenance BEFORE each
    native_validated=True call. This pure state machine cannot prove them.
    """

    def __init__(self, course_identifier):
        self.course = course_from_identifier(course_identifier)
        self._last_time = None
        self._clear()

    def _clear(self):
        self._challenge = None
        self._challenge_at = None
        self._started_at = None
        self._last_alive = None

    def observe(self, raw, now_ms, *, native_validated=False):
        """Return READY/ALIVE or empty; never return a fabricated success.

        No response after broken monotonic time, a missing verification,
        malformed message, mismatched epoch, failed/deadline START or staleness.
        READY alone never constitutes a mission result. The C++ flight guard
        additionally checks freshness <=32 ms and strict ALIVE progression.
        """
        if (type(now_ms) is not int or not 0 <= now_ms <= _MAX_TIME_MS or
                native_validated is not True):
            self._clear()
            return ""
        if self._last_time is not None and now_ms <= self._last_time:
            self._clear()
            self._last_time = now_ms
            return ""
        self._last_time = now_ms
        try:
            event = parse_flight_channel(raw, self.course.identifier)
        except ValueError:
            self._clear()
            return ""
        if isinstance(event, Challenge):
            if event != self._challenge:
                self._challenge = event
                self._challenge_at = now_ms
                self._started_at = None
                self._last_alive = None
            if self._started_at is not None:
                self._clear()
                return ""
            return (f"GP_ROUTE_READY_V1 attempt={event.attempt} "
                    f"config={event.config} epoch={event.epoch} time_ms={now_ms}")
        if isinstance(event, Start):
            if event.state != "admitted" or event.challenge != self._challenge:
                self._clear()
                return ""
            if self._started_at is None:
                if (self._challenge_at is None or event.start_ms < self._challenge_at
                        or not event.start_ms <= now_ms <= event.start_ms + 32):
                    self._clear()
                    return ""
                self._started_at = event.start_ms
            elif event.start_ms != self._started_at:
                self._clear()
                return ""
            if now_ms <= self._started_at or (
                    self._last_alive is not None and now_ms <= self._last_alive):
                return ""
            self._last_alive = now_ms
            return (f"GP_ROUTE_ALIVE_V1 attempt={event.challenge.attempt} "
                    f"config={event.challenge.config} epoch={event.challenge.epoch} "
                    f"time_ms={now_ms}")
        self._clear()
        return ""
