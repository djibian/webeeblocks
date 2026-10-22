#!/usr/bin/env python3
"""Report reproducible *structural* Blockly complexity, not pupil usability.

Usage: python3 tools/blockly/measure_wbb.py path/to/project.wbb
This is deliberately independent of Webots, Chrome, private oracle and the AST.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 5_000_000
MAX_BLOCKS = 20_000
MAX_DEPTH = 150
STATEMENT_INPUT = re.compile(r"^(?:DO\d*|ELSE|STACK|ON_SENSOR|BODY)$")


class InvalidWorkspace(ValueError):
    pass


def analyze(project):
    if not isinstance(project, dict) or project.get('format') != 'webeeblocks-project' or project.get('version') != 1:
        raise InvalidWorkspace('not a supported WebeeBlocks .wbb project (format/version)')
    ws = project.get('workspace')
    if not isinstance(ws, dict) or not isinstance(ws.get('blocks'), dict):
        raise InvalidWorkspace('missing Blockly workspace.blocks')
    roots = ws['blocks'].get('blocks', [])
    variables = ws.get('variables', [])
    if not isinstance(roots, list) or not isinstance(variables, list):
        raise InvalidWorkspace('malformed workspace roots or variables')
    declared = {}
    for var in variables:
        if not isinstance(var, dict) or not isinstance(var.get('id'), str) or not isinstance(var.get('name'), str):
            raise InvalidWorkspace('malformed variable declaration')
        if var['id'] in declared:
            raise InvalidWorkspace('duplicate variable declaration ID')
        declared[var['id']] = var['name']

    counts = Counter()
    referenced = set()
    block_ids = set()
    max_input = 0
    max_statement = 0
    max_chain = 0
    instances = 0

    def visit(block, nesting, statement_nesting, depth):
        nonlocal max_input, max_statement, max_chain, instances
        if depth > MAX_DEPTH:
            raise InvalidWorkspace('nesting exceeds safety limit')
        if not isinstance(block, dict) or not isinstance(block.get('type'), str) or not block['type']:
            raise InvalidWorkspace('malformed Blockly block')
        bid = block.get('id')
        if not isinstance(bid, str) or not bid or bid in block_ids:
            raise InvalidWorkspace('missing/duplicate Blockly block ID')
        block_ids.add(bid)
        instances += 1
        if instances > MAX_BLOCKS:
            raise InvalidWorkspace('block count exceeds safety limit')
        typ = block['type']
        counts[typ] += 1
        fields = block.get('fields', {})
        if not isinstance(fields, dict):
            raise InvalidWorkspace('malformed block fields')
        var = fields.get('VAR')
        if isinstance(var, dict) and isinstance(var.get('id'), str):
            referenced.add(var['id'])
        max_input = max(max_input, nesting)
        max_statement = max(max_statement, statement_nesting)
        inputs = block.get('inputs', {})
        if not isinstance(inputs, dict):
            raise InvalidWorkspace('malformed block inputs')
        for name, entry in inputs.items():
            if not isinstance(entry, dict):
                raise InvalidWorkspace('malformed Blockly input')
            # A retained shadow is only a fallback when a real child is connected.
            child = entry.get('block') or entry.get('shadow')
            if child is not None:
                visit(child, nesting + 1, statement_nesting + bool(STATEMENT_INPUT.fullmatch(name)), depth + 1)
        successor = block.get('next')
        chain = 1
        if successor is not None:
            if not isinstance(successor, dict) or not isinstance(successor.get('block'), dict):
                raise InvalidWorkspace('malformed next-block connection')
            chain += visit(successor['block'], nesting, statement_nesting, depth + 1)
        max_chain = max(max_chain, chain)
        return chain

    main_candidates = []
    for root in roots:
        if not isinstance(root, dict):
            raise InvalidWorkspace('malformed top-level block')
        if root.get('type') in ('webeeblocks_v2_takeoff', 'webeeblocks_takeoff'):
            main_candidates.append(root)
        visit(root, 0, 0, 0)
    main_chain = None
    if len(main_candidates) == 1:
        chain = 0
        item = main_candidates[0]
        while item is not None:
            chain += 1
            item = (item.get('next') or {}).get('block')
        main_chain = chain

    return {
        'schema_version': 1,
        'basis': 'serialized Blockly workspace; no runtime/learner/ergonomic acceptance',
        'activity_id': (project.get('activity') or {}).get('id'),
        'total_blocks': instances,
        'block_types': dict(sorted(counts.items())),
        'top_level_stacks': len(roots),
        'main_chain_blocks': main_chain,
        'max_connected_chain_blocks': max_chain,
        'max_input_nesting': max_input,
        'max_statement_nesting': max_statement,
        'procedure_definitions': sum(n for t, n in counts.items() if t.startswith('procedures_def')),
        'procedure_calls': sum(n for t, n in counts.items() if t.startswith('procedures_call')),
        'declared_variables': len(declared),
        'referenced_variables': len(referenced),
        'unused_variable_declarations': sorted(declared[k] for k in declared.keys() - referenced),
        'undeclared_variable_ids': sorted(referenced - declared.keys()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wbb', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.wbb.stat().st_size > MAX_BYTES:
            raise InvalidWorkspace('project exceeds maximum supported size')
        project = json.loads(args.wbb.read_text(encoding='utf-8'))
        print(json.dumps(analyze(project), indent=2, sort_keys=True, ensure_ascii=False))
    except (OSError, UnicodeError, json.JSONDecodeError, InvalidWorkspace) as exc:
        print(f'Invalid .wbb: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
