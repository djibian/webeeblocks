"""Fail-closed Webots collider preflight for a canonical variable Grand Prix.

This does not grant admission/READY or qualify real Webots contacts. The
native evaluator must reconstruct CoursePlan independently, build the same
expected numeric geometry as the world, verify it here, and only then establish
its separately attempt-bound readiness with the native flight controller.
"""
from dataclasses import dataclass
from tools.grand_prix.native_field_lookup_v2 import NativeFieldLookup
import math
from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier
from tools.grand_prix.route_solid_v2 import corner_boxes, HEIGHT as CORNER_HEIGHT
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes
from tools.grand_prix.course_footprint_v2 import course_rectangles


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


def _native_enabled(value):
    """R2025a Python Supervisor reports SFBool as integer 0/1.

    Accept the exact enabled value, not arbitrary truthy objects; our host
    fakes also use Python booleans. Never turn malformed field values into
    valid collision geometry.
    """
    return value is True or (type(value) is int and value == 1)


def _verify_floor(node, route, fields):
    """A permitted floor is the locked horizontal Plane at z=0, not an obstacle."""
    position = tuple(node.getPosition())
    _vector(position)
    locked = node.getBaseNodeField('locked')
    rotation = fields.get(node, 'rotation')
    rotation = rotation.getSFRotation() if rotation else None
    field = node.getBaseNodeField('boundingObject')
    body = field.getSFNode() if field else None
    # Preserve every native rejection. The exact R2025a Floor PROTO readback
    # is retained in the failure artifact when a native preflight fails,
    # allowing geometry vs Supervisor API mismatch to be distinguished.
    native_locked = locked.getSFBool() if locked is not None else None
    native_shape = body.getTypeName() if body is not None else None
    if (abs(position[2]) > 1e-9 or locked is None or
            not _native_enabled(native_locked) or
            not isinstance(rotation, (list, tuple)) or len(rotation) != 4 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in rotation) or
            abs(rotation[3]) > 1e-9 or body is None or native_shape != 'Plane'):
        raise RuntimeError(
            'floor must be the locked horizontal z=0 Plane; native readback '
            f'position={position!r} locked={native_locked!r} '
            f'rotation={rotation!r} boundingObject={native_shape!r}')
    size = body.getField('size')
    size = size.getSFVec2f() if size else None
    if (not isinstance(size, (list, tuple)) or len(size) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in size)):
        raise RuntimeError('invalid native floor extent')
    for xmin, ymin, xmax, ymax in course_rectangles(route):
        if not (position[0]-size[0]/2 <= xmin <= xmax <= position[0]+size[0]/2 and
                position[1]-size[1]/2 <= ymin <= ymax <= position[1]+size[1]/2):
            raise RuntimeError('native floor does not cover the full course')


def _read_scene_boxes(root_nodes, expected_names, route, fields, inspect=None,
                      *, verified_model_edges=False):
    """Reject unlisted physics, including bodies outside the GP_V2 namespace.

    Physical GP_V2 solids are direct root children by contract. Fail closed
    on cycles, unreadable nodes and oversized traversal rather than accepting
    a visually plausible scene with an extra collidable descendant.
    """
    pending = [(node, 0, False) for node in root_nodes]
    visited = 0
    models = set()
    boxes = {}
    evaluator_seen = False
    while pending:
        node, depth, under_guide = pending.pop()
        visited += 1
        if node is None or visited > 8192 or depth > 64:
            raise RuntimeError('unreadable/oversized native course scene graph')
        name = node.getDef()
        kind = node.getTypeName()
        base = node.getBaseTypeName()
        if inspect is not None:
            inspect(node, depth)
        if not isinstance(base, str) or not base:
            raise RuntimeError('unreadable native base node type')
        # The installed, pinned R2025a models are the only opaque physics
        # roots. Their editable extension slots remain subject to traversal.
        # Source/asset provenance and live reset are separate preconditions
        # of future admission; this static function grants no READY.
        model = depth == 0 and kind in ('Floor', 'Crazyflie')
        if model:
            if (not node.isProto() or kind in models or
                    base != {'Floor': 'Solid', 'Crazyflie': 'Robot'}[kind]):
                raise RuntimeError('duplicate or invalid pinned scene model')
            models.add(kind)
            if kind == 'Crazyflie':
                field = fields.get(node, 'name')
                if field is None or field.getSFString() != 'Crazyflie WebeeBlocks':
                    raise RuntimeError('unrecognized native vehicle')
            else:
                _verify_floor(node, route, fields)
            # The pinned Floor/Crazyflie checks above are independent of the
            # export. Their exposed node parameters are covered by the exact
            # bulk comparison after a full traversal with no nested PROTO.
            if verified_model_edges:
                continue
        physical = fields.get(node, 'boundingObject')
        if physical is None and node.isProto() and not model:
            physical = node.getBaseNodeField('boundingObject')
        collider = physical.getSFNode() if physical is not None else None
        has_collider = collider is not None
        evaluator = (depth == 0 and name == 'GP_ROUTE_EVALUATOR' and
                     kind == 'Robot' and base == 'Robot' and not has_collider)
        if name == 'GP_ROUTE_EVALUATOR':
            if not evaluator or evaluator_seen:
                raise RuntimeError('invalid or duplicate native course evaluator')
            evaluator_seen = True
        listed = depth == 0 and name in expected_names and kind == 'Solid'
        if not (model or listed or evaluator) and (
                base in ('Solid', 'Robot', 'Fluid') or has_collider):
            raise RuntimeError('unlisted native physical body: ' + str(name))
        guide = (isinstance(name, str) and
                 name.startswith(('GP_V2_WHITE_', 'GP_V2_RED_',
                                  'GP_V2_COURSE_RED_')))
        if guide and kind != 'Pose':
            raise RuntimeError('course guide is not a visual Pose: ' + name)
        if guide and has_collider:
            raise RuntimeError('collidable course guide: ' + name)
        if under_guide and kind == 'Solid':
            raise RuntimeError('hidden Solid under visual course guide')
        under_guide = under_guide or guide
        if depth and isinstance(name, str) and name.startswith('GP_V2_'):
            if (kind == 'Solid' or
                    name.startswith(('GP_V2_L_', 'GP_V2_H_',
                                     'GP_V2_FINAL_'))):
                raise RuntimeError('nested reserved course body: ' + name)
        display = None
        for field_name in ('children', 'extensionSlot', 'choice'):
            children = fields.get(node, field_name)
            if children is None and node.isProto() and not model:
                children = node.getBaseNodeField(field_name)
            if children is not None:
                count = children.getCount()
                if type(count) is not int or not 0 <= count <= 4096:
                    raise RuntimeError('invalid nested course child inventory')
                nodes = [children.getMFNode(i) for i in range(count)]
                if listed and field_name == 'children':
                    display = nodes
                pending.extend((child, depth + 1, under_guide) for child in nodes)
        if listed:
            boxes[name] = (node, collider, display)
        if has_collider:
            pending.append((collider, depth + 1, under_guide))
        for field_name in ('endPoint', 'geometry'):
            field = fields.get(node, field_name)
            if field is None and node.isProto() and not model:
                field = node.getBaseNodeField(field_name)
            if field is not None:
                nested = field.getSFNode()
                if nested is not None:
                    pending.append((nested, depth + 1, under_guide))

    if models != {'Floor', 'Crazyflie'}:
        missing = ', '.join(sorted({'Floor', 'Crazyflie'} - models))
        raise RuntimeError('missing required pinned scene model: ' + missing)
    return boxes


def _read_native_root_nodes(supervisor):
    """Read the root inventory once per check, never across native steps."""
    children, count = _root_inventory(supervisor.getRoot())
    nodes = [children.getMFNode(index) for index in range(count)]
    if any(node is None for node in nodes):
        raise RuntimeError('unreadable native root node')
    return nodes


def _root_inventory(root):
    children = root.getField('children')
    count = children.getCount() if children is not None else None
    if type(count) is not int or not 0 < count < 8192:
        raise RuntimeError('invalid native root inventory')
    return children, count


def verify_native_boxes(supervisor, course, boxes):
    """Require exactly the expected physical solids, locked and observable.

    Independently derive exact expected positions and dimensions from the
    canonical CoursePlan and physical geometry primitives. A manifest forged
    from scene readback must fail even if it matches every observed collider.
    This still provides no READY or real R2025a contact qualification.
    """
    canonical = canonical_native_boxes(course)
    if not isinstance(boxes, tuple) or len(boxes) != len(canonical):
        raise ValueError('incomplete native collider manifest')
    if (any(type(box) is not NativeBox for box in boxes) or
            tuple(box.name for box in boxes) != tuple(box.name for box in canonical)):
        raise ValueError('native collider manifest names/order mismatch')
    for box, expected in zip(boxes, canonical):
        _vector(box.position)
        _vector(box.size, positive=True)
        if (_serialized(box.position) != _serialized(expected.position) or
                _serialized(box.size) != _serialized(expected.size)):
            raise ValueError('native collider manifest differs from canonical geometry')
    _verify_scene_boxes(course, canonical, _read_native_root_nodes(supervisor), NativeFieldLookup())


def _verify_scene_boxes(course, boxes, root_nodes, fields, inspect=None):
    expected_names = {box.name for box in boxes}
    # Reject unexpected course Solids too: a hidden collidable object is not
    # made safe by verifying all the expected objects are present.
    scene_names = []
    for node in root_nodes:
        name = node.getDef()
        if name and name.startswith('GP_V2_'):
            if node.getTypeName() == 'Solid':
                # Reject even an unexpected GP_V2_EXTRA physical Solid.
                scene_names.append(name)
            elif name.startswith(('GP_V2_L_', 'GP_V2_H_', 'GP_V2_FINAL_')):
                raise RuntimeError('non-Solid using a reserved physical DEF')
            elif not (name.startswith(('GP_V2_WHITE_', 'GP_V2_RED_',
                                       'GP_V2_COURSE_RED_')) and
                      node.getTypeName() == 'Pose'):
                # The GP_V2_* namespace is reserved for the exact physical
                # inventory and non-colliding visual guides. An unknown Group
                # could otherwise conceal an unprefixed Solid below it.
                raise RuntimeError('unexpected reserved course node: ' + name)
            # White/red course guides are non-colliding Pose nodes.
    live_boxes = _read_scene_boxes(root_nodes, expected_names, course.route, fields, inspect)
    if len(scene_names) != len(set(scene_names)) or set(scene_names) != expected_names:
        raise RuntimeError('native scene has missing/extra/duplicate mission Solids')
    _verify_box_measurements(boxes, live_boxes, fields)
    return live_boxes


def _verify_box_measurements(boxes, live_boxes, fields, *, verify_visual=True):
    """Always read physics; optionally reuse an unchanged, verified visual tree.

    verify_visual=False is legal only on the NativeSceneSnapshot fast path:
    the exact live root export still matches a prior FULL visual check, with
    every visual field included in the signature. It is never a scene admission
    shortcut and never caches a physical collider value.
    """
    for box in boxes:
        node, collider, display = live_boxes[box.name]
        locked = fields.get(node, 'locked')
        if locked is None or not _native_enabled(locked.getSFBool()):
            raise RuntimeError('movable course collider: ' + box.name)
        if not _equal(node.getPosition(), box.position):
            raise RuntimeError('native collider world pose mismatch: ' + box.name)
        rotation = fields.get(node, 'rotation')
        actual_rotation = rotation.getSFRotation() if rotation is not None else None
        if (not isinstance(actual_rotation, (tuple, list)) or
                len(actual_rotation) != 4 or
                any(type(v) not in (float, int) or not math.isfinite(v)
                    for v in actual_rotation) or
                abs(actual_rotation[3]) > 1e-6):
            # Current host GP Solids use Webots' default identity rotation.
            raise RuntimeError('rotated/malformed native collider: ' + box.name)
        if collider is None or collider.getTypeName() != 'Box':
            raise RuntimeError('missing physical Box: ' + box.name)
        size_field = fields.get(collider, 'size')
        if size_field is None or not _equal(size_field.getSFVec3f(), box.size):
            raise RuntimeError('physical Box dimensions mismatch: ' + box.name)
        if not verify_visual:
            # Visual topology/size was validated in the full read that stored
            # this snapshot, and is covered by today's unchanged full export.
            # This branch MUST NOT skip locked/pose/rotation/physical Box reads.
            continue
        if display is None or len(display) != 1:
            raise RuntimeError('missing/extra native child under ' + box.name)
        child = display[0]
        if child is None or child.getTypeName() != 'Shape':
            raise RuntimeError('unexpected native child under ' + box.name)
        geometry = fields.get(child, 'geometry')
        visible = geometry.getSFNode() if geometry else None
        if visible is None or visible.getTypeName() != 'Box':
            raise RuntimeError('invisible or ambiguous rendered collider: ' + box.name)
        visual_size = fields.get(visible, 'size')
        if visual_size is None or not _equal(visual_size.getSFVec3f(), box.size):
            raise RuntimeError('rendered and physical Box mismatch: ' + box.name)
