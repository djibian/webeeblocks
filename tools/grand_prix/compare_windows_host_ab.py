#!/usr/bin/env python3
"""Fail-closed paired diagnostics for passive Grand Prix Windows host captures.

These captures observe a native engine PID, not simulated time, FPS, GUI,
commands, safety or pupil usability. A valid comparison is diagnostic ONLY.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

SCHEMA = 'webeeblocks.windows-passive-host-v1'
REQUIRED_CSV = ('elapsed_ms', 'period_ms', 'cpu_percent_one_core',
                'process_cpu_total_s', 'working_set_bytes',
                'private_memory_bytes', 'thread_count')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(value, n):
    return isinstance(value, str) and len(value) == n and all(c in '0123456789abcdef' for c in value)


def number(value, *, positive=False):
    try:
        v = float(value)
        if not math.isfinite(v) or (v <= 0 if positive else v < 0):
            raise ValueError
        return v
    except (TypeError, ValueError, OverflowError):
        raise ValueError('invalid finite nonnegative host sample') from None


def load_capture(directory):
    meta_file = directory / 'metadata.json'
    csv_file = directory / 'samples.csv'
    metadata_bytes = meta_file.read_bytes()
    samples_bytes = csv_file.read_bytes()
    meta = json.loads(metadata_bytes.decode('utf-8-sig'))
    require(type(meta) is dict and meta.get('schema') == SCHEMA, 'unsupported passive host schema')
    require(meta.get('webots_version') == 'R2025a' and meta.get('process_name') == 'webots-bin'
            and meta.get('performance_acceptance') == 'NOT_MEASURED'
            and meta.get('sampling_scope') == 'single Webots engine PID; no children, GPU utilization or simulation clock',
            'missing exact engine-only diagnostic boundary')
    require(sha(meta.get('source_sha'), 40) and sha(meta.get('webots_executable_sha256'), 64),
            'missing source or engine digest')
    require(meta.get('variant') in ('reference', 'candidate') and
            isinstance(meta.get('course_id'), str) and meta['course_id'], 'missing variant/course')
    require(type(meta.get('webots_pid')) is int and meta['webots_pid'] > 0 and
            isinstance(meta.get('process_start_utc'), str) and meta['process_start_utc'] and
            type(meta.get('sample_count')) is int and meta['sample_count'] >= 2,
            'missing PID, process epoch or sample count')
    duration = number(meta.get('actual_duration_s'), positive=True)
    require(duration >= 30 and number(meta.get('requested_duration_s'), positive=True) >= 30,
            'passive capture shorter than 30 seconds')
    require(type(meta.get('requested_period_ms')) is int and 200 <= meta['requested_period_ms'] <= 5000,
            'invalid sampling cadence')
    require(type(meta.get('operating_system')) is dict and
            isinstance(meta.get('cpus'), list) and bool(meta['cpus']) and
            isinstance(meta.get('video_devices'), list) and bool(meta['video_devices']),
            'incomplete equipment inventory')
    # This metadata is a limited comparability fingerprint, not host identity:
    # it may coincide on distinct machines and cannot attest actual GL usage.
    hardware = {k: meta[k] for k in ('operating_system', 'cpus', 'video_devices', 'external_browser')}
    with csv_file.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and set(REQUIRED_CSV).issubset(reader.fieldnames),
                'missing passive host CSV columns')
        rows = list(reader)
    require(len(rows) == meta['sample_count'], 'missing host samples')
    elapsed = []
    cpu = []
    memory = []
    private = []
    threads = []
    prev_cpu_total = None
    for row in rows:
        t = number(row['elapsed_ms'], positive=True)
        interval = number(row['period_ms'], positive=True)
        pct = number(row['cpu_percent_one_core'])
        total = number(row['process_cpu_total_s'])
        ws = number(row['working_set_bytes'], positive=True)
        pm = number(row['private_memory_bytes'], positive=True)
        th = number(row['thread_count'], positive=True)
        require(th.is_integer(), 'non-integer thread count')
        require(not elapsed or t > elapsed[-1], 'non-monotonic sample clock')
        require(not elapsed or abs((t - elapsed[-1]) - interval) <= 2.5,
                'inconsistent host sampling interval')
        require(prev_cpu_total is None or total >= prev_cpu_total - 1e-5,
                'non-monotonic process CPU total')
        elapsed.append(t)
        cpu.append(pct)
        memory.append(ws)
        private.append(pm)
        threads.append(th)
        prev_cpu_total = total
    require(elapsed[-1] <= (duration * 1000 + 50) and
            abs(elapsed[-1] - duration * 1000) <= max(200, meta['requested_period_ms']),
            'capture duration contradicts host samples')
    digest = hashlib.sha256(metadata_bytes + b'\0' + samples_bytes).hexdigest()
    return {
        'metadata': meta, 'hardware': hardware, 'digest': digest,
        'duration_s': round(duration, 3),
        'cpu_one_core_mean_percent': round(statistics.fmean(cpu), 4),
        'working_set_max_bytes': int(max(memory)),
        'private_memory_max_bytes': int(max(private)),
        'thread_count_max': int(max(threads)),
        'sample_count': len(rows),
    }


def compare(manifest_path):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(type(manifest) is dict and manifest.get('schema') == 1, 'unknown comparison manifest')
    require(isinstance(manifest.get('host_id'), str) and manifest['host_id'].strip(),
            'operator-declared host_id required')
    require(isinstance(manifest.get('phase'), str) and manifest['phase'].strip(),
            'operator-declared common phase required')
    trials = manifest.get('trials')
    require(type(trials) is list and len(trials) >= 6 and len(trials) % 2 == 0,
            'at least three complete pairs required')
    seen_paths = set()
    seen_digests = set()
    per_arm = {'reference': [], 'candidate': []}
    first_arm = None
    baseline = None
    identity = {}
    for i in range(0, len(trials), 2):
        pair = trials[i:i + 2]
        require(all(type(row) is dict and row.get('variant') in per_arm
                    and isinstance(row.get('directory'), str) and row['directory'] for row in pair)
                and {r['variant'] for r in pair} == set(per_arm),
                'pair must contain one reference and one candidate')
        require(first_arm is None or pair[0]['variant'] != first_arm,
                'pairs must alternate AB/BA')
        first_arm = pair[0]['variant']
        for row in pair:
            directory = (manifest_path.parent / row['directory']).resolve()
            require(directory not in seen_paths, 'host capture reused across trials')
            seen_paths.add(directory)
            capture = load_capture(directory)
            require(capture['digest'] not in seen_digests, 'duplicate host capture bytes')
            seen_digests.add(capture['digest'])
            meta = capture['metadata']
            require(meta['variant'] == row['variant'], 'variant mismatch between manifest and capture')
            common = (capture['hardware'], meta['course_id'],
                      meta['requested_duration_s'], meta['requested_period_ms'])
            require(baseline is None or common == baseline,
                    'different hardware/software/course/duration/cadence across trials')
            baseline = common
            engine = meta['webots_executable_sha256']
            arm = row['variant']
            require(arm not in identity or identity[arm] == (meta['source_sha'], engine),
                    'source/engine identity changed within one A/B arm')
            identity[arm] = (meta['source_sha'], engine)
            per_arm[arm].append({key: capture[key] for key in (
                'duration_s', 'cpu_one_core_mean_percent', 'working_set_max_bytes',
                'private_memory_max_bytes', 'thread_count_max', 'sample_count')})
    require(identity['reference'][1] != identity['candidate'][1],
            'reference/candidate use identical engine bytes')
    summaries = {}
    for arm, samples in per_arm.items():
        summaries[arm] = {
            'source_sha': identity[arm][0], 'engine_sha256': identity[arm][1],
            'median_cpu_one_core_percent': round(statistics.median(
                x['cpu_one_core_mean_percent'] for x in samples), 4),
            'median_peak_working_set_bytes': round(statistics.median(
                x['working_set_max_bytes'] for x in samples)),
            'trials': samples,
        }
    return {
        'schema': 1, 'status': 'PASSIVE_HOST_DIAGNOSTIC_ONLY',
        'operator_declared_host': manifest['host_id'],
        'operator_declared_phase': manifest['phase'],
        'course': baseline[1],
        'pair_count': len(trials) // 2,
        'arms': summaries,
        'limitations': ('Cannot establish same physical host, rendered phase, simulation speed, '
                        'step p99, measured OpenGL/FPS, GUI/Blockly responsiveness, '
                        'safety or product PASS. No CPU/RAM score is an acceptance oracle.'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path, help='JSON manifest of alternating capture directories')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(compare(args.manifest), indent=2, sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(f'UNPROVEN: {exc}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
