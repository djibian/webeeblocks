#!/usr/bin/env python3
"""Strict, measurement-only breakdown of GP_EVALUATOR_PHASE_V1 records.

An opt-in probe does not attest native provenance, scene immutability, GUI FPS,
or gain from an optimization. Nested exportString is NOT an extra tick cost.
Read unchanged log records. A discontinuity/reset must start a separate run.
"""

import argparse
import json
import math
from pathlib import Path
import sys

PREFIX = 'GP_EVALUATOR_PHASE_V1 '
STEP_MS = 8
WINDOW_STEPS = 125
SCENE_CHILDREN = ('exportString', 'scene_root_inventory',
                  'scene_vehicle_identity', 'scene_collider_traversal',
                  'scene_collider_values', 'collider_batch_python_consumption')
EXCLUSIVE = ('scene_and_colliders', 'kinematics', 'flight_observation',
             'contacts', 'liveness_wire', 'mission_oracle',
             'protocol_request', 'protocol_model', 'protocol_channel')
PHASES = ('tick_total', 'exportString', 'scene_and_colliders',
          'scene_root_inventory', 'scene_vehicle_identity',
          'scene_collider_traversal', 'scene_collider_values',
          'collider_batch_python_consumption', 'scene_collider_total', 'scene_without_exportString',
          'scene_exclusive_residual', 'kinematics', 'flight_observation',
          'contacts', 'liveness_wire', 'mission_oracle',
          'protocol_request', 'protocol_model', 'protocol_channel',
          'protocol_total', 'unattributed_tick')


def _percentile(values, fraction):
    sorted_values = sorted(values)
    return sorted_values[math.ceil(len(sorted_values) * fraction) - 1]


def parse_windows(lines):
    """Read native windows; never turn missing/corrupted timing into zero."""
    windows = []
    for number, line in enumerate(lines, 1):
        index = line.find(PREFIX)
        if index < 0:
            continue
        try:
            raw = json.loads(line[index + len(PREFIX):])
            if (not isinstance(raw, dict) or type(raw.get('schema')) is not int or
                    raw['schema'] != 1 or not isinstance(raw.get('course'), str) or
                    not raw['course'] or type(raw.get('window')) is not int or
                    raw['window'] < 0):
                raise ValueError('invalid phase schema, course or window')
            rows = raw.get('rows')
            if not isinstance(rows, list) or not 1 <= len(rows) <= WINDOW_STEPS:
                raise ValueError('invalid phase sample count')
            last = None
            for row in rows:
                if not isinstance(row, dict) or type(row.get('sim_ms')) is not int or (
                        row['sim_ms'] < STEP_MS or row['sim_ms'] % STEP_MS or
                        last is not None and row['sim_ms'] != last + STEP_MS):
                    raise ValueError('invalid 8-ms physical sample clock')
                last = row['sim_ms']
                times = row.get('durations_ns')
                if not isinstance(times, dict) or not times or any(
                        not isinstance(k, str) or type(v) is not int or v < 0
                        for k, v in times.items()):
                    raise ValueError('malformed durations')
                if 'tick_total' not in times:
                    raise ValueError('missing tick_total')
                if any(k not in EXCLUSIVE + SCENE_CHILDREN + ('tick_total',) for k in times):
                    raise ValueError('unknown phase (version mismatch)')
                if any(k in times for k in SCENE_CHILDREN) and 'scene_and_colliders' not in times:
                    raise ValueError('orphan nested scene phase')
                if (sum(times.get(k, 0) for k in SCENE_CHILDREN) >
                        times.get('scene_and_colliders', 0) or
                        sum(times.get(k, 0) for k in EXCLUSIVE) > times['tick_total']):
                    raise ValueError('impossible overlapping durations')
            windows.append(raw)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError(f'invalid phase log line {number}: {exc}') from exc
    if not windows:
        raise ValueError('no GP_EVALUATOR_PHASE_V1 samples')
    return windows


def analyze(windows, course, start_ms=0, end_ms=None, minimum_sim_ms=30000):
    """Analyze only complete, contiguous, 125-step windows for one run.

    Conditional paths remain missing. 'unattributed_tick' includes timing
    overhead, uninstrumented channel I/O and publication:
    it MUST NOT be relabeled as any individual cause without a new probe.
    """
    if (not isinstance(course, str) or not course or
            type(start_ms) is not int or start_ms < 0 or start_ms % STEP_MS or
            (end_ms is not None and (type(end_ms) is not int or
             end_ms < start_ms or end_ms % STEP_MS)) or
            type(minimum_sim_ms) is not int or minimum_sim_ms < STEP_MS):
        raise ValueError('invalid 8-ms phase boundary')
    included = [w for w in windows if w['rows'][0]['sim_ms'] >= start_ms and
                (end_ms is None or w['rows'][-1]['sim_ms'] <= end_ms)]
    if not included:
        raise ValueError('no complete phase window in selected interval')
    if any(w['course'] != course or len(w['rows']) != WINDOW_STEPS for w in included):
        raise ValueError('mixed course or incomplete phase window')
    for a, b in zip(included, included[1:]):
        if (b['window'] != a['window'] + 1 or
                b['rows'][0]['sim_ms'] != a['rows'][-1]['sim_ms'] + STEP_MS):
            raise ValueError('discontinuous phase: reset, dropped samples or concatenated runs')
    rows = [row for w in included for row in w['rows']]
    if not rows:
        raise ValueError('no timing samples')
    # Derived exclusive durations are calculated PER TICK, never by subtracting
    # independent p99 values that may come from different physical steps.
    per_sample = []
    for row in rows:
        t = row['durations_ns']
        values = dict(t)
        if 'scene_and_colliders' in t:
            if 'exportString' in t:
                values['scene_without_exportString'] = (t['scene_and_colliders'] - t['exportString'])
            values['scene_exclusive_residual'] = (t['scene_and_colliders'] -
                                                  sum(t.get(k, 0) for k in SCENE_CHILDREN))
            if ('scene_collider_traversal' in t and 'scene_collider_values' in t):
                values['scene_collider_total'] = (t['scene_collider_traversal'] +
                                                  t['scene_collider_values'])
        if any(k in t for k in ('protocol_request', 'protocol_model', 'protocol_channel')):
            values['protocol_total'] = sum(t.get(k, 0) for k in
                                          ('protocol_request', 'protocol_model', 'protocol_channel'))
        values['unattributed_tick'] = t['tick_total'] - sum(t.get(k, 0) for k in EXCLUSIVE)
        per_sample.append(values)
    worst_n = max(1, math.ceil(len(rows) * .01))
    tail_indices = sorted(range(len(rows)), key=lambda i: per_sample[i]['tick_total'],
                          reverse=True)[:worst_n]
    results = {}
    for key in PHASES:
        samples = [v[key] for v in per_sample if key in v]
        tail = [per_sample[i][key] for i in tail_indices if key in per_sample[i]]
        results[key] = {
            'observed': len(samples), 'missing': len(rows) - len(samples),
            'mean_ms': round(sum(samples) / len(samples) / 1e6, 6) if samples else None,
            'p50_ms': round(_percentile(samples, .5) / 1e6, 6) if samples else None,
            'p95_ms': round(_percentile(samples, .95) / 1e6, 6) if samples else None,
            'p99_ms': round(_percentile(samples, .99) / 1e6, 6) if samples else None,
            'max_ms': round(max(samples) / 1e6, 6) if samples else None,
            'slow_tick_tail_observed': len(tail),
            'slow_tick_tail_mean_ms': round(sum(tail) / len(tail) / 1e6, 6) if tail else None,
            'slow_tick_tail_share_of_tick_pct': (
                round(100 * sum(tail) / sum(per_sample[i]['tick_total'] for i in tail_indices), 4)
                if tail else None),
        }
    simulated_ms = len(rows) * STEP_MS
    return {
        'schema': 'webeeblocks-grand-prix-evaluator-phase-analysis-v1',
        'status': 'MEASURED_ONLY' if simulated_ms >= minimum_sim_ms else 'UNPROVEN_TOO_SHORT',
        'course': course,
        'sim_start_ms': rows[0]['sim_ms'],
        'sim_end_ms': rows[-1]['sim_ms'],
        'simulated_ms': simulated_ms,
        'windows': len(included), 'steps': len(rows),
        'slow_tick_tail_count': worst_n,
        'phases': results,
        'speed_x': None, 'visible_fps': None, 'overall_product_acceptance': 'UNPROVEN',
        'limitations': ('Measurements are in-process and conditional; no direct A/B causal '
                        'effect, native mutation coverage, complete cycle speed, or GUI/FPS proof. '
                        'Nested scene and derived totals must not be added to parent stages. '
                        'Tail percentages are per-stage intersections, not an additive profile. '
                        'Unattributed time includes unprobed calls and timer overhead.'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--course', required=True)
    parser.add_argument('--start-ms', type=int, default=0)
    parser.add_argument('--end-ms', type=int)
    parser.add_argument('--min-sim-ms', type=int, default=30000)
    parser.add_argument('--output', type=Path, help='Create new JSON; never overwrite')
    args = parser.parse_args(argv)
    try:
        with args.log.open(encoding='utf-8', errors='strict') as source:
            result = analyze(parse_windows(source), args.course, args.start_ms,
                             args.end_ms, args.min_sim_ms)
        output = json.dumps(result, indent=2, sort_keys=True) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as destination:
                destination.write(output)
        else:
            sys.stdout.write(output)
        return 0 if result['status'] == 'MEASURED_ONLY' else 2
    except (ValueError, OSError) as exc:
        parser.exit(2, f'UNPROVEN: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
