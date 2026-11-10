#!/usr/bin/env python3
"""Compare fresh native scene incarnations on the identical built Windows engine.

A new process is not a proven within-attempt RESET epoch: retain that distinction.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('previous', 'restarted', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    result = {'schema': 1, 'status': 'UNPROVEN',
              'claim': 'fresh engine restart incarnation only; not product RESET'}
    try:
        a = json.loads(args.previous.read_text(encoding='utf-8'))
        b = json.loads(args.restarted.read_text(encoding='utf-8'))
        for key in ('engine_sha256', 'controller_dll_sha256',
                    'world_sha256', 'assembly', 'host'):
            if a.get(key) != b.get(key):
                raise ValueError('different native source or runner: ' + key)
        first = a['compact_colliders']['first_incarnation']
        second = b['compact_colliders']['first_incarnation']
        if (not first or not second or first == second or
                a.get('status') != 'MEASURED_ONLY' or
                b.get('status') != 'MEASURED_ONLY'):
            raise ValueError('fresh native incarnation not demonstrated')
        witness = b.get('mutation_probe', [])
        if len(witness) != 1 or witness[0].get('status') != 'PASS':
            raise ValueError('real native mutation witness not complete')
        result.update(status='MEASURED_ONLY', previous_incarnation=first,
                      restarted_incarnation=second,
                      mutation_checks=witness[0]['checks'])
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8')
    return 0 if result['status'] == 'MEASURED_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
