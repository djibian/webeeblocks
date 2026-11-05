"""Read flight-owned native ranges from two verified Webots Robots; data only.

A Supervisor cannot read another Robot's DistanceSensors. The flight process
writes GP_ROUTE_EVALUATOR.model and owns the customData challenge/start channel.
Neither a matching value nor a finite sample grants READY, RESET or flight.
"""
import math

from tools.grand_prix.evaluator_scene_identity_v2 import check_native_evaluator_scene
from tools.grand_prix.route_evaluator_wire_v2 import parse_flight_channel
from tools.grand_prix.route_flight_observation_v2 import parse_flight_observation


def _text(node, name):
    field = node.getField(name)
    if field is None:
        raise RuntimeError('missing native ' + name + ' field')
    value = field.getSFString()
    if type(value) is not str:
        raise RuntimeError('invalid native ' + name + ' field')
    return value


def _args(node, identifier):
    field = node.getField('controllerArgs')
    if field is None or field.getCount() != 1 or field.getMFString(0) != identifier:
        raise RuntimeError('changed native course arguments')


def _now_ms(supervisor):
    value = supervisor.getTime()
    if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1e12:
        raise RuntimeError('invalid native observation time')
    ms = round(value * 1000)
    if abs(value * 1000 - ms) > 1e-4 or ms % 8:
        raise RuntimeError('noncanonical native observation time')
    return ms


class NativeFlightRangeReader:
    """Bind verified native Robot IDs, then read their live fields each tick.

    Complete scene/collider identity is checked on construction. Every read
    rechecks flight/evaluator provenance and parses the actual native fields.
    The caller still needs independent RESET, contacts, pose and mission oracles.
    """

    def __init__(self, supervisor, identifier):
        check_native_evaluator_scene(supervisor, identifier)
        evaluator = supervisor.getSelf()
        children = supervisor.getRoot().getField('children')
        vehicles = []
        for index in range(children.getCount()):
            node = children.getMFNode(index)
            name = node.getField('name') if node is not None else None
            if name is not None and name.getSFString() == 'Crazyflie WebeeBlocks':
                vehicles.append(node)
        if len(vehicles) != 1:
            raise RuntimeError('missing or duplicate native flight Robot')
        self._evaluator_id = evaluator.getId()
        self._flight_id = vehicles[0].getId()
        if (type(self._evaluator_id) is not int or self._evaluator_id <= 0 or
                type(self._flight_id) is not int or self._flight_id <= 0 or
                self._evaluator_id == self._flight_id):
            raise RuntimeError('invalid native Robot IDs')
        self._supervisor = supervisor
        self._identifier = identifier
        self._last_ms = None

    def read(self):
        """Return a FlightObservation, never an authority or a predicted range."""
        supervisor = self._supervisor
        if supervisor.getBasicTimeStep() != 8:
            raise RuntimeError('changed native timestep')
        evaluator = supervisor.getFromId(self._evaluator_id)
        flight = supervisor.getFromId(self._flight_id)
        self_node = supervisor.getSelf()
        marker = supervisor.getFromDef('GP_ROUTE_EVALUATOR')
        if (evaluator is None or flight is None or self_node is None or
                marker is None or evaluator.getId() != self._evaluator_id or
                self_node.getId() != self._evaluator_id or
                marker.getId() != self._evaluator_id or
                evaluator.getTypeName() != 'Robot' or
                evaluator.getBaseTypeName() != 'Robot' or
                flight.getId() != self._flight_id or
                not flight.isProto() or flight.getTypeName() != 'Crazyflie' or
                flight.getBaseTypeName() != 'Robot'):
            raise RuntimeError('native Robot source identity changed')
        if (_text(evaluator, 'controller') != 'grand_prix_route_evaluator' or
                _text(flight, 'name') != 'Crazyflie WebeeBlocks' or
                _text(flight, 'controller') != 'grand_prix_route_flight' or
                _text(flight, 'window') != 'grand_prix_route_v2'):
            raise RuntimeError('native Robot source provenance changed')
        for node in (evaluator, flight):
            field = node.getField('supervisor')
            if field is None or field.getSFBool() is not True:
                raise RuntimeError('native supervisor provenance changed')
            _args(node, self._identifier)
        now = _now_ms(supervisor)
        if self._last_ms is not None and now <= self._last_ms:
            raise RuntimeError('replayed native evaluator observation tick')
        event = parse_flight_channel(_text(flight, 'customData'), self._identifier)
        if event is None:
            raise RuntimeError('flight observation without live attempt')
        packet = _text(evaluator, 'model')
        result = parse_flight_observation(packet, event, now)
        self._last_ms = now
        return result
