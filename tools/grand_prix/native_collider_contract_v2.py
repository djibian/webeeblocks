"""Fail-closed Webots collider preflight for a canonical variable Grand Prix.

This does not grant admission/READY or qualify real Webots contacts. The
native evaluator must reconstruct CoursePlan independently, build the same
expected numeric geometry as the world, verify it here, and only then establish
its separately attempt-bound readiness with the native flight controller.
"""
from dataclasses import dataclass
import math
from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier
from tools.grand_prix.route_solid_v2 import corner_boxes, HEIGHT as CORNER_HEIGHT
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes


@dataclass(frozen=True)
class NativeBox:
    name: str
    position: tuple[float, float, float]
    size: tuple[float, float, float]


def required_box_names(course):
    """Exhaustive physical mission inventory: two L, open H and closed H."""
    if type(course) is not CoursePlan:
        raise ValueError('canonical CoursePlan required')
    # Reconstruct from the canonical identifier, not untrusted mutable geometry.
    if course_from_identifier(course.identifier) != course:
        raise ValueError('forged or inconsistent CoursePlan')
    corners = tuple(f'GP_V2_L_{i}_{part}' for i in range(2) for part in range(2))
    gates = tuple(f'GP_V2_H_{g.leg_index}_{part}' for g in course.gates
                  for part in ('LEFT', 'RIGHT', 'BEAM'))
    terminal = tuple('GP_V2_FINAL_' + part
                     for part in ('LEFT', 'RIGHT', 'BEAM', 'PANEL'))
    return corners + gates + terminal


def canonical_native_boxes(course):
    """Rebuild every expected physical Box from the canonical host geometry.

    An evaluator must not make an arbitrary, self-consistent scene/readback
    manifest authoritative. This remains a static preflight, NOT READY.
    """
    expected_names = required_box_names(course)
    result = []
    for box in corner_boxes(course.route):
        result.append(NativeBox(box.name, (box.x, box.y, CORNER_HEIGHT / 2),
                                (box.sx, box.sy, CORNER_HEIGHT)))
    for box in open_h_boxes(course):
        result.append(NativeBox(box.name, (box.x, box.y, box.z),
                                (box.sx, box.sy, box.sz)))
    for box in terminal_boxes(course.route):
        result.append(NativeBox(box.name, (box.x, box.y, box.z),
                                (box.sx, box.sy, box.sz)))
    if tuple(box.name for box in result) != expected_names:
        raise ValueError('canonical course geometry inventory mismatch')
    return tuple(result)


def _serialized(vector):
    """Exact 6-decimal VRML geometry, never a free safety tolerance."""
    return tuple(float(f'{value:.6f}') for value in vector)


def _vector(vector, *, positive=False):
    if (not isinstance(vector, tuple) or len(vector) != 3 or
            any(type(v) not in (float, int) or not math.isfinite(v) or
                (positive and v <= 0) for v in vector)):
        raise ValueError('finite three-dimensional collider vector required')
    return vector


def _equal(actual, expected):
    """Compare against six-decimal VRML serialization, not a loose tolerance."""
    expected = tuple(float(f'{v:.6f}') for v in expected)
    try:
        return len(actual) == 3 and all(
            type(a) in (float, int) and math.isfinite(a) and
            math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
            for a, b in zip(actual, expected))
    except (TypeError, ValueError):
        return False


def _reject_nested_course_nodes(root_nodes):
    """Reject GP_V2 physics hidden under a Group/Pose/Transform/SFNode.

    Physical GP_V2 solids are direct root children by contract. Fail closed
    on cycles, unreadable nodes and oversized traversal rather than accepting
    a visually plausible scene with an extra collidable descendant.
    """
    pending = [(node, 0, False) for node in root_nodes]
    visited = 0
    while pending:
        node, depth, under_guide = pending.pop()
        visited += 1
        if node is None or visited > 8192 or depth > 64:
            raise RuntimeError('unreadable/oversized native course scene graph')
        name = node.getDef()
        kind = node.getTypeName()
        guide = (isinstance(name, str) and
                 name.startswith(('GP_V2_WHITE_', 'GP_V2_RED_',
                                  'GP_V2_COURSE_RED_')))
        if guide and kind != 'Pose':
            raise RuntimeError('course guide is not a visual Pose: ' + name)
        if under_guide and kind == 'Solid':
            raise RuntimeError('hidden Solid under visual course guide')
        under_guide = under_guide or guide
        if depth and isinstance(name, str) and name.startswith('GP_V2_'):
            if (kind == 'Solid' or
                    name.startswith(('GP_V2_L_', 'GP_V2_H_',
                                     'GP_V2_FINAL_'))):
                raise RuntimeError('nested reserved course body: ' + name)
        children = node.getField('children')
        if children is not None:
            count = children.getCount()
            if type(count) is not int or not 0 <= count <= 4096:
                raise RuntimeError('invalid nested course child inventory')
            for i in range(count):
                pending.append((children.getMFNode(i), depth + 1, under_guide))
        for field_name in ('endPoint', 'boundingObject', 'geometry'):
            field = node.getField(field_name)
            if field is not None:
                nested = field.getSFNode()
                if nested is not None:
                    if guide and field_name == 'boundingObject':
                        raise RuntimeError('collidable course guide: ' + name)
                    pending.append((nested, depth + 1, under_guide))


def verify_native_boxes(supervisor, course, boxes):
    """Require exactly the expected physical solids, locked and observable.

    Independently derive exact expected positions and dimensions from the
    canonical CoursePlan and physical geometry primitives. A manifest forged
    from scene readback must fail even if it matches every observed collider.
    This still provides no READY or real R2025a contact qualification.
    """
    canonical = canonical_native_boxes(course)
    expected_names = tuple(box.name for box in canonical)
    if not isinstance(boxes, tuple) or len(boxes) != len(expected_names):
        raise ValueError('incomplete native collider manifest')
    if (any(type(box) is not NativeBox for box in boxes) or
            tuple(box.name for box in boxes) != expected_names):
        raise ValueError('native collider manifest names/order mismatch')
    for box, expected in zip(boxes, canonical):
        _vector(box.position)
        _vector(box.size, positive=True)
        if (_serialized(box.position) != _serialized(expected.position) or
                _serialized(box.size) != _serialized(expected.size)):
            raise ValueError('native collider manifest differs from canonical geometry')

    # Reject unexpected course Solids too: a hidden collidable object is not
    # made safe by verifying all the expected objects are present.
    children = supervisor.getRoot().getField('children')
    scene_names = []
    root_nodes = []
    for index in range(children.getCount()):
        node = children.getMFNode(index)
        root_nodes.append(node)
        name = node.getDef()
        if name and name.startswith('GP_V2_'):
            if node.getTypeName() == 'Solid':
                # Reject even an unexpected GP_V2_EXTRA physical Solid.
                scene_names.append(name)
            elif name.startswith(('GP_V2_L_', 'GP_V2_H_', 'GP_V2_FINAL_')):
                raise RuntimeError('non-Solid using a reserved physical DEF')
            # White/red course guides are non-colliding Pose nodes.
    _reject_nested_course_nodes(root_nodes)
    if len(scene_names) != len(set(scene_names)) or set(scene_names) != set(expected_names):
        raise RuntimeError('native scene has missing/extra/duplicate mission Solids')

    for box in boxes:
        node = supervisor.getFromDef(box.name)
        if node is None or node.getTypeName() != 'Solid':
            raise RuntimeError('missing or non-Solid course collider: ' + box.name)
        locked = node.getField('locked')
        if locked is None or locked.getSFBool() is not True:
            raise RuntimeError('movable course collider: ' + box.name)
        if not _equal(node.getPosition(), box.position):
            raise RuntimeError('native collider world pose mismatch: ' + box.name)
        rotation = node.getField('rotation')
        actual_rotation = rotation.getSFRotation() if rotation is not None else None
        if (not isinstance(actual_rotation, (tuple, list)) or
                len(actual_rotation) != 4 or
                any(type(v) not in (float, int) or not math.isfinite(v)
                    for v in actual_rotation) or
                abs(actual_rotation[3]) > 1e-6):
            # Current host GP Solids use Webots' default identity rotation.
            raise RuntimeError('rotated/malformed native collider: ' + box.name)
        field = node.getField('boundingObject')
        collider = field.getSFNode() if field else None
        if collider is None or collider.getTypeName() != 'Box':
            raise RuntimeError('missing physical Box: ' + box.name)
        size_field = collider.getField('size')
        if size_field is None or not _equal(size_field.getSFVec3f(), box.size):
            raise RuntimeError('physical Box dimensions mismatch: ' + box.name)
        display = node.getField('children')
        if display is None or display.getCount() != 1:
            raise RuntimeError('missing/extra native child under ' + box.name)
        child = display.getMFNode(0)
        if child is None or child.getTypeName() != 'Shape':
            raise RuntimeError('unexpected native child under ' + box.name)
        geometry = child.getField('geometry')
        visible = geometry.getSFNode() if geometry else None
        if visible is None or visible.getTypeName() != 'Box':
            raise RuntimeError('invisible or ambiguous rendered collider: ' + box.name)
        visual_size = visible.getField('size')
        if visual_size is None or not _equal(visual_size.getSFVec3f(), box.size):
            raise RuntimeError('rendered and physical Box mismatch: ' + box.name)
    # Explicitly return *no* authority token: READY is a separate live
    # handshake following validated RESET, never a static function result.
    return None
