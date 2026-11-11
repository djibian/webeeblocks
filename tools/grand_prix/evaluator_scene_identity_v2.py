"""Strict native scene/identity check for the variable-course Supervisor.

This checks a Webots scene *only*. It does not observe another robot's
DistanceSensors, certify contacts/RESET, return READY, or authorize flight.
The native evaluator must separately establish all live admission evidence.
"""
from tools.grand_prix.native_collider_contract_v2 import (
    canonical_native_boxes, _read_native_root_nodes, _read_scene_boxes, _root_inventory,
    _verify_box_measurements, _verify_scene_boxes,
)
from tools.grand_prix.route_courses_v2 import course_from_identifier
from tools.grand_prix.native_sfbbool_v2 import enabled
from tools.grand_prix.native_field_lookup_v2 import NativeFieldLookup
from tools.grand_prix.native_scene_snapshot_v2 import read_scene_signature


def _field_text(node, name, fields):
    field = fields.get(node, name)
    if field is None:
        raise RuntimeError('missing native ' + name)
    value = field.getSFString()
    if type(value) is not str:
        raise RuntimeError('invalid native ' + name)
    return value


def _one_arg(node):
    field = node.getField('controllerArgs')
    if field is None or field.getCount() != 1:
        raise RuntimeError('native route requires one controllerArgs ID')
    value = field.getMFString(0)
    if type(value) is not str:
        raise RuntimeError('invalid native route controllerArgs')
    return value


def _supervisor(node, fields):
    field = fields.get(node, 'supervisor')
    if field is None or not enabled(field.getSFBool()):
        raise RuntimeError('native route supervisor authority missing')


def check_native_evaluator_scene(supervisor, identifier):
    """Check the canonical scene without granting flight authority."""
    read_native_evaluator_scene(supervisor, course_from_identifier(identifier), NativeFieldLookup())


def read_native_evaluator_scene(supervisor, course, fields, snapshot=None):
    """Reject noncanonical host identities/colliders. Return *no* authority.

    The calling native evaluator must be the unique GP_ROUTE_EVALUATOR Robot;
    the student flight controller must be the single pinned Crazyflie PROTO.
    Native sensor samples and fresh RESET are outside this static check.
    """
    identifier = course.identifier
    if supervisor.getBasicTimeStep() != 8:
        raise RuntimeError('variable Grand Prix requires 8 ms Webots timestep')
    evaluator = supervisor.getSelf()
    found = supervisor.getFromDef('GP_ROUTE_EVALUATOR')
    if (evaluator is None or found is None or
            evaluator.getDef() != 'GP_ROUTE_EVALUATOR' or
            evaluator.isProto() or
            evaluator.getTypeName() != 'Robot' or
            evaluator.getBaseTypeName() != 'Robot' or
            evaluator.getId() != found.getId()):
        raise RuntimeError('native evaluator must own exact root DEF')
    _supervisor(evaluator, fields)
    if (_one_arg(evaluator) != identifier or
            _field_text(evaluator, 'controller', fields) != 'grand_prix_route_evaluator'):
        raise RuntimeError('native evaluator identity differs from canonical route')
    if snapshot is None:
        root_nodes = _read_native_root_nodes(supervisor)
        vehicle = _read_vehicle(root_nodes, identifier, fields)
        _verify_scene_boxes(course, canonical_native_boxes(course), root_nodes, fields)
        return vehicle
    if snapshot.course is not course:
        raise RuntimeError('native scene snapshot course changed')
    return _check_snapshot(supervisor, fields, snapshot)


def _read_vehicle(root_nodes, identifier, fields):
    vehicles = []
    for node in root_nodes:
        name = fields.get(node, 'name')
        if name is not None and name.getSFString() == 'Crazyflie WebeeBlocks':
            vehicles.append(node)
    if len(vehicles) != 1:
        raise RuntimeError('missing or duplicated canonical Crazyflie')
    vehicle = vehicles[0]
    if (not vehicle.isProto() or vehicle.getTypeName() != 'Crazyflie' or
            vehicle.getBaseTypeName() != 'Robot'):
        raise RuntimeError('unknown native vehicle PROTO')
    _supervisor(vehicle, fields)
    if (_one_arg(vehicle) != identifier or
            _field_text(vehicle, 'controller', fields) != 'grand_prix_route_flight' or
            _field_text(vehicle, 'window', fields) != 'grand_prix_route_v2'):
        raise RuntimeError('native flight identity differs from canonical route')
    return vehicle


def _check_snapshot(supervisor, fields, snapshot):
    course, boxes = snapshot.course, snapshot.expected_boxes
    root = supervisor.getRoot()
    signature = read_scene_signature(root)
    children, count = _root_inventory(root)
    if snapshot.matches(signature, count):
        # PROTO internals are not represented by the VRML export. Resolve
        # and reinspect each opaque root and the dynamic evaluator every tick.
        opaque = [children.getMFNode(index) for index, _ in snapshot.opaque_roots]
        if all(node is not None and node.getId() == node_id
               for node, (_, node_id) in zip(opaque, snapshot.opaque_roots)):
            vehicle = _read_vehicle(opaque, course.identifier, fields)
            _read_scene_boxes(opaque, set(), course.route, fields, verified_model_edges=True)
            # The exact root export still includes ALL visual Box topology and
            # dimensions. A previous full check established their validity;
            # re-reading those visual fields would repeat already-certified
            # information. Physical locks, poses, rotations and Box extents
            # are nevertheless freshly read on EVERY tick.
            _verify_box_measurements(boxes, snapshot.boxes, fields, verify_visual=False)
            return vehicle

    root_nodes = [children.getMFNode(index) for index in range(count)]
    if any(node is None for node in root_nodes):
        raise RuntimeError('unreadable native root node')
    vehicle = _read_vehicle(root_nodes, course.identifier, fields)

    nested_proto = False

    def inspect(node, depth):
        nonlocal nested_proto
        if depth and node.isProto():
            nested_proto = True

    live_boxes = _verify_scene_boxes(course, boxes, root_nodes, fields, inspect)
    opaque = tuple((index, node.getId()) for index, node in enumerate(root_nodes)
                   if node.isProto() or node.getDef() == 'GP_ROUTE_EVALUATOR')
    if (signature is None or nested_proto or
            any(type(node_id) is not int or node_id <= 0 for _, node_id in opaque) or
            read_scene_signature(root) != signature):
        snapshot.record(None, None, None, ())
    else:
        snapshot.record(signature, count, live_boxes, opaque)
    return vehicle
