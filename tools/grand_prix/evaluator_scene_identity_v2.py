"""Strict native scene/identity check for the variable-course Supervisor.

This checks a Webots scene *only*. It does not observe another robot's
DistanceSensors, certify contacts/RESET, return READY, or authorize flight.
The native evaluator must separately establish all live admission evidence.
"""
from tools.grand_prix.native_collider_contract_v2 import (
    canonical_native_boxes, _read_native_root_nodes, _verify_scene_boxes,
)
from tools.grand_prix.route_courses_v2 import course_from_identifier
from tools.grand_prix.native_sfbbool_v2 import enabled
from tools.grand_prix.native_field_lookup_v2 import NativeFieldLookup


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


def read_native_evaluator_scene(supervisor, course, fields):
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
    root_nodes = _read_native_root_nodes(supervisor)
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
    # Full live Supervisor readback: floor, every collision box and absence
    # of hidden extra bodies. This function itself returns no READY token.
    _verify_scene_boxes(course, canonical_native_boxes(course), root_nodes, fields)
    return vehicle
