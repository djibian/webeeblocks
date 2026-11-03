"""Fail-closed Webots collider preflight for a canonical variable Grand Prix.

This does not grant admission/READY or qualify real Webots contacts. The
native evaluator must reconstruct CoursePlan independently, build the same
expected numeric geometry as the world, verify it here, and only then establish
its separately attempt-bound readiness with the native flight controller.
"""
from dataclasses import dataclass
import math
from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier


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


def verify_native_boxes(supervisor, course, boxes):
    """Require exactly the expected physical solids, locked and observable.

    The boxes MUST come from the trusted world/evaluator's common numeric
    geometry, not an AST, browser value or scene readback. Enforce complete
    CoursePlan-derived *names* here so omitting a whole H cannot make a
    falsely green, self-consistent reduced manifest.
    """
    expected_names = required_box_names(course)
    if not isinstance(boxes, tuple) or len(boxes) != len(expected_names):
        raise ValueError('incomplete native collider manifest')
    if (any(type(box) is not NativeBox for box in boxes) or
            tuple(box.name for box in boxes) != expected_names):
        raise ValueError('native collider manifest names/order mismatch')
    for box in boxes:
        _vector(box.position)
        _vector(box.size, positive=True)

    # Reject unexpected course Solids too: a hidden collidable object is not
    # made safe by verifying all the expected objects are present.
    children = supervisor.getRoot().getField('children')
    scene_names = []
    for index in range(children.getCount()):
        node = children.getMFNode(index)
        name = node.getDef()
        if name and name.startswith(('GP_V2_L_', 'GP_V2_H_', 'GP_V2_FINAL_')):
            if node.getTypeName() != 'Solid':
                raise RuntimeError('non-Solid using a reserved physical DEF')
            scene_names.append(name)
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
