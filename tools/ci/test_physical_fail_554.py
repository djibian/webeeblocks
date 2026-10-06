#!/usr/bin/env python3
"""Exact historical binding replay, only the shared interpreter and fake effects."""
from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/physical'))
from shared_interpreter_host import BoundSharedInterpreter, SharedInterpreterHostError, validate_bound_shared_program
from launch_physical_qualification import execution_request_count
from range_observer import range_mm_to_m

BINDING = (ROOT / 'tools/ci/fixtures/physical_fail_554_ast.json').read_text().strip()
HASH = '55b78da087a11730328e7be7d2616420881cbadcbd9d7d604b76250eb3e6dc99'


class Backend:
    def __init__(self, raw_mm=1000, fail_at=None):
        self.trace = []
        self.raw_mm = raw_mm
        self.fail_at = fail_at

    def __getattr__(self, method):
        if method not in {'takeoff', 'setSpeed', 'wait', 'readRange', 'move', 'turn', 'vertical', 'land'}:
            raise AttributeError(method)
        def call(*args):
            self.trace.append((method, *args))
            if len(self.trace) == self.fail_at:
                raise RuntimeError('injected independent failure at ' + method)
            if method == 'readRange':
                return range_mm_to_m(self.raw_mm)
        return call


def main():
    assert sha256(BINDING.encode()).hexdigest() == HASH, 'historical AST identity changed'
    assert execution_request_count(BINDING) == 1, 'step 1 is the whole dynamic program'
    assert validate_bound_shared_program(BINDING).ast_binding == BINDING
    prefix = [('takeoff', 0.5), ('setSpeed', 0.2), ('wait', 1), ('readRange', 'front')]
    suffix = [('turn', 45), ('vertical', 'up', 0.2), ('vertical', 'down', 0.2), ('land',)]
    for raw, branch in ((1000, ('move', 'forward', 0.2)), (800, ('wait', 1)), (500, ('wait', 1))):
        backend = Backend(raw)
        BoundSharedInterpreter(BINDING, backend).run()
        assert backend.trace == prefix + [branch] + suffix, backend.trace
    for raw in (8000, 8190, 65535):
        backend = Backend(raw)
        try:
            BoundSharedInterpreter(BINDING, backend).run()
        except SharedInterpreterHostError:
            pass
        else:
            raise AssertionError('unavailable Multi-ranger became a free-space number')
        assert backend.trace == prefix, 'failure continued to another program effect'
    for failed_call in range(1, 10):
        backend = Backend(fail_at=failed_call)
        host = BoundSharedInterpreter(BINDING, backend)
        try:
            host.run()
        except SharedInterpreterHostError:
            pass
        else:
            raise AssertionError('injected effect failure was accepted')
        assert len(backend.trace) == failed_call, 'program continued after failure'
        try:
            host.run()
        except SharedInterpreterHostError:
            pass
        assert len(backend.trace) == failed_call, 'failed interpreter replayed'
    print('PASS #554 exact AST digest, both sensor branches, unavailable values, all failure sites and no replay (no hardware)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
