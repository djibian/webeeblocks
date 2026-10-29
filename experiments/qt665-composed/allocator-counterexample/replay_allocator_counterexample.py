"""Replay two real native traces through the actual composed-consumer check.

Inputs: run40897930515/artifact12908396846, baseline and repaired Webots.
This tests an offline evidence predicate, never claims a new native execution.
"""
import ast
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent


def loop_source(source):
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.For)
                and isinstance(n.target, ast.Name) and n.target.id == 'r')
    return ast.get_source_segment(source, node)


def accepted(source, rows):
    tree = ast.parse(source)
    scope = dict(rows=rows, current={})
    try:
        exec(compile(tree, 'exact-evidence-loop', 'exec'), scope)
        assert all(d == 0 for d in scope['current'].values())
    except AssertionError:
        return False
    return True


def main():
    old = (HERE / 'allocator-loop-before.txt').read_text()
    current = loop_source((HERE.parent / 'run_composed.py').read_text())
    inputs = {
        'baseline': ('38f89dbad3ccb20f5712222a7604c69539ac3e9ca2e11ff7a72a046c7cb5e7df', 4),
        'selfpipe': ('68922512989c48862efd3b8216ef961ad15e81ea596d599a5f49c628c10bfb72', 0),
    }
    result = {}
    for name, (digest, allocations) in inputs.items():
        raw = (HERE / (name + '-trace.bin')).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest and len(raw) % 48 == 0
        rows = []
        for magic, pid, tid, event, depth, value in struct.iter_unpack('<6Q', raw):
            assert magic == 0x5154363635534947
            rows.append(dict(pid=pid, tid=tid, event=chr(event), depth=depth, value=value))
        assert sum(r['event'] in 'MCAF' for r in rows) == allocations
        before, after = accepted(old, rows), accepted(current, rows)
        assert before is True and after == (allocations == 0)
        result[name] = dict(records=len(rows), allocator_events=allocations,
                            old_accepted=before, repaired_accepted=after,
                            original_trace_sha256=digest)
    output = dict(scope='offline predicate replay of two retained real Webots traces',
                  old_source='a393476e80f12455e412ec2aa132de66dba79a0d',
                  old_loop_sha256=hashlib.sha256(old.encode()).hexdigest(),
                  verdict='PASS: faulty trace rejected, healthy trace preserved', cases=result)
    (HERE / 'RESULT.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
