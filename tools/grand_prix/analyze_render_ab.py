#!/usr/bin/env python3
"""Fail-closed, offline comparison of #912 renderer A/B step-wall evidence.

Reads raw GP_STEP_WALL_V1 lines; makes no simulator, safety or GUI decisions.
The declared common hardware/GUI conditions are not independently attested.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

PREFIX = 'GP_STEP_WALL_V1 '
DIGEST = re.compile(r'^[0-9a-f]{64}$')
SHA = re.compile(r'^[0-9a-f]{40}$')
ARMS = ('reference', 'candidate')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rank(values, percentile):
    require(bool(values), 'empty step durations')
    return sorted(values)[math.ceil(len(values) * percentile / 100) - 1]


def read_windows(path, course_id):
    windows = {}
    raw = path.read_bytes()
    for line in raw.decode('utf-8').splitlines():
        if not line.startswith(PREFIX):
            continue
        try:
            w = json.loads(line[len(PREFIX):])
        except json.JSONDecodeError as exc:
            raise ValueError(f'{path}: malformed telemetry JSON') from exc
        require(isinstance(w, dict) and w.get('schema') == 1 and
                w.get('course') == course_id, f'{path}: wrong telemetry schema/course')
        index = w.get('window')
        require(type(index) is int and index >= 0 and index not in windows,
                f'{path}: duplicate or invalid window')
        count, steps = w.get('count'), w.get('step_ns')
        require(type(count) is int and count > 0 and isinstance(steps, list) and
                len(steps) == count and all(type(v) is int and v >= 0 for v in steps),
                f'{path}: invalid raw step array')
        start, end, simulated, wall = (w.get(k) for k in
                                       ('start_sim_ms', 'end_sim_ms', 'simulated_ms', 'wall_ns'))
        require(all(type(v) is int for v in (start, end, simulated, wall)) and
                start >= 0 and end == start + (count - 1) * 8 and
                simulated == count * 8 and wall > 0 and
                w.get('step_p99_ns') == rank(steps, 99) and
                w.get('step_max_ns') == max(steps),
                f'{path}: inconsistent or incomplete native window {index}')
        windows[index] = w
    require(bool(windows), f'{path}: missing {PREFIX.strip()}')
    return windows, hashlib.sha256(raw).hexdigest()


def parse_trial(trial, root, course_id, minimum_sim_ms):
    require(isinstance(trial, dict) and
            type(trial.get('pair')) is int and trial['pair'] >= 1 and
            trial.get('arm') in ARMS, 'invalid pair/arm')
    first, last = trial.get('first_window'), trial.get('last_window')
    require(type(first) is int and type(last) is int and 0 <= first <= last,
            'invalid native window selection')
    log = trial.get('log')
    require(isinstance(log, str) and log and '\\' not in log, 'invalid log path')
    relative = Path(log)
    require(not relative.is_absolute() and '..' not in relative.parts and
            relative.as_posix() == log, 'log path must stay relative to manifest')
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), 'log escapes evidence directory')
    windows, digest = read_windows(path, course_id)
    selected = []
    for index in range(first, last + 1):
        require(index in windows, f'{log}: missing window {index}')
        w = windows[index]
        require(w.get('reason') == 'complete',
                f'{log}: partial or discontinuous window {index}')
        if selected:
            require(w['start_sim_ms'] == selected[-1]['end_sim_ms'] + 8,
                    f'{log}: simulator clock gap/RESET in selected phase')
        selected.append(w)
    simulated_ms = sum(w['simulated_ms'] for w in selected)
    require(simulated_ms >= minimum_sim_ms, f'{log}: phase shorter than {minimum_sim_ms} simulated ms')
    steps = [v for w in selected for v in w['step_ns']]
    wall_ns = sum(w['wall_ns'] for w in selected)
    return {
        'pair': trial['pair'], 'arm': trial['arm'], 'log': log,
        'log_sha256': digest, 'first_window': first, 'last_window': last,
        'simulated_ms': simulated_ms, 'wall_ns_in_windows': wall_ns,
        'speed_x_in_windows': round(simulated_ms * 1e6 / wall_ns, 6),
        'step_count': len(steps),
        'step_p50_ms': round(rank(steps, 50) / 1e6, 6),
        'step_p95_ms': round(rank(steps, 95) / 1e6, 6),
        'step_p99_ms': round(rank(steps, 99) / 1e6, 6),
        'step_max_ms': round(max(steps) / 1e6, 6),
    }


def analyze(manifest_path, minimum_sim_ms=30000):
    path = Path(manifest_path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(data, dict) and data.get('schema') == 'webeeblocks.gp-render-ab-v1',
            'unknown A/B manifest')
    common = data.get('common')
    require(isinstance(common, dict), 'missing common test conditions')
    for name, pattern in (('source_sha', SHA), ('webots_sha256', DIGEST),
                          ('wbb_sha256', DIGEST)):
        require(isinstance(common.get(name), str) and pattern.fullmatch(common[name]),
                f'missing or invalid {name}')
    for name in ('host_token', 'course_id', 'viewport', 'renderer', 'browser', 'phase'):
        require(isinstance(common.get(name), str) and common[name].strip(),
                f'missing common condition {name}')
    require(common.get('physical_step_ms') == 8 and common.get('gui_visible') is True,
            'rendered A/B requires declared visible GUI and unchanged physical 8-ms step')
    trials = data.get('trials')
    require(isinstance(trials, list) and len(trials) >= 6 and len(trials) % 2 == 0,
            'at least three A/B pairs required')
    candidate_fps = data.get('candidate_fps')
    require(type(candidate_fps) is int and candidate_fps in (25, 30, 60),
            'candidate must use a supported FPS budget')
    results = []
    seen_paths = set()
    orders = set()
    for offset in range(0, len(trials), 2):
        pair = offset // 2 + 1
        group = trials[offset:offset + 2]
        require(all(isinstance(t, dict) for t in group), 'invalid trial')
        require(all(t.get('pair') == pair for t in group) and
                {t.get('arm') for t in group} == set(ARMS),
                f'pair {pair} must contain adjacent distinct A/B arms')
        orders.add(tuple(t['arm'] for t in group))
        for t in group:
            require(t.get('render_fps') == (None if t['arm'] == 'reference' else candidate_fps),
                    'only the candidate may change WorldInfo.FPS')
            require(t.get('log') not in seen_paths, 'log reused across trials')
            seen_paths.add(t.get('log'))
            results.append(parse_trial(t, path.parent, common['course_id'], minimum_sim_ms))
    require(len(orders) == 2, 'A/B ordering must be counterbalanced (both AB and BA)')
    pairs = []
    for offset in range(0, len(results), 2):
        by_arm = {item['arm']: item for item in results[offset:offset + 2]}
        a, b = by_arm['reference'], by_arm['candidate']
        pairs.append({'pair': a['pair'],
                      'speed_ratio_candidate_over_reference': round(
                          b['speed_x_in_windows'] / a['speed_x_in_windows'], 6),
                      'step_p99_delta_ms': round(b['step_p99_ms'] - a['step_p99_ms'], 6)})
    return {
        'schema': 'webeeblocks.gp-render-ab-analysis-v1',
        'common_declared_not_independently_verified': common,
        'candidate_fps': candidate_fps,
        'trials': results, 'paired_differences': pairs,
        'interpretation': 'Instrumented complete step-wall windows only; gaps, actual visible FPS, GPU, UI latency and external wall clock are NOT measured.',
        'product_or_windows_acceptance': 'NOT_ESTABLISHED',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', help='JSON manifest referring to unmodified raw evaluator logs')
    args = parser.parse_args(argv)
    try:
        result = analyze(args.manifest)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
