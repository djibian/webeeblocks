"""Conservative R2025a bulk read of the live route scene graph."""
import re
import time

from tools.grand_prix.native_collider_contract_v2 import canonical_native_boxes


_VEHICLE = '\n    Crazyflie {\n'
_EVALUATOR = '\n    DEF GP_ROUTE_EVALUATOR Robot {\n'
_END_NODE = '\n    }'
_NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
_VEHICLE_DYNAMIC = re.compile(
    r'^      (?:(?:(?:hidden (?:linearVelocity|angularVelocity)_0|translation)'
    rf'(?: {_NUMBER}){{3}}|rotation(?: {_NUMBER}){{4}})'
    r'|customData "[^"\\\r\n]*")\n', re.MULTILINE)
_EVALUATOR_DYNAMIC = re.compile(
    r'^      (?:model|description|customData) "[^"\\\r\n]*"\n', re.MULTILINE)
_USE = re.compile(r'\bUSE\s+\S')


def read_scene_signature(root, probe=None):
    """Remove only the root robots' live pose, velocities and protocol strings.

    Other fields, root entries, node edges and names remain byte-for-byte.
    Only the pinned serializer's ordinary, self-contained scene is eligible.
    Unknown formats go through the regular Supervisor traversal.
    """
    export = getattr(root, 'exportString', None)
    if not callable(export):
        return None
    start_ns = time.perf_counter_ns() if probe is not None else None
    try:
        scene = export()
    finally:
        if start_ns is not None:
            probe.record('exportString', time.perf_counter_ns() - start_ns)
    if (type(scene) is not str or len(scene) > 256 * 1024 or
            not scene.startswith('Group {\n  children [\n') or
            not scene.endswith('\n  ]\n}') or scene.count(_VEHICLE) != 1 or
            scene.count(_EVALUATOR) != 1 or '\\' in scene or _USE.search(scene)):
        return None
    # R2025a can write literal line breaks inside SFString. In that format
    # indentation alone cannot identify a root node or one of its fields.
    quoted = scene.split('"')
    if len(quoted) % 2 == 0 or any('\n' in value or '\r' in value for value in quoted[1::2]):
        return None
    before, _, tail = scene.partition(_VEHICLE)
    vehicle, end, tail = tail.partition(_END_NODE)
    if not end:
        return None
    between, evaluator_start, tail = tail.partition(_EVALUATOR)
    evaluator, end, after = tail.partition(_END_NODE)
    if not evaluator_start or not end:
        return None
    # Append a newline so the final scalar of either node can also be removed.
    return (before, _VEHICLE_DYNAMIC.sub('', vehicle + '\n'), between,
            _EVALUATOR_DYNAMIC.sub('', evaluator + '\n'), after)


class NativeSceneSnapshot:
    """Keep topology from a full check while an exact live signature agrees."""

    def __init__(self, course, phase_probe=None):
        self.course = course
        self.phase_probe = phase_probe
        self.expected_boxes = canonical_native_boxes(course)
        self.signature = None
        self.root_count = None
        self.boxes = None
        self.opaque_roots = ()

    def matches(self, signature, root_count):
        return (signature is not None and signature == self.signature and
                root_count == self.root_count)

    def record(self, signature, root_count, boxes, opaque_roots):
        self.signature = signature
        self.root_count = root_count
        self.boxes = boxes
        self.opaque_roots = opaque_roots
