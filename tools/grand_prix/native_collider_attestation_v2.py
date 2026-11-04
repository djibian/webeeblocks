"""Fail-closed, host-only Supervisor checks for variable Grand Prix colliders.

This verifies only the *expected named physical boxes*. It does not attest
other scene nodes, contacts, the full flight boundary, RESET, evaluator liveness
or the independent 210000-ms LAND authority. It must never issue READY or PASS.
"""
from dataclasses import dataclass
import math

from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier
from tools.grand_prix.route_solid_v2 import corner_boxes, HEIGHT as L_HEIGHT
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes

TOL = 1e-5


class ColliderAttestationError(ValueError):
    """Required physical evidence is absent, inconsistent, or untrusted."""


@dataclass(frozen=True)
class ColliderExpectation:
    name: str
    position: tuple[float, float, float]
    size: tuple[float, float, float]


def expected_course_colliders(course):
    """Consume only canonical host geometry; never an AST-supplied route."""
    if type(course) is not CoursePlan:
        raise ColliderAttestationError('canonical CoursePlan required')
    try:
        if course_from_identifier(course.identifier) != course:
            raise ColliderAttestationError('forged CoursePlan')
        boxes = [ColliderExpectation(
            box.name, (box.x, box.y, L_HEIGHT / 2),
            (box.sx, box.sy, L_HEIGHT))
            for box in corner_boxes(course.route)]
        boxes.extend(ColliderExpectation(
            box.name, (box.x, box.y, box.z),
            (box.sx, box.sy, box.sz)) for box in open_h_boxes(course))
        boxes.extend(ColliderExpectation(
            box.name, (box.x, box.y, box.z),
            (box.sx, box.sy, box.sz)) for box in terminal_boxes(course.route))
    except (TypeError, ValueError, AttributeError) as error:
        raise ColliderAttestationError('invalid canonical physical manifest') from error
    names = [box.name for box in boxes]
    if len(boxes) != 8 + 3 * course.count or len(set(names)) != len(names):
        raise ColliderAttestationError('incomplete or duplicate physical manifest')
    return tuple(boxes)


def _finite_tuple(value, size):
    if (not isinstance(value, (list, tuple)) or len(value) != size or
            any(type(number) not in (int, float) or not math.isfinite(number)
                for number in value)):
        raise ColliderAttestationError('finite native vector required')
    return tuple(float(number) for number in value)


def _same(value, expected):
    return all(abs(actual - wanted) <= TOL for actual, wanted in zip(
        _finite_tuple(value, len(expected)), expected))


def attest_native_course_colliders(supervisor, course):
    """Refuse missing, moved, rotated, resized or nonphysical expected Solids.

    The caller must separately prove a fresh exact-attempt evaluator, complete
    physical scene, contact/swept safety and independent deadline before READY.
    This function returns only a tuple of verified DEF identifiers, not a grant.
    """
    expected = expected_course_colliders(course)
    if not callable(getattr(supervisor, 'getFromDef', None)):
        raise ColliderAttestationError('native Supervisor required')
    for box in expected:
        try:
            node = supervisor.getFromDef(box.name)
            if node is None or node.getTypeName() != 'Solid':
                raise ColliderAttestationError('missing physical Solid')
            locked = node.getField('locked')
            translation = node.getField('translation')
            rotation = node.getField('rotation')
            bounding = node.getField('boundingObject')
            if any(field is None for field in (locked, translation, rotation, bounding)):
                raise ColliderAttestationError('missing Solid geometry field')
            collider = bounding.getSFNode()
            if (locked.getSFBool() is not True or
                    not _same(translation.getSFVec3f(), box.position) or
                    not _same(node.getPosition(), box.position) or
                    collider is None or collider.getTypeName() != 'Box'):
                raise ColliderAttestationError('wrong native Solid pose/lock/shape')
            angle = _finite_tuple(rotation.getSFRotation(), 4)[3]
            if abs(angle) > TOL:
                raise ColliderAttestationError('unexpected rotated collider')
            size_field = collider.getField('size')
            if size_field is None or not _same(size_field.getSFVec3f(), box.size):
                raise ColliderAttestationError('wrong native collider size')
        except Exception as error:
            raise ColliderAttestationError(
                'physical collider attestation failed: ' + box.name) from error
    return tuple(box.name for box in expected)
