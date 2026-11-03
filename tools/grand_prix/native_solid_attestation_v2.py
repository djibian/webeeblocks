"""Fail-closed Webots Supervisor check for variable Grand Prix Solid/Box bodies.

Host-only admission *precondition*: this does not compose a world, authorize
flight, validate actual sensing or declare any course mission successful.
The caller must independently build a complete expected manifest from the
same immutable CoursePlan used by the scene and mission evaluator.
"""
from dataclasses import dataclass
import math
import re

_PREFIXES = ('GP_V2_L_', 'GP_V2_H_', 'GP_V2_FINAL_')
_TOLERANCE_M = 1e-6  # World-builder renders coordinates to six decimal places.


class NativeGeometryMismatch(ValueError):
    """Missing, unexpected or inconsistent native physical geometry."""


def _vector(value, label, *, positive=False):
    if (not isinstance(value, (tuple, list)) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in value) or
            (positive and any(v <= 0 for v in value))):
        raise NativeGeometryMismatch(f'{label}: finite 3-vector required')
    return tuple(float(v) for v in value)


@dataclass(frozen=True)
class RequiredSolid:
    name: str
    translation: tuple
    size: tuple

    def __post_init__(self):
        if (type(self.name) is not str or not re.fullmatch(
                r'GP_V2_(?:L|H|FINAL)_[A-Z0-9_]+', self.name)):
            raise NativeGeometryMismatch('invalid Grand Prix solid DEF')
        object.__setattr__(self, 'translation', _vector(self.translation, 'translation'))
        object.__setattr__(self, 'size', _vector(self.size, 'size', positive=True))


def _close(actual, expected, label):
    observed = _vector(actual, label, positive=label.endswith('size'))
    if any(abs(a - b) > _TOLERANCE_M for a, b in zip(observed, expected)):
        raise NativeGeometryMismatch(f'{label}: native values differ from host geometry')


def _require_identity_rotation(value, label):
    """Canonical GP solids are axis-aligned: their native Solid pose must be too."""
    if (not isinstance(value, (tuple, list)) or len(value) != 4 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in value)):
        raise NativeGeometryMismatch(f'{label}: finite 4-value rotation required')
    # The scene generators emit no Solid.rotation (Webots default angle 0).
    # Reject nonzero rotations even if translation and both Box sizes match.
    if abs(value[3]) > _TOLERANCE_M:
        raise NativeGeometryMismatch(f'{label}: unexpected native Solid rotation')


def _node_field(node, field):
    value = node.getField(field)
    if value is None:
        raise NativeGeometryMismatch(f'missing Webots field: {field}')
    return value


def _solid_geometry(node, expectation):
    name = expectation.name
    if node.getTypeName() != 'Solid':
        raise NativeGeometryMismatch(f'{name}: not a Solid')
    if _node_field(node, 'locked').getSFBool() is not True:
        raise NativeGeometryMismatch(f'{name}: body is not locked')
    _close(_node_field(node, 'translation').getSFVec3f(),
           expectation.translation, f'{name} translation')
    _require_identity_rotation(_node_field(node, 'rotation').getSFRotation(),
                               f'{name} rotation')
    collider = _node_field(node, 'boundingObject').getSFNode()
    if collider is None or collider.getTypeName() != 'Box':
        raise NativeGeometryMismatch(f'{name}: missing Box collider')
    _close(_node_field(collider, 'size').getSFVec3f(),
           expectation.size, f'{name} collider size')
    children = _node_field(node, 'children')
    if children.getCount() != 1:
        raise NativeGeometryMismatch(f'{name}: expected one visible Shape')
    shape = children.getMFNode(0)
    if shape is None or shape.getTypeName() != 'Shape':
        raise NativeGeometryMismatch(f'{name}: invisible or invalid child')
    visible = _node_field(shape, 'geometry').getSFNode()
    if visible is None or visible.getTypeName() != 'Box':
        raise NativeGeometryMismatch(f'{name}: visible geometry is not Box')
    _close(_node_field(visible, 'size').getSFVec3f(),
           expectation.size, f'{name} visible size')


def _reject_nested_course_solids(root_nodes):
    """Forbid reserved GP physical bodies hidden under scene graph wrappers.

    All expected GP_V2 bodies have to be direct root children. The bounded
    traversal also visits Group/Transform/Pose children and the SFNode fields
    that can contain colliders; a hidden descendant must not evade inventory.
    """
    pending = [(node, 0) for node in root_nodes]
    visited = 0
    while pending:
        node, depth = pending.pop()
        visited += 1
        if node is None or visited > 8192 or depth > 64:
            raise NativeGeometryMismatch('unreadable/oversized native scene graph')
        if depth:
            name = node.getDef()
            if isinstance(name, str) and name.startswith(_PREFIXES):
                raise NativeGeometryMismatch(
                    f'nested Grand Prix physical DEF: {name}')
        children = node.getField('children')
        if children is not None:
            count = children.getCount()
            if type(count) is not int or not 0 <= count <= 4096:
                raise NativeGeometryMismatch('invalid native child inventory')
            for index in range(count):
                pending.append((children.getMFNode(index), depth + 1))
        for field_name in ('endPoint', 'boundingObject', 'geometry'):
            field = node.getField(field_name)
            if field is not None:
                nested = field.getSFNode()
                if nested is not None:
                    pending.append((nested, depth + 1))


def assert_native_solids_match(supervisor, required):
    """Verify direct-root GP_V2 physical bodies; return no mission authority.

    Reject absent, duplicate, extra and modified Grand Prix body DEFs, including
    a cosmetic Box without its matching collider. Non-physical guides/tape are
    intentionally outside the reserved physical-name prefixes.
    """
    required = tuple(required)
    if not required or any(not isinstance(v, RequiredSolid) for v in required):
        raise NativeGeometryMismatch('nonempty verified host manifest required')
    expected = {entry.name: entry for entry in required}
    if len(expected) != len(required):
        raise NativeGeometryMismatch('duplicate required Solid DEF')
    try:
        children = _node_field(supervisor.getRoot(), 'children')
        count = children.getCount()
        if type(count) is not int or not 0 <= count <= 4096:
            raise NativeGeometryMismatch('invalid root children count')
        observed = {}
        root_nodes = []
        for index in range(count):
            node = children.getMFNode(index)
            root_nodes.append(node)
            name = node.getDef() if node is not None else None
            if isinstance(name, str) and name.startswith(_PREFIXES):
                if name in observed:
                    raise NativeGeometryMismatch(f'duplicate native DEF: {name}')
                observed[name] = node
        _reject_nested_course_solids(root_nodes)
        if set(observed) != set(expected):
            raise NativeGeometryMismatch('missing/unexpected GP_V2 native solids: '
                                         f'{sorted(set(expected)-set(observed))}; '
                                         f'{sorted(set(observed)-set(expected))}')
        for name, spec in expected.items():
            _solid_geometry(observed[name], spec)
    except NativeGeometryMismatch:
        raise
    except (AttributeError, TypeError, ValueError, IndexError) as error:
        raise NativeGeometryMismatch('unreadable/incomplete Supervisor geometry') from error
