"""Experimental, read-only collateral decode of ONE native root.exportString reply.

This is NOT a substitute for Supervisor scene traversal or any mission oracle.
The physical #922/#923 native engine remains in place; the existing exportString
RPC supplies one grouped native observation, without an additional RPC.
Only the R2025a pinned serializer's simple root Solid layout is recognized.
"""
import json
import math
import re
import time

PREFIX = 'GP_COLLIDER_SHADOW_V1 '
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
ROOT_SOLID = re.compile(r'^    DEF (GP_V2_(?:L|H|FINAL)_[A-Z0-9_]+) Solid \{\s*$', re.M)
ROOT_END = re.compile(r'^    }\s*$', re.M)
POSITION = re.compile(r'^\s{6}translation\s+(' + NUMBER + r')\s+(' + NUMBER +
                      r')\s+(' + NUMBER + r')\s*$', re.M)
ROTATION = re.compile(r'^\s{6}rotation\s+(' + NUMBER + r')\s+(' + NUMBER +
                      r')\s+(' + NUMBER + r')\s+(' + NUMBER + r')\s*$', re.M)
LOCKED = re.compile(r'^\s{6}locked\s+TRUE\s*$', re.M)
BOUND = re.compile(r'\bboundingObject\s+Box\s*\{\s*size\s+(' + NUMBER + r')\s+(' +
                   NUMBER + r')\s+(' + NUMBER + r')\s*\}', re.M)
VISUAL = re.compile(r'\bgeometry\s+Box\s*\{\s*size\s+(' + NUMBER + r')\s+(' +
                    NUMBER + r')\s+(' + NUMBER + r')\s*\}', re.M)


def _triplet(match):
    if match is None:
        raise ValueError('missing native collider vector')
    numbers = tuple(float(v) for v in match.groups())
    if any(not math.isfinite(v) for v in numbers):
        raise ValueError('nonfinite native collider vector')
    return numbers


def grouped_boxes(scene):
    """Decode only root physical Solid representations; reject unknown syntax.

    The independent authoritative Supervisor API must still reject ALL unlisted
    bodies, PROTO internals, Floor changes and stale/reset observations.
    """
    if type(scene) is not str or len(scene) > 256 * 1024 or '\\' in scene or '\r' in scene:
        raise ValueError('unknown/oversized native export format')
    if not scene.startswith('Group {\n  children [\n') or not scene.endswith('\n  ]\n}'):
        raise ValueError('unknown native root serializer')
    results = {}
    starts = list(ROOT_SOLID.finditer(scene))
    for start in starts:
        end = ROOT_END.search(scene, start.end())
        if end is None:
            raise ValueError('unterminated root collider')
        name = start.group(1)
        if name in results:
            raise ValueError('duplicate physical DEF ' + name)
        body = scene[start.end():end.start()]
        if (len(re.findall(r'\bShape\s*\{', body)) != 1 or
                len(re.findall(r'\bgeometry\s+Box\s*\{', body)) != 1 or
                len(re.findall(r'\bboundingObject\s+Box\s*\{', body)) != 1 or
                not LOCKED.search(body)):
            raise ValueError('noncanonical physical/visible shape ' + name)
        rotation = ROTATION.search(body)
        if rotation is not None and abs(float(rotation.group(4))) > 1e-6:
            raise ValueError('rotated native collider ' + name)
        results[name] = (_triplet(POSITION.search(body)),
                         _triplet(BOUND.search(body)), _triplet(VISUAL.search(body)))
    return results


def _matching(actual, expected):
    return (len(actual) == len(expected) and
            all(math.isclose(a, float(f'{e:.6f}'), rel_tol=0, abs_tol=1e-9)
                for a, e in zip(actual, expected)))


def compare_grouped_to_canonical(scene, expected_boxes):
    """Compare the grouped native bytes to independent host geometry values."""
    actual = grouped_boxes(scene)
    expected = {box.name: box for box in expected_boxes}
    if actual.keys() != expected.keys():
        raise ValueError('native batch missing/extra collider names')
    for name, (position, physical, visual) in actual.items():
        box = expected[name]
        if (not _matching(position, box.position) or
                not _matching(physical, box.size) or
                not _matching(visual, box.size)):
            raise ValueError('native batch physical/visible geometry differs: ' + name)
    return len(actual)


class CanonicalColliderShadow:
    """Observe one grouped export plus unchanged historical authority per tick."""

    def __init__(self, expected, probe, window=125):
        self.expected = expected
        self.probe = probe
        self.window = window
        self.count = 0
        self.parity = 0
        self.shadow_accept = 0
        self.historical_accept = 0
        self.failures = {}
        self.total_bytes = 0
        self.last = None

    def observe(self, scene):
        started = time.perf_counter_ns()
        try:
            count = compare_grouped_to_canonical(scene, self.expected)
            outcome, detail = True, 'ok:' + str(count)
        except Exception as exc:
            outcome, detail = False, type(exc).__name__ + ': ' + str(exc)
        duration = time.perf_counter_ns() - started
        self.probe.record('collider_batch_python_consumption', duration)
        self.last = (outcome, detail)
        self.total_bytes += len(scene.encode('utf-8')) if type(scene) is str else 0

    def historical(self, success, error=None):
        if self.last is None:
            return
        accepted, detail = self.last
        self.last = None
        self.count += 1
        self.shadow_accept += int(accepted)
        self.historical_accept += int(success)
        self.parity += int(accepted == success)
        if not accepted or not success:
            reason = detail if not accepted else type(error).__name__
            self.failures[reason] = self.failures.get(reason, 0) + 1
        if self.count % self.window == 0:
            self.probe.sink(PREFIX + json.dumps({
                'schema': 1, 'window': self.count // self.window - 1,
                'samples': self.window,
                'parity': self.parity,
                'shadow_accepted': self.shadow_accept,
                'historical_accepted': self.historical_accept,
                'bytes_total': self.total_bytes,
                'failures': self.failures,
            }, separators=(',', ':'), sort_keys=True))
            self.parity = self.shadow_accept = self.historical_accept = 0
            self.total_bytes = 0
            self.failures = {}
