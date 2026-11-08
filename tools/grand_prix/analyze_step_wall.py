#!/usr/bin/env python3
"""Audit one continuous Grand Prix 8-ms phase from raw evaluator wall-time logs.

This is a measurement-only diagnostic for #912/#914. It cannot establish the
actual displayed FPS, GPU acceleration, student UI latency or human acceptance.
"""

import argparse
import json
import math
from pathlib import Path
import sys

PREFIX = 'GP_STEP_WALL_V1 '
STEP_MS = 8


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * fraction) - 1]


def parse_windows(lines):
    """Strictly validate native evaluator output; never silently skip corrupt samples."""
    windows = []
    for line_number, line in enumerate(lines, 1):
        index = line.find(PREFIX)
        if index < 0:
            continue  # Other Webots log lines are not observations.
        try:
            row = json.loads(line[index + len(PREFIX):])
            if not isinstance(row, dict) or row.get('schema') != 1:
                raise ValueError('invalid schema')
            if not isinstance(row.get('course'), str) or not row['course']:
                raise ValueError('missing course')
            for field in ('window', 'count', 'start_sim_ms', 'end_sim_ms',
                          'simulated_ms', 'wall_ns', 'first_start_wall_ns', 'last_end_wall_ns'):
                if type(row.get(field)) is not int:
                    raise ValueError(f'invalid {field}')
            steps, ticks = row.get('step_ns'), row.get('tick_ns')
            if not isinstance(steps, list) or not isinstance(ticks, list):
                raise ValueError('missing raw durations')
            n = row['count']
            if n < 1 or len(steps) != n or len(ticks) != n or any(
                    type(v) is not int or v < 0 for v in steps + ticks):
                raise ValueError('invalid step/tick arrays')
            if (row['window'] < 0 or row['reason'] not in ('complete', 'partial', 'clock-discontinuity') or
                    row['simulated_ms'] != n * STEP_MS or
                    row['end_sim_ms'] - row['start_sim_ms'] != (n - 1) * STEP_MS or
                    row['start_sim_ms'] < 0 or row['start_sim_ms'] % STEP_MS or
                    row['wall_ns'] != row['last_end_wall_ns'] - row['first_start_wall_ns'] or
                    row['wall_ns'] <= 0):
                raise ValueError('inconsistent window bounds')
            # The native StepWallProbe emits a complete window only after 125 steps.
            if row['reason'] == 'complete' and n != 125:
                raise ValueError('non-native complete window size')
            # Each step and tick interval is monotone and non-overlapping by
            # construction of StepWallProbe.record(). The enclosing wall span
            # must never be shorter than their sum, even in a forged log.
            if (row['first_start_wall_ns'] < 0 or row['last_end_wall_ns'] < 0 or
                    sum(steps) + sum(ticks) > row['wall_ns']):
                raise ValueError('impossible wall duration for raw steps/ticks')
            if (row.get('step_p99_ns') != percentile(steps, .99) or
                    row.get('step_max_ns') != max(steps) or
                    row.get('tick_p99_ns') != percentile(ticks, .99)):
                raise ValueError('inconsistent raw percentiles')
            windows.append(row)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f'bad measurement at log line {line_number}: {error}') from error
    if not windows:
        raise ValueError('no GP_STEP_WALL_V1 windows in log')
    return windows


def analyze(windows, course, start_ms, end_ms, minimum_sim_ms=30000):
    if not course or type(start_ms) is not int or start_ms < 0 or start_ms % STEP_MS or (
            end_ms is not None and (type(end_ms) is not int or end_ms < start_ms or end_ms % STEP_MS)):
        raise ValueError('invalid course or 8-ms-aligned phase boundaries')
    if type(minimum_sim_ms) is not int or minimum_sim_ms < STEP_MS:
        raise ValueError('invalid minimum duration')
    selected = [w for w in windows if w['start_sim_ms'] >= start_ms and
                (end_ms is None or w['end_sim_ms'] <= end_ms)]
    if not selected:
        raise ValueError('no complete windows within phase')
    if any(w['course'] != course for w in selected):
        raise ValueError('mixed course IDs in selected phase')
    for prev, row in zip(selected, selected[1:]):
        if (row['window'] != prev['window'] + 1 or
                row['start_sim_ms'] != prev['end_sim_ms'] + STEP_MS or
                row['first_start_wall_ns'] < prev['last_end_wall_ns']):
            raise ValueError('discontinuous phase, concatenated logs or reversed monotonic clock')
    if any(w['reason'] != 'complete' for w in selected):
        raise ValueError('partial or reset-crossing window in selected phase')
    first, last = selected[0], selected[-1]
    steps = [v for w in selected for v in w['step_ns']]
    ticks = [v for w in selected for v in w['tick_ns']]
    # A physical iteration also pays its evaluator tick, not only Webots step().
    cycles = [step + tick for step, tick in zip(steps, ticks)]
    measured_ms = len(steps) * STEP_MS
    wall_ns = last['last_end_wall_ns'] - first['first_start_wall_ns']
    if wall_ns <= 0 or wall_ns < sum(w['wall_ns'] for w in selected):
        raise ValueError('invalid phase wall-time envelope')
    sufficient = measured_ms >= minimum_sim_ms
    speed = measured_ms * 1e6 / wall_ns
    p99 = percentile(steps, .99) / 1e6
    cycle_p99 = percentile(cycles, .99) / 1e6
    return {
        'schema': 'webeeblocks-grand-prix-step-phase-v1',
        'status': 'MEASURED_ONLY' if sufficient else 'UNPROVEN_TOO_SHORT',
        'course': course,
        'phase_start_sim_ms': first['start_sim_ms'],
        'phase_end_sim_ms': last['end_sim_ms'],
        'simulated_ms': measured_ms,
        'elapsed_wall_ms': wall_ns / 1e6,
        'windows': len(selected), 'step_count': len(steps),
        'speed_x': round(speed, 6),
        'step_p50_ms': round(percentile(steps, .50) / 1e6, 6),
        'step_p95_ms': round(percentile(steps, .95) / 1e6, 6),
        'step_p99_ms': round(p99, 6),
        'step_max_ms': round(max(steps) / 1e6, 6),
        'evaluator_tick_p99_ms': round(percentile(ticks, .99) / 1e6, 6),
        'cycle_p50_ms': round(percentile(cycles, .50) / 1e6, 6),
        'cycle_p95_ms': round(percentile(cycles, .95) / 1e6, 6),
        'cycle_p99_ms': round(cycle_p99, 6),
        'cycle_max_ms': round(max(cycles) / 1e6, 6),
        'speed_target_0_95_met': sufficient and speed >= .95,
        'step_p99_target_25ms_met': sufficient and p99 <= 25,
        'cycle_p99_target_25ms_met': sufficient and cycle_p99 <= 25,
        'display_fps': None, 'gui_latency': None, 'opengl_renderer': None,
        'overall_product_acceptance': 'UNPROVEN',
        'limitations': 'No native oracle/GUI/FPS evidence, no host identity or A/B comparability proof',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path, help='unchanged native evaluator log')
    parser.add_argument('--course', required=True, help='exact CoursePlan identifier')
    parser.add_argument('--start-ms', type=int, default=0, help='inclusive 8-ms-aligned simulated clock')
    parser.add_argument('--end-ms', type=int, help='inclusive 8-ms-aligned simulated clock')
    parser.add_argument('--min-sim-ms', type=int, default=30000)
    parser.add_argument('--output', type=Path, help='new JSON path; never overwrite')
    args = parser.parse_args(argv)
    try:
        with args.log.open(encoding='utf-8', errors='strict') as source:
            result = analyze(parse_windows(source), args.course, args.start_ms, args.end_ms, args.min_sim_ms)
        text = json.dumps(result, indent=2, sort_keys=True) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as destination:
                destination.write(text)
        else:
            sys.stdout.write(text)
        return 0 if result['status'] == 'MEASURED_ONLY' else 2
    except (ValueError, OSError) as error:
        parser.exit(2, f'UNPROVEN: {error}\n')


if __name__ == '__main__':
    sys.exit(main())
