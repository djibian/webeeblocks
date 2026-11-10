#!/usr/bin/env python3
"""Same-runner, same-binary A/B of *observation overhead*, NEVER a product gain."""
import argparse
import json
from pathlib import Path


def compare(a, b):
    if a.get('status') != 'MEASURED_ONLY' or b.get('status') != 'MEASURED_ONLY':
        raise ValueError('at least one native measurement is UNPROVEN')
    if a.get('compact_enabled') is not False or b.get('compact_enabled') is not True:
        raise ValueError('mislabelled native lanes')
    for key in ('assembly', 'host', 'engine_sha256', 'world_sha256', 'controller_dll_sha256',
                'physical_timestep_ms', 'required_simulated_ms', 'scenario'):
        if a.get(key) != b.get(key):
            raise ValueError('A/B not comparable: ' + key)
    native = b.get('compact_colliders') or {}
    count = native.get('samples', 0)
    if count < 3000 or native.get('decode_errors', 1) or native.get('canonical_parity') != count:
        raise ValueError('compact coverage or canonical parity incomplete')
    ea, eb = a['evaluator'], b['evaluator']
    if ea.get('course') != eb.get('course') or ea.get('overall_product_acceptance') != 'UNPROVEN' or eb.get('overall_product_acceptance') != 'UNPROVEN':
        raise ValueError('mission identity or diagnostic acceptance changed')
    p = eb['phases']
    c = p['scene_collider_total']['mean_ms']
    n = p['compact_native_rpc_and_decode']['mean_ms']
    if c is None or n is None or n <= 0:
        raise ValueError('missing same-tick native cost')
    t = lambda key: round(native[key] / count / 1e6, 6)
    return {
        'schema': 1, 'status': 'MEASURED_ONLY', 'not_a_product_speedup': True,
        'assembly': a['assembly'], 'engine_sha256': a['engine_sha256'],
        'dll_sha256': a['controller_dll_sha256'],
        'world_sha256': a['world_sha256'], 'host': a['host'],
        'simulated_ticks_per_lane': 3750, 'compact_checked_ticks': count,
        'compact_payload_bytes_per_checked_tick': round(native['payload_bytes'] / count, 3),
        'native_production_ms_mean': t('native_production_ns'),
        'native_serialization_ms_mean': t('native_serialization_ns'),
        'native_rpc_total_ms_mean': t('native_rpc_total_ns'),
        'python_consumption_ms_mean': t('python_consumption_ns'),
        'transfer_plus_dispatch_residual_ms_mean': t('transfer_plus_controller_dispatch_ns'),
        'historical_collider_traversal_and_values_ms_mean_on_B': c,
        'compact_native_rpc_and_decode_ms_mean_on_B': n,
        'hypothetical_net_saving_if_full_authority_parity_later_proven_ms_per_checked_tick':
            round(c - n, 6),
        'A_tick_mean_ms': ea['phases']['tick_total']['mean_ms'],
        'B_tick_mean_ms': eb['phases']['tick_total']['mean_ms'],
        'A_wall_ms': a['evaluator'].get('elapsed_wall_ms'),
        'B_wall_ms': b['evaluator'].get('elapsed_wall_ms'),
        'native_unknown_coverage_samples': native['unknown_coverage_samples'],
        'native_structure_changes': native['root_structure_changes'],
        'native_canonical_parity': native['canonical_parity'],
        'native_canonical_accepted': native['canonical_accepted'],
        'native_historical_accepted': native['historical_accepted'],
        'limitations': [
            'Both A and B retain complete historical Supervisor authority and full exportString.',
            'B adds an extra native inventory RPC; observed B/A is an overhead A/B, not a product speedup.',
            'Transfer-plus-dispatch residual includes native C parsing, synchronization and scheduling, not pure wire time.',
            'Root topology hash does not certify Floor or internal PROTO and scene revision coverage is incomplete.',
            'No native mutations, negative refusals, RESET, 3D rendering, GUI or pupil Blockly were tested here.',
            'An imagined replacement of historical reads must not be presented as measured speedup.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--compact', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        a = json.loads(args.baseline.read_text(encoding='utf-8'))
        b = json.loads(args.compact.read_text(encoding='utf-8'))
        result = compare(a, b)
    except Exception as exc:
        result = {'schema': 1, 'status': 'UNPROVEN', 'error': type(exc).__name__ + ': ' + str(exc)}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0 if result['status'] == 'MEASURED_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
