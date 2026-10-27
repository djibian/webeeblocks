#!/usr/bin/env python3
"""Compare actual serialized .wbb structures; never infer classroom usability.

Usage: python3 tools/blockly/compare_wbb.py A.wbb B.wbb [C.wbb ...]
The human construction/debugging protocol lives in docs/GRAND_PRIX_PEDAGOGICAL_BLOCKS.md.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from measure_wbb import InvalidWorkspace, MAX_BYTES, analyze


INDICATORS = (
    'total_blocks', 'referenced_variables', 'procedure_definitions',
    'procedure_calls', 'main_chain_blocks', 'max_statement_nesting',
    'max_input_nesting', 'conditions', 'comparisons', 'logic_operations',
    'numeric_literals', 'sensor_reads', 'variable_updates', 'movement_commands',
)


def summarize(metrics):
    """Explicit structural proxies, not a cognitive score or a grade."""
    c = metrics['block_types']
    return {
        'total_blocks': metrics['total_blocks'],
        'referenced_variables': metrics['referenced_variables'],
        'procedure_definitions': metrics['procedure_definitions'],
        'procedure_calls': metrics['procedure_calls'],
        'main_chain_blocks': metrics['main_chain_blocks'],
        'max_statement_nesting': metrics['max_statement_nesting'],
        'max_input_nesting': metrics['max_input_nesting'],
        'conditions': c.get('controls_if', 0),
        'comparisons': c.get('logic_compare', 0),
        'logic_operations': c.get('logic_operation', 0),
        'numeric_literals': c.get('math_number', 0),
        'sensor_reads': sum(count for kind, count in c.items()
                            if kind in ('webeeblocks_v2_range', 'webeeblocks_range')),
        'variable_updates': c.get('variables_set', 0) + c.get('math_change', 0),
        'movement_commands': sum(c.get(kind, 0) for kind in (
            'webeeblocks_v2_move', 'webeeblocks_v2_vertical',
            'webeeblocks_v2_turn', 'webeeblocks_move',
            'webeeblocks_vertical', 'webeeblocks_turn')),
    }


def read_candidate(path):
    if path.stat().st_size > MAX_BYTES:
        raise InvalidWorkspace(f'{path}: project exceeds maximum supported size')
    data = path.read_bytes()
    project = json.loads(data.decode('utf-8'))
    metrics = analyze(project)
    return {
        'path': str(path),
        'sha256': hashlib.sha256(data).hexdigest(),
        'metrics': summarize(metrics),
        'unused_variable_declarations': metrics['unused_variable_declarations'],
        'undeclared_variable_ids': metrics['undeclared_variable_ids'],
    }


def compare(paths):
    if len(paths) < 2:
        raise ValueError('at least two actual .wbb projects are required')
    candidates = [read_candidate(Path(path)) for path in paths]
    base = candidates[0]['metrics']
    deltas = []
    for candidate in candidates[1:]:
        current = candidate['metrics']
        deltas.append({
            'path': candidate['path'],
            'delta_vs_first': {
                key: (current[key] - base[key]) if base[key] is not None and current[key] is not None else None
                for key in INDICATORS
            },
        })
    return {
        'schema_version': 1,
        'basis': 'real serialized Blockly structures; no AST, runtime or student observation inferred',
        'candidates': candidates,
        'comparisons': deltas,
        'human_construction_debugging_evidence_required': True,
        'automatic_pedagogical_winner': None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wbb', type=Path, nargs='+')
    args = parser.parse_args(argv)
    try:
        result = compare(args.wbb)
    except (OSError, UnicodeError, json.JSONDecodeError, InvalidWorkspace, ValueError) as error:
        print(f'Cannot compare .wbb: {error}', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
