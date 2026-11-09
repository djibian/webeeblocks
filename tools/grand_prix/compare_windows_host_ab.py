#!/usr/bin/env python3
"""Offline A/B diagnostic for the passive Webots Windows engine PID collector.

The collector observes only one process; this comparison never measures Webots
simulation speed, frame rate, GUI response, or product/safety acceptance.
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

SCHEMA = 'webeeblocks.windows-passive-host-v1'
EXPECTED_SCOPE = 'single Webots engine PID; no children, GPU utilization or simulation clock'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(value, size):
    return isinstance(value, str) and len(value) == size and all(c in '0123456789abcdef' for c in value)


def number(value, name, *, positive=False):
    require(not isinstance(value, bool), f'invalid {name}')
    try:
        val = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'invalid {name}') from exc
    require(math.isfinite(val) and (val > 0 if positive else val >= 0), f'invalid {name}')
    return val


def integer(value, name, *, positive=False):
    require(not isinstance(value, bool) and str(value).isdigit(), f'invalid {name}')
    val = int(value)
    require(val > 0 if positive else val >= 0, f'invalid {name}')
    return val


def fingerprint(data):
    """Equipment compatibility hint, not proof of same physical host."""
    os = data.get('operating_system')
    require(isinstance(os, dict), 'missing OS inventory')
    require(all(isinstance(os.get(k), str) and os[k] for k in ('caption', 'version', 'build')),
            'incomplete OS inventory')
    ram = integer(os.get('ram_bytes'), 'installed memory', positive=True)
    cpus, gpus = data.get('cpus'), data.get('video_devices')
    require(isinstance(cpus, list) and cpus and isinstance(gpus, list) and gpus,
            'missing CPU/GPU inventory')
    require(all(isinstance(c, dict) and isinstance(c.get('model'), str) and c['model']
                and integer(c.get('logical_processors'), 'logical_processors', positive=True) >= 1
                for c in cpus), 'invalid CPU identity')
    require(all(isinstance(g, dict) and isinstance(g.get('model'), str) and g['model']
                and isinstance(g.get('driver_version'), str) for g in gpus), 'invalid GPU identity')
    browser = data.get('external_browser')
    if browser is not None:
        require(isinstance(browser, dict) and sha(browser.get('exe_sha256'), 64)
                and browser.get('used_in_gui') == 'UNVERIFIED', 'invalid browser provenance')
    return json.dumps([os, ram, cpus, gpus, browser], sort_keys=True, separators=(',', ':'))


def read_trial(directory, expected_course):
    meta_path = directory / 'metadata.json'
    csv_path = directory / 'samples.csv'
    meta_bytes = meta_path.read_bytes()
    csv_bytes = csv_path.read_bytes()
    meta = json.loads(meta_bytes.decode('utf-8-sig'))
    require(isinstance(meta, dict) and meta.get('schema') == SCHEMA, 'unsupported host collector schema')
    require(meta.get('sampling_scope') == EXPECTED_SCOPE and meta.get('performance_acceptance') == 'NOT_MEASURED',
            'host capture is not an unmodified engine-only diagnostic')
    require(meta.get('course_id') == expected_course, 'course differs between A/B trials')
    require(meta.get('webots_version') == 'R2025a'
            and str(meta.get('process_name', '')).lower() == 'webots-bin', 'not an R2025a engine PID')
    require(meta.get('variant') in ('reference', 'candidate'), 'unexpected arm variant')
    require(sha(meta.get('source_sha'), 40) and sha(meta.get('webots_executable_sha256'), 64),
            'missing exact source and native engine digests')
    require(integer(meta.get('webots_pid'), 'PID', positive=True) > 0
            and isinstance(meta.get('process_start_utc'), str) and meta['process_start_utc'],
            'unbound process identity')
    actual = number(meta.get('actual_duration_s'), 'actual duration', positive=True)
    requested = number(meta.get('requested_duration_s'), 'requested duration', positive=True)
    period = integer(meta.get('requested_period_ms'), 'sample interval', positive=True)
    require(100 <= period <= 60000 and actual <= requested + period / 1000 + 5,
            'incoherent capture duration/interval')
    count = integer(meta.get('sample_count'), 'sample count', positive=True)
    with csv_path.open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        needed = {'elapsed_ms', 'period_ms', 'cpu_percent_one_core',
                  'process_cpu_total_s', 'working_set_bytes', 'private_memory_bytes',
                  'thread_count', 'utc'}
        require(reader.fieldnames is not None and len(reader.fieldnames) == len(needed)
                and set(reader.fieldnames) == needed,
                'unexpected Windows CSV telemetry columns')
        rows = list(reader)
    require(count == len(rows) and count >= 2, 'missing or truncated CPU/RAM samples')
    last_elapsed = 0.0
    last_cpu = -1.0
    usage = []
    for row in rows:
        require(all(isinstance(v, str) and v for v in row.values()), 'missing CSV value')
        elapsed = number(row['elapsed_ms'], 'elapsed', positive=True)
        span = number(row['period_ms'], 'period', positive=True)
        cpu = number(row['cpu_percent_one_core'], 'CPU percentage')
        cumulative = number(row['process_cpu_total_s'], 'cumulative process CPU')
        mem = integer(row['working_set_bytes'], 'working set')
        private = integer(row['private_memory_bytes'], 'private memory')
        threads = integer(row['thread_count'], 'threads', positive=True)
        require(elapsed > last_elapsed and abs((elapsed - last_elapsed) - span) <= .004,
                'non-monotonic or inconsistent sample period')
        require(cumulative + 1e-5 >= last_cpu, 'decreasing cumulative CPU')
        require(cpu <= 100 * len(meta['cpus']) * max(
            int(c['logical_processors']) for c in meta['cpus']) + 1,
            'impossible engine process CPU percentage')
        usage.append((span, cpu, mem, private, threads))
        last_elapsed, last_cpu = elapsed, cumulative
    require(last_elapsed <= actual * 1000 + .01 and actual * 1000 - last_elapsed <= period + 100,
            'CSV samples do not account for recorded duration')
    total_span = sum(x[0] for x in usage)
    require(total_span > 0, 'empty monotonic sampling envelope')
    return {
        'variant': meta['variant'], 'source_sha': meta['source_sha'],
        'engine_sha256': meta['webots_executable_sha256'],
        'equipment': fingerprint(meta), 'duration_s': actual,
        'metadata_sha256': hashlib.sha256(meta_bytes).hexdigest(),
        'samples_sha256': hashlib.sha256(csv_bytes).hexdigest(),
        'mean_cpu_percent_one_core': round(sum(x[0] * x[1] for x in usage) / total_span, 4),
        'median_working_set_mib': round(statistics.median(x[2] for x in usage) / 1048576, 4),
        'peak_working_set_mib': round(max(x[2] for x in usage) / 1048576, 4),
        'peak_private_memory_mib': round(max(x[3] for x in usage) / 1048576, 4),
        'median_threads': statistics.median(x[4] for x in usage),
        'sample_count': count,
    }


def compare(manifest_path):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(isinstance(manifest, dict) and manifest.get('schema') == 1,
            'invalid paired Windows host manifest')
    course = manifest.get('course_id')
    declared_host = manifest.get('declared_host')
    require(isinstance(course, str) and course and isinstance(declared_host, str)
            and declared_host.strip(), 'course and declared host required')
    trials = manifest.get('trials')
    require(isinstance(trials, list) and len(trials) >= 6 and len(trials) % 2 == 0,
            'three complete A/B pairs required')
    parsed = []
    used_paths = set()
    seen_samples = set()
    base_dir = manifest_path.parent.resolve()
    for i, row in enumerate(trials):
        require(isinstance(row, dict) and set(row) == {'arm', 'directory'}
                and row['arm'] in ('A', 'B') and isinstance(row['directory'], str)
                and row['directory'].strip(), 'invalid paired trial descriptor')
        expected_arm = ('A' if i % 4 in (0, 3) else 'B')
        require(row['arm'] == expected_arm, 'pairs must alternate AB/BA/AB')
        path = (base_dir / row['directory']).resolve()
        require(path.is_relative_to(base_dir) and path not in used_paths,
                'trial directory outside manifest or reused')
        used_paths.add(path)
        entry = read_trial(path, course)
        require(entry['variant'] == ('reference' if row['arm'] == 'A' else 'candidate'),
                'arm label disagrees with capture variant')
        require(entry['samples_sha256'] not in seen_samples, 'duplicated raw samples')
        seen_samples.add(entry['samples_sha256'])
        parsed.append(dict(arm=row['arm'], **entry))
    host = parsed[0]['equipment']
    require(all(r['equipment'] == host for r in parsed),
            'inconsistent Windows CPU/GPU/OS/browser inventory between A/B captures')
    identity = {a: {(r['source_sha'], r['engine_sha256']) for r in parsed if r['arm'] == a}
                for a in ('A', 'B')}
    require(all(len(group) == 1 for group in identity.values()),
            'candidate identity changed between repetitions')
    enough = all(r['duration_s'] >= 30 for r in parsed)
    pairs = []
    for i in range(0, len(parsed), 2):
        a, b = sorted(parsed[i:i + 2], key=lambda x: x['arm'])
        pairs.append({
            'pair': i // 2 + 1,
            'B_minus_A_mean_cpu_percentage_points': round(
                b['mean_cpu_percent_one_core'] - a['mean_cpu_percent_one_core'], 4),
            'B_minus_A_peak_working_set_mib': round(
                b['peak_working_set_mib'] - a['peak_working_set_mib'], 4),
        })
    result = {
        'schema': 1, 'course_id': course,
        'declared_host': declared_host,
        'status': 'HOST_ONLY_DIAGNOSTIC' if enough else 'INSUFFICIENT_CAPTURE_DURATION',
        'minimum_duration_s_per_capture': 30,
        'arms': {}, 'pairs': pairs,
        'source_identity': {a: dict(source_sha=next(iter(v))[0], engine_sha256=next(iter(v))[1])
                            for a, v in identity.items()},
        'trial_evidence': [
            {k: r[k] for k in ('arm', 'duration_s', 'sample_count', 'metadata_sha256', 'samples_sha256')}
            for r in parsed],
        'limitations': ('HOST PID ONLY; hardware equivalence is declared, not verified by this file; '
                        'no measured Webots simulation speed, step latency, GPU, real FPS, actual browser '
                        'usage, Blockly responsiveness, safety, or pedagogical acceptance; no PASS claim'),
    }
    for arm in ('A', 'B'):
        rows = [r for r in parsed if r['arm'] == arm]
        result['arms'][arm] = {
            metric: round(statistics.median(r[metric] for r in rows), 4)
            for metric in ('mean_cpu_percent_one_core', 'median_working_set_mib',
                           'peak_working_set_mib', 'peak_private_memory_mib', 'median_threads')
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args(argv)
    try:
        result = compare(args.manifest)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f'UNPROVEN: {exc}\n')
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['status'] == 'HOST_ONLY_DIAGNOSTIC' else 2


if __name__ == '__main__':
    sys.exit(main())
