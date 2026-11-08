#!/usr/bin/env python3
"""Offline non-authoritative A/B analysis of 8-ms Grand Prix wall-step logs.

Only complete, continuous GP_STEP_WALL_V1 windows from one stable phase
are admissible. Provenance, GUI FPS, safety, and end-to-end throughput remain
external evidence; window durations omit inter-window logging gaps.
"""
import argparse
import json
import math
from pathlib import Path
import statistics
import sys

from tools.grand_prix.step_wall_probe import PREFIX

STEP_MS = 8
COUNT = 125


def percentile(values, p):
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * p / 100) - 1]


def read_trial(path, course_id, min_seconds=30):
    """Reject mixed, discontinuous, insufficient or corrupted windows."""
    windows = []
    with Path(path).open(encoding='utf-8') as source:
        for line in source:
            if PREFIX not in line:
                continue
            item = json.loads(line.split(PREFIX, 1)[1])
            if type(item) is not dict:
                raise ValueError('invalid window object')
            expected = {'schema': 1, 'course': course_id, 'reason': 'complete',
                        'count': COUNT, 'simulated_ms': COUNT * STEP_MS}
            for key, value in expected.items():
                if type(item.get(key)) is not type(value) or item[key] != value:
                    raise ValueError(f'incompatible {key} in {path}')
            n = item['count']
            start, end, sequence = (item.get(k) for k in
                                    ('start_sim_ms', 'end_sim_ms', 'window'))
            if any(type(v) is not int for v in (start, end, sequence)):
                raise ValueError('invalid simulation time or window index')
            if start < 0 or start % STEP_MS or end != start + (n - 1) * STEP_MS:
                raise ValueError('invalid physical clock interval')
            if windows and (start != windows[-1]['end_sim_ms'] + STEP_MS or
                            sequence != windows[-1]['window'] + 1):
                raise ValueError('discontinuous phase, reset, or missing window')
            arrays = []
            for key in ('step_ns', 'tick_ns'):
                samples = item.get(key)
                if (not isinstance(samples, list) or len(samples) != n or
                        any(type(v) is not int or v < 0 for v in samples)):
                    raise ValueError(f'invalid raw {key}')
                arrays.append(samples)
            steps, ticks = arrays
            wall = item.get('wall_ns')
            if type(wall) is not int or wall < sum(steps) + sum(ticks):
                raise ValueError('invalid or understated window wall time')
            checks = {'step_p50_ns': percentile(steps, 50),
                      'step_p95_ns': percentile(steps, 95),
                      'step_p99_ns': percentile(steps, 99),
                      'step_max_ns': max(steps),
                      'tick_p99_ns': percentile(ticks, 99)}
            if any(type(item.get(k)) is not int or item[k] != v
                   for k, v in checks.items()):
                raise ValueError('published summary contradicts raw samples')
            speed = round(COUNT * STEP_MS * 1e6 / wall, 6)
            if (type(item.get('speed_x')) not in (float, int) or
                    not math.isfinite(item['speed_x']) or
                    abs(item['speed_x'] - speed) > 0.000001):
                raise ValueError('published speed contradicts raw wall time')
            windows.append(item)
    if len(windows) * COUNT * STEP_MS < min_seconds * 1000:
        raise ValueError('insufficient continuous stable-phase seconds')
    steps = [v for w in windows for v in w['step_ns']]
    ticks = [v for w in windows for v in w['tick_ns']]
    wall = sum(w['wall_ns'] for w in windows)
    return {
        'file': str(path), 'windows': len(windows),
        'simulated_s': len(windows) * COUNT * STEP_MS / 1000,
        'step_p50_ms': percentile(steps, 50) / 1e6,
        'step_p95_ms': percentile(steps, 95) / 1e6,
        'step_p99_ms': percentile(steps, 99) / 1e6,
        'step_max_ms': max(steps) / 1e6,
        'tick_p99_ms': percentile(ticks, 99) / 1e6,
        'optimistic_window_speed_x': round(len(windows) * COUNT * STEP_MS * 1e6 / wall, 6),
    }


def compare(trials, course_id, min_seconds=30):
    groups = {'reference': [], 'candidate': []}
    for arm, path in trials:
        if arm not in groups:
            raise ValueError('trial arm must be reference or candidate')
        if any(row['file'] == str(path) for rows in groups.values() for row in rows):
            raise ValueError('same log submitted more than once')
        groups[arm].append(read_trial(path, course_id, min_seconds))
    if any(len(rows) < 3 for rows in groups.values()):
        raise ValueError('at least three independent trials per arm are required')
    ref_p99 = statistics.median(row['step_p99_ms'] for row in groups['reference'])
    new_p99 = statistics.median(row['step_p99_ms'] for row in groups['candidate'])
    return {
        'scope': 'offline-diagnostic-only; not performance or safety acceptance',
        'provenance': 'caller-labelled logs; same hardware/GUI/program not verified',
        'speed_caveat': 'window speed excludes gaps between windows; not end-to-end sim/wall',
        'course': course_id, 'minimum_stable_phase_seconds': min_seconds,
        'trials': groups, 'median_step_p99_ms': {'reference': ref_p99, 'candidate': new_p99},
        'median_step_p99_delta_ms': round(new_p99 - ref_p99, 6),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course-id', required=True,
                        help='exact shared host CoursePlan ID (not pupil AST)')
    parser.add_argument('--min-seconds', type=int, default=30,
                        help='minimum continuous simulated seconds per trial (default 30)')
    parser.add_argument('--trial', action='append', required=True,
                        metavar='reference:FILE|candidate:FILE')
    parser.add_argument('--output', help='new JSON report; stdout if omitted')
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.min_seconds <= 210:
            raise ValueError('min-seconds outside 1..210')
        trials = []
        for item in args.trial:
            arm, sep, path = item.partition(':')
            if not sep or not path:
                raise ValueError('trial format is reference:FILE or candidate:FILE')
            trials.append((arm, path))
        report = json.dumps(compare(trials, args.course_id, args.min_seconds),
                            indent=2, sort_keys=True) + '\n'
        if args.output:
            with Path(args.output).open('x', encoding='utf-8') as dest:
                dest.write(report)
        else:
            print(report, end='')
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f'INVALID A/B evidence: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
