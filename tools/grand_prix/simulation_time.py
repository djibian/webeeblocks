"""Exact elapsed milliseconds from the Webots simulation-time interface.

The supported controller clock is millisecond-granular (32 ms basic step).
Reject unsupported timestamps. Floating representation error at the interface
must not create an extra started second; no real delay is subtracted.
"""
import math


def milliseconds(seconds):
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or
            not math.isfinite(seconds) or seconds < 0):
        raise ValueError('invalid simulation timestamp')
    scaled = seconds * 1000
    if not math.isfinite(scaled) or math.ulp(scaled) >= .125:
        raise ValueError('unsupported simulation timestamp resolution')
    whole = round(scaled)
    # Only the floating encoding error of an integer-millisecond timestamp is
    # admissible. This is not a tolerance at a scoring/deadline boundary.
    if abs(scaled - whole) > 4 * math.ulp(scaled):
        raise ValueError('simulation timestamp is not millisecond-granular')
    return whole


def elapsed_seconds(start, end):
    duration = milliseconds(end) - milliseconds(start)
    if duration < 0:
        raise ValueError('simulation clock moved backwards')
    return duration / 1000
