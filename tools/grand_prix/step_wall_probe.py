"""Opt-in, non-authoritative wall-time observer for the native Grand Prix evaluator.

This module never controls or reads mission authority. Each JSON line retains
raw monotonic durations so offline A/B statistics can be recomputed. It does
not measure graphical FPS or itself establish GUI/Windows qualification.
"""
import json
import math

PREFIX = 'GP_STEP_WALL_V1 '
STEP_MS = 8


def _percentile(values, percent):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)]


class StepWallProbe:
    def __init__(self, course_id, sink, window_steps=125):
        if not isinstance(course_id, str) or not course_id or not callable(sink):
            raise ValueError('course and sink required')
        if type(window_steps) is not int or not 1 <= window_steps <= 3750:
            raise ValueError('window_steps must be 1..3750')
        self.course_id = course_id
        self.sink = sink
        self.window_steps = window_steps
        self.sequence = 0
        self.reset()

    def reset(self):
        self.records = []
        self.first_ms = None
        self.last_ms = None

    def record(self, simulated_seconds, start_ns, step_end_ns, tick_end_ns):
        if (not isinstance(simulated_seconds, (float, int)) or
                not math.isfinite(simulated_seconds) or simulated_seconds < 0):
            raise ValueError('invalid simulator clock')
        time_ms = round(simulated_seconds * 1000)
        if abs(simulated_seconds * 1000 - time_ms) > 1e-5 or time_ms % STEP_MS:
            raise ValueError('simulator clock is not an 8ms physical boundary')
        if any(type(v) is not int for v in (start_ns, step_end_ns, tick_end_ns)):
            raise ValueError('monotonic ns required')
        if not 0 <= start_ns <= step_end_ns <= tick_end_ns:
            raise ValueError('invalid monotonic time ordering')
        if self.last_ms is not None and time_ms != self.last_ms + STEP_MS:
            self.flush('clock-discontinuity')
        if self.records and start_ns < self.records[-1][2]:
            raise ValueError('wall clock reversed')
        if not self.records:
            self.first_ms = time_ms
        self.records.append((start_ns, step_end_ns, tick_end_ns))
        self.last_ms = time_ms
        if len(self.records) >= self.window_steps:
            self.flush('complete')

    def flush(self, reason='partial'):
        if not self.records:
            return
        steps = [v[1] - v[0] for v in self.records]
        ticks = [v[2] - v[1] for v in self.records]
        wall_ns = self.records[-1][2] - self.records[0][0]
        if wall_ns <= 0:
            raise ValueError('non-positive wall-time interval')
        n = len(self.records)
        payload = {
            'schema': 1, 'course': self.course_id, 'window': self.sequence,
            'reason': reason, 'start_sim_ms': self.first_ms,
            'end_sim_ms': self.last_ms, 'simulated_ms': n * STEP_MS,
            'wall_ns': wall_ns,
            'first_start_wall_ns': self.records[0][0],
            'last_end_wall_ns': self.records[-1][2],
            'speed_x': round(n * STEP_MS * 1e6 / wall_ns, 6),
            'count': n, 'step_ns': steps, 'tick_ns': ticks,
            'step_p50_ns': _percentile(steps, 50),
            'step_p95_ns': _percentile(steps, 95),
            'step_p99_ns': _percentile(steps, 99),
            'step_max_ns': max(steps),
            'tick_p99_ns': _percentile(ticks, 99),
        }
        self.sink(PREFIX + json.dumps(payload, sort_keys=True, separators=(',', ':')))
        self.sequence += 1
        self.reset()
