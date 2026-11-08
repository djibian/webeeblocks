#!/usr/bin/env python3
"""Offline, non-authoritative paired analysis of Grand Prix 8-ms wall traces.

Never infers renderer/FPS or identical hardware from a trace: provenance is
operator-declared in the manifest. This is not a GUI, safety, or speed PASS.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

PREFIX = 'GP_STEP_WALL_V1 '
STEP_MS = 8


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(value, length):
    return isinstance(value, str) and len(value) == length and all(c in '0123456789abcdef' for c in value)


def _percentile(samples, percent):
    ordered = sorted(samples)
    return ordered[math.ceil(len(ordered) * percent / 100) - 1]


def _windows(path, course, start, end):
    """Select one continuous native trace epoch, not stitched attempts."""
    result = []
    last_sequence = -1
    for line in path.read_text(encoding='utf-8').splitlines():
        if PREFIX not in line:
            continue
        row = json.loads(line.split(PREFIX, 1)[1])
        _require(isinstance(row, dict) and row.get('schema') == 1, 'unknown probe schema')
        _require(row.get('course') == course, 'mixed course in probe log')
        sequence = row.get('window')
        _require(type(sequence) is int and sequence > last_sequence, 'repeated or unordered probe window')
        last_sequence = sequence
        count = row.get('count')
        first, final = row.get('start_sim_ms'), row.get('end_sim_ms')
        _require(type(count) is int and count > 0 and type(first) is int and type(final) is int
                 and first >= 0 and final == first + (count - 1) * STEP_MS,
                 'invalid 8-ms native window clock')
        _require(type(row.get('simulated_ms')) is int and row['simulated_ms'] == count * STEP_MS,
                 'invalid simulated duration')
        steps, ticks = row.get('step_ns'), row.get('tick_ns')
        _require(isinstance(steps, list) and isinstance(ticks, list)
                 and len(steps) == len(ticks) == count
                 and all(type(x) is int and x >= 0 for x in steps + ticks),
                 'missing or invalid raw native durations')
        wall = row.get('wall_ns')
        wall_start, wall_end = row.get('first_start_wall_ns'), row.get('last_end_wall_ns')
        _require(type(wall_start) is int and type(wall_end) is int
                 and wall_start >= 0 and wall_end > wall_start
                 and type(wall) is int and wall == wall_end - wall_start
                 and sum(steps) + sum(ticks) <= wall,
                 'inconsistent monotonic wall duration')
        # A reset or other epoch is not comparable to another attempt.
        # Windows straddling a phase boundary are discarded, not truncated.
        if first >= start and final + STEP_MS <= end:
            _require(row.get('reason') == 'complete', 'partial native window in measured phase')
            _require(count == 125, 'non-native complete window size')
            _require(first % STEP_MS == 0, 'unaligned native 8-ms window')
            _require(not result or sequence == result[-1]['window'] + 1,
                     'discontinuous native window index')
            _require(not result or wall_start >= result[-1]['last_end_wall_ns'],
                     'overlapping monotonic wall windows')
            # These summary fields are emitted by StepWallProbe, not independent
            # observations. Reject altered summaries before comparing trials.
            expected_summary = {
                'speed_x': round(count * STEP_MS * 1e6 / wall, 6),
                'step_p50_ns': _percentile(steps, 50),
                'step_p95_ns': _percentile(steps, 95),
                'step_p99_ns': _percentile(steps, 99),
                'step_max_ns': max(steps),
                'tick_p99_ns': _percentile(ticks, 99),
            }
            _require(all(type(row.get(name)) is (float if name == 'speed_x' else int)
                         and row[name] == value
                         for name, value in expected_summary.items()),
                     'inconsistent native probe summary')
            result.append(row)
    _require(bool(result), f'no complete native windows in {path.name}')
    for older, newer in zip(result, result[1:]):
        _require(newer['start_sim_ms'] == older['end_sim_ms'] + STEP_MS,
                 'gapped/overlapping phase or multiple reset epochs')
    count = sum(row['count'] for row in result)
    _require(count >= 125, 'less than one simulated second of complete observations')
    # Deduplicate native timing evidence, never an unchecked summary or
    # arbitrary metadata that could change without a new observation.
    native_fields = ('course', 'window', 'reason', 'start_sim_ms', 'end_sim_ms',
                     'simulated_ms', 'count', 'step_ns', 'tick_ns', 'wall_ns',
                     'first_start_wall_ns', 'last_end_wall_ns')
    observations = [{field: row[field] for field in native_fields} for row in result]
    digest = hashlib.sha256(json.dumps(observations, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    return {
        'trace_digest': digest,
        'windows': len(result), 'simulated_ms': count * STEP_MS,
        'observed_start_ms': result[0]['start_sim_ms'],
        'observed_end_ms': result[-1]['end_sim_ms'] + STEP_MS,
        # These sums omit wall-clock gaps between completed probe windows.
        'wall_ns_in_windows': sum(row['wall_ns'] for row in result),
        # Continuous monotonic envelope of the selected complete windows.
        # Includes stalls between windows, but not time outside the observed range.
        'wall_ns_observed_envelope': (result[-1]['last_end_wall_ns'] -
                                      result[0]['first_start_wall_ns']),
        'step_ns': [x for row in result for x in row['step_ns']],
        'tick_ns': [x for row in result for x in row['tick_ns']],
    }


def compare(manifest_path):
    manifest_path = Path(manifest_path)
    doc = json.loads(manifest_path.read_text(encoding='utf-8'))
    _require(type(doc) is dict and doc.get('schema') == 1, 'unknown manifest schema')
    _require(_sha(doc.get('source_sha'), 40) and _sha(doc.get('webots_executable_sha256'), 64)
             and _sha(doc.get('program_sha256'), 64), 'exact code/binary/program digests required')
    for name in ('course', 'host_id', 'display_mode'):
        _require(isinstance(doc.get(name), str) and doc[name].strip(), f'{name} required')
    phase = doc.get('phase_ms')
    _require(type(phase) is list and len(phase) == 2
             and all(type(x) is int and x >= 0 and x % STEP_MS == 0 for x in phase)
             and phase[1] > phase[0], 'invalid fixed 8-ms comparison phase')
    fps = doc.get('render_fps')
    _require(isinstance(fps, dict) and set(fps) == {'A', 'B'}
             and all(type(value) is int and value in (25, 30, 60) for value in fps.values())
             and fps['A'] != fps['B'], 'two different declared rendered FPS caps required')
    trials = doc.get('trials')
    _require(isinstance(trials, list) and len(trials) >= 6 and len(trials) % 2 == 0,
             'at least three complete A/B pairs required')
    records = {'A': [], 'B': []}
    seen_logs = set()
    seen_digests = set()
    first_arm = None
    for i in range(0, len(trials), 2):
        pair = trials[i:i + 2]
        _require(all(type(row) is dict and row.get('arm') in ('A', 'B')
                     and isinstance(row.get('log'), str) and row['log'] for row in pair)
                 and {row['arm'] for row in pair} == {'A', 'B'},
                 f'pair {i // 2 + 1} must contain one A and one B')
        _require(first_arm is None or pair[0]['arm'] != first_arm,
                 'paired trial order must alternate AB/BA')
        first_arm = pair[0]['arm']
        for row in pair:
            path = (manifest_path.parent / row['log']).resolve()
            _require(path not in seen_logs, 'same log reused for multiple trials')
            seen_logs.add(path)
            entry = _windows(path, doc['course'], *phase)
            _require(entry['trace_digest'] not in seen_digests,
                     'duplicate native observations under different paths')
            seen_digests.add(entry['trace_digest'])
            entry['trial'] = i // 2 + 1
            records[row['arm']].append(entry)
    coverage = {(entry['observed_start_ms'], entry['observed_end_ms'], entry['simulated_ms'])
                for results in records.values() for entry in results}
    _require(len(coverage) == 1, 'different simulated coverage across paired trials')
    summary = {}
    for arm, results in records.items():
        # Equal weight per trial prevents one long window from hiding a slow run.
        speeds = [r['simulated_ms'] * 1e6 / r['wall_ns_in_windows'] for r in results]
        envelope_speeds = [r['simulated_ms'] * 1e6 / r['wall_ns_observed_envelope'] for r in results]
        p99_ms = [_percentile(r['step_ns'], 99) / 1e6 for r in results]
        summary[arm] = {
            'render_fps_declared': fps[arm],
            'median_speed_in_windows_x': round(statistics.median(speeds), 6),
            'median_speed_observed_envelope_x': round(statistics.median(envelope_speeds), 6),
            'median_step_p99_ms': round(statistics.median(p99_ms), 6),
            'per_trial': [dict(pair=r['trial'], simulated_ms=r['simulated_ms'],
                               speed_in_windows_x=round(speed, 6),
                               speed_observed_envelope_x=round(envelope_speed, 6),
                               step_p99_ms=round(p99, 6),
                               tick_p99_ms=round(_percentile(r['tick_ns'], 99) / 1e6, 6))
                          for r, speed, envelope_speed, p99 in
                          zip(results, speeds, envelope_speeds, p99_ms)],
        }
    return {
        'schema': 1, 'source_sha': doc['source_sha'], 'course': doc['course'],
        'declared_host': doc['host_id'], 'display_mode': doc['display_mode'],
        'phase_ms': phase, 'pair_count': len(trials) // 2,
        'observed_complete_window_phase_ms': [records['A'][0]['observed_start_ms'],
                                              records['A'][0]['observed_end_ms']],
        'arms': summary,
        'measurement_scope': 'WINDOW_DURATION_ONLY_INTER_WINDOW_GAPS_NOT_MEASURED',
        'envelope_measurement_scope': 'FIRST_TO_LAST_COMPLETE_WINDOW_INCLUDING_GAPS',
        'interpretation': ('DIAGNOSTIC_ONLY: speed_in_windows_x excludes inter-window stalls; '
                           'speed_observed_envelope_x includes gaps between the first and last '
                           'selected complete windows, but not time outside their observed range '
                           'or necessarily the full requested phase; '
                           'no overall 0.95x, measured FPS/GUI or safety PASS'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path, help='paired trials JSON manifest')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(compare(args.manifest), sort_keys=True, indent=2))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(f'refused A/B comparison: {exc}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
