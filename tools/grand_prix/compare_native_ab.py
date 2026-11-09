#!/usr/bin/env python3
"""Fail-closed offline comparison of two R2025a native-engine builds (#914).

Uses unmodified GP_STEP_WALL_V1 records and the exact executable digests from
Windows inventory files. Inventory is evidence of bytes on disk, not proof that
this executable ran, nor a renderer/GUI or product-acceptance measurement.
"""

import argparse
import json
from pathlib import Path
import statistics

from tools.grand_prix.compare_render_ab import _require, _sha, _windows, _percentile


def _inventory(path, source_sha):
    doc = json.loads(path.read_text(encoding='utf-8'))
    _require(type(doc) is dict and doc.get('schema') == 'webeeblocks-grand-prix-windows-host-v1',
             'unsupported Windows inventory schema')
    _require(doc.get('source_sha') == source_sha, 'inventory source SHA missing or mismatched')
    webots = doc.get('webots')
    _require(type(webots) is dict and webots.get('release') == 'R2025a'
             and webots.get('exe_relative_path') == 'msys64/mingw64/bin/webots-bin.exe'
             and _sha(webots.get('exe_sha256'), 64), 'wrong or missing native engine inventory')
    _require(type(doc.get('physical_memory_bytes')) is int and doc['physical_memory_bytes'] > 0
             and type(doc.get('os')) is dict and type(doc.get('cpu')) is list
             and bool(doc['cpu']) and type(doc.get('display_adapters')) is list
             and bool(doc['display_adapters']), 'incomplete machine inventory')
    _require(doc.get('measurement_state') == 'INVENTORY_ONLY_NOT_A_PERFORMANCE_OR_ACCEPTANCE_RESULT',
             'inventory falsely claims performance')
    browser = doc.get('browser')
    if browser is not None:
        _require(type(browser) is dict and _sha(browser.get('exe_sha256'), 64),
                 'invalid optional browser inventory')
    return doc


def compare(manifest_path):
    manifest_path = Path(manifest_path)
    doc = json.loads(manifest_path.read_text(encoding='utf-8'))
    _require(type(doc) is dict and doc.get('schema') == 1, 'unsupported native A/B manifest')
    _require(_sha(doc.get('source_sha'), 40) and _sha(doc.get('program_sha256'), 64),
             'exact source/program digests required')
    for key in ('course', 'host_id', 'display_mode'):
        _require(isinstance(doc.get(key), str) and doc[key].strip(), f'{key} required')
    phase = doc.get('phase_ms')
    _require(type(phase) is list and len(phase) == 2
             and all(type(t) is int and t >= 0 and t % 8 == 0 for t in phase)
             and phase[1] - phase[0] >= 30000, 'aligned phase >=30 simulated seconds required')
    fps = doc.get('render_fps')
    _require(type(fps) is int and fps in (25, 30, 60), 'one identical declared rendered FPS cap required')
    inv_paths = doc.get('inventories')
    _require(type(inv_paths) is dict and set(inv_paths) == {'A', 'B'},
             'exactly two engine inventories required')
    inventories = {}
    paths = set()
    for arm in ('A', 'B'):
        name = inv_paths[arm]
        _require(isinstance(name, str) and bool(name), 'inventory path required')
        path = (manifest_path.parent / name).resolve()
        _require(path not in paths, 'inventory reused for different engines')
        paths.add(path)
        inventories[arm] = _inventory(path, doc['source_sha'])
    a, b = inventories['A'], inventories['B']
    host_fields = ('os', 'physical_memory_bytes', 'cpu', 'display_adapters', 'browser')
    _require(all(a.get(key) == b.get(key) for key in host_fields),
             'host/browser/driver inventory differs across arms')
    engine_a, engine_b = a['webots']['exe_sha256'], b['webots']['exe_sha256']
    _require(engine_a != engine_b, 'A/B did not identify distinct native engines')
    trials = doc.get('trials')
    _require(type(trials) is list and len(trials) >= 6 and len(trials) % 2 == 0,
             'three complete alternating A/B pairs required')
    seen_paths, seen_digests = set(), set()
    records = {'A': [], 'B': []}
    first_arm = None
    for i in range(0, len(trials), 2):
        pair = trials[i:i + 2]
        _require(all(type(row) is dict and row.get('arm') in ('A', 'B')
                     and isinstance(row.get('log'), str) and bool(row['log']) for row in pair)
                 and {row['arm'] for row in pair} == {'A', 'B'}, 'incomplete A/B pair')
        _require(first_arm is None or pair[0]['arm'] != first_arm,
                 'non-alternating AB/BA trial order')
        first_arm = pair[0]['arm']
        for row in pair:
            path = (manifest_path.parent / row['log']).resolve()
            _require(path not in seen_paths, 'native log reused in multiple trials')
            seen_paths.add(path)
            record = _windows(path, doc['course'], *phase)
            _require(record['trace_digest'] not in seen_digests,
                     'replayed native observations under a different path')
            seen_digests.add(record['trace_digest'])
            _require(record['simulated_ms'] >= 30000,
                     'native log lacks 30 consecutive simulated seconds')
            record['pair'] = i // 2 + 1
            records[row['arm']].append(record)
    coverage = {(x['observed_start_ms'], x['observed_end_ms'], x['simulated_ms'])
                for arm in ('A', 'B') for x in records[arm]}
    _require(len(coverage) == 1, 'different native simulated phase coverage')
    summary = {}
    for arm in ('A', 'B'):
        entries = []
        for row in records[arm]:
            speed = row['simulated_ms'] * 1e6 / row['wall_ns_observed_envelope']
            steps = row['step_ns']
            cycles = [s + t for s, t in zip(steps, row['tick_ns'])]
            entries.append({
                'pair': row['pair'], 'speed_observed_envelope_x': round(speed, 6),
                'step_p99_ms': round(_percentile(steps, 99) / 1e6, 6),
                'cycle_p99_ms': round(_percentile(cycles, 99) / 1e6, 6),
            })
        summary[arm] = {
            'engine_sha256_from_inventory': engine_a if arm == 'A' else engine_b,
            'median_speed_observed_envelope_x': round(statistics.median(
                entry['speed_observed_envelope_x'] for entry in entries), 6),
            'per_trial': entries,
        }
    return {
        'schema': 1, 'analysis': 'NON_AUTHORITATIVE_NATIVE_ENGINE_AB',
        'source_sha': doc['source_sha'], 'course': doc['course'],
        'declared_host': doc['host_id'], 'declared_render_fps': fps,
        'declared_display_mode': doc['display_mode'], 'pair_count': len(trials) // 2,
        'observed_simulated_phase_ms': list(next(iter(coverage)))[:2],
        'arms': summary,
        'interpretation': ('Native engine bytes are inventoried, not tied to the actually running PID; '
                           'host/program/GUI/display equality is not independently witnessed. '
                           'The observed envelope includes gaps only between the first and last '
                           'complete native windows. No Webots safety, rendered FPS, Blockly '
                           'latency, full phase, 0.95x product PASS or teacher acceptance is established.'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(compare(args.manifest), indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.error(f'UNPROVEN native A/B: {error}')


if __name__ == '__main__':
    raise SystemExit(main())
