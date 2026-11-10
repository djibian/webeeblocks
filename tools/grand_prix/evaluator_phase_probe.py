"""Opt-in, non-authoritative timing of the real evaluator per 8-ms tick.

The raw nanosecond samples are not aggregate FPS or proof of a faster engine.
Unknown/missing stages are absent, not silently converted to zero.
"""
from contextlib import contextmanager
import json
import time

PREFIX = 'GP_EVALUATOR_PHASE_V1 '


class EvaluatorPhaseProbe:
    def __init__(self, course, sink, window_steps=125):
        if not isinstance(course, str) or not course or not callable(sink):
            raise ValueError('course and sink required')
        if type(window_steps) is not int or not 1 <= window_steps <= 3750:
            raise ValueError('window_steps must be 1..3750')
        self.course = course
        self.sink = sink
        self.window_steps = window_steps
        self.sequence = 0
        self.rows = []
        self.opened = None
        self.durations = None

    def begin(self):
        if self.opened is not None:
            raise RuntimeError('overlapping evaluator ticks')
        self.opened = time.perf_counter_ns()
        self.durations = {}

    def record(self, name, duration_ns):
        if (self.durations is not None and isinstance(name, str) and
                type(duration_ns) is int and duration_ns >= 0):
            self.durations[name] = self.durations.get(name, 0) + duration_ns

    @contextmanager
    def phase(self, name):
        started = time.perf_counter_ns()
        try:
            yield
        finally:
            self.record(name, time.perf_counter_ns() - started)

    def end(self, sim_ms):
        if self.opened is None:
            raise RuntimeError('tick is not open')
        self.record('tick_total', time.perf_counter_ns() - self.opened)
        self.rows.append({'sim_ms': sim_ms, 'durations_ns': self.durations})
        self.opened = None
        self.durations = None
        if len(self.rows) >= self.window_steps:
            self.flush()

    def flush(self):
        if self.opened is not None:
            raise RuntimeError('cannot flush a running tick')
        if not self.rows:
            return
        payload = {'schema': 1, 'course': self.course,
                   'window': self.sequence, 'rows': self.rows}
        self.sink(PREFIX + json.dumps(payload, separators=(',', ':'), sort_keys=True))
        self.sequence += 1
        self.rows = []
