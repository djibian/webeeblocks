"""Decode flight-owned native samples; data only, never READY or RESET authority.

Read GP_ROUTE_EVALUATOR.model, written only by the flight controller, after
independently verifying both Robots' identities/controllers/scene. The evaluator
cannot use its own devices as a substitute. A caller's string is not provenance.
"""
from dataclasses import dataclass
import re

from tools.grand_prix.route_courses_v2 import course_from_identifier
from tools.grand_prix.route_evaluator_wire_v2 import Challenge, Start

OBSERVATION_FIELD = 'model'  # Plain GP_ROUTE_EVALUATOR Robot; flight is the only writer.

_SAMPLE = re.compile(
    r'GP_ROUTE_SAMPLE_V1 attempt=(?P<attempt>[1-9][0-9]*) '
    r'config=(?P<config>gp-route-v2-[A-Za-z0-9-]+) '
    r'epoch=(?P<epoch>[0-9a-f]{32}) time_ms=(?P<time>0|[1-9][0-9]*) '
    r'period_ms=32 ground=(?P<ground>[01]) ranges_um='
    + ','.join(fr'(?P<r{i}>0|[1-9][0-9]*)' for i in range(5)), re.ASCII)


@dataclass(frozen=True)
class FlightObservation:
    challenge: Challenge
    time_ms: int
    ground_confirmed: bool
    # Native sensor order, never configuration/route information for Blockly.
    ranges_m: tuple[float, float, float, float, float]
    sensor_period_ms: int = 32


def parse_flight_observation(raw, flight_event, now_ms):
    """Require same context and native observation age in [0, 32] ms.

    The same sample may remain fresh across the evaluator's 8-ms observations;
    its timestamp cannot be refreshed by receipt. Devices update every 32 ms;
    Webots exposes no individual acquisition timestamp. Measurement age is
    conservatively bounded by observation age plus this native period (<=64 ms),
    including a controller restart or the off-phase tick after exact expiry.
    Missing/malformed/stale evidence raises ValueError, never an empty success.
    """
    if (type(raw) is not str or len(raw) > 383 or type(now_ms) is not int or
            not 0 <= now_ms <= 10**15):
        raise ValueError('invalid native observation input')
    if type(flight_event) is Start:
        if (flight_event.state != 'admitted' or
                type(flight_event.start_ms) is not int or
                not 0 <= flight_event.start_ms <= now_ms):
            raise ValueError('inactive flight observation context')
        expected = flight_event.challenge
    elif type(flight_event) is Challenge:
        expected = flight_event
    else:
        raise ValueError('parsed flight context required')
    if (type(expected) is not Challenge or type(expected.attempt) is not int or
            not 1 <= expected.attempt < 2**64 or
            type(expected.config) is not str or
            course_from_identifier(expected.config).identifier != expected.config or
            type(expected.epoch) is not str or
            re.fullmatch('[0-9a-f]{32}', expected.epoch, re.ASCII) is None):
        raise ValueError('canonical flight observation context required')
    match = _SAMPLE.fullmatch(raw)
    if match is None:
        raise ValueError('missing or malformed flight observation')
    values = match.groupdict()
    if (int(values['attempt']) != expected.attempt or
            values['config'] != expected.config or values['epoch'] != expected.epoch):
        raise ValueError('flight observation identity mismatch')
    stamp = int(values['time'])
    if (stamp % 8 or not 0 <= now_ms - stamp <= 32 or
            (type(flight_event) is Start and stamp < flight_event.start_ms)):
        raise ValueError('stale/future/off-grid flight observation')
    ranges = tuple(int(values[f'r{i}']) for i in range(5))
    if any(v > 2001000 for v in ranges):
        raise ValueError('unavailable native range observation')
    return FlightObservation(expected, stamp, values['ground'] == '1',
                             tuple(v / 1000000 for v in ranges))
