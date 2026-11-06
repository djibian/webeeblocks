"""Read-only native R2025a Crazyflie contacts for the variable Grand Prix.

A returned empty list means *only* that Webots returned no contact points at
this tick. It is NOT proof of contact tracking, collision freedom, fresh RESET,
a complete scene, a qualified flight, or evaluator admission. The caller must
separately attest the scene and native attempt. No READY/ALIVE is emitted here.
"""
from dataclasses import dataclass
import math

from tools.grand_prix.route_courses_v2 import course_from_identifier
from tools.grand_prix.native_sfbbool_v2 import enabled


@dataclass(frozen=True)
class NativeContactPoint:
    point: tuple[float, float, float]
    node_id: int


@dataclass(frozen=True)
class NativeContactObservation:
    time_ms: int
    points: tuple[NativeContactPoint, ...]


def _strict_vector(value):
    if (not isinstance(value, (tuple, list)) or len(value) != 3 or
            any(type(x) not in (float, int) or not math.isfinite(x) for x in value)):
        raise RuntimeError("invalid native contact coordinates")
    return tuple(float(x) for x in value)


def _time_ms(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise RuntimeError("invalid native contact clock")
    milliseconds = round(value * 1000)
    if (milliseconds > 10**15 or milliseconds % 8 != 0 or
            abs(value * 1000 - milliseconds) > 1e-4):
        raise RuntimeError("noncanonical native contact clock")
    return milliseconds


def _field(node, key):
    result = node.getField(key)
    if result is None:
        raise RuntimeError("missing native contact source field " + key)
    return result


def _valid_vehicle(node, identifier):
    if (node is None or not node.isProto() or
            node.getTypeName() != "Crazyflie" or
            node.getBaseTypeName() != "Robot" or
            _field(node, "name").getSFString() != "Crazyflie WebeeBlocks" or
            not enabled(_field(node, "supervisor").getSFBool()) or
            _field(node, "controller").getSFString() != "grand_prix_route_flight" or
            _field(node, "window").getSFString() != "grand_prix_route_v2"):
        raise RuntimeError("invalid native contact source identity")
    args = _field(node, "controllerArgs")
    if args.getCount() != 1 or args.getMFString(0) != identifier:
        raise RuntimeError("native contact source course mismatch")


class NativeContactSampler:
    """Sample the real Robot's contacts after each native 8-ms step.

    The pinned R2025a Python API returns ContactPoint(point, node_id).
    includeDescendants=True is necessary for contacts of PROTO children.
    These are raw observations, never contact-clear or route verdicts.
    """

    def __init__(self, supervisor, course_identifier):
        if (type(course_identifier) is not str or
                course_from_identifier(course_identifier).identifier != course_identifier or
                supervisor.getBasicTimeStep() != 8):
            raise RuntimeError("noncanonical native contact course or timestep")
        children = supervisor.getRoot().getField("children")
        if children is None or not 0 < children.getCount() < 8192:
            raise RuntimeError("missing native contact root inventory")
        matches = []
        for index in range(children.getCount()):
            node = children.getMFNode(index)
            if node is None:
                raise RuntimeError("unreadable native contact root node")
            name = node.getField("name")
            if name is not None and name.getSFString() == "Crazyflie WebeeBlocks":
                matches.append(node)
        if len(matches) != 1:
            raise RuntimeError("missing or duplicate native contact source")
        _valid_vehicle(matches[0], course_identifier)
        identity = matches[0].getId()
        if type(identity) is not int or identity <= 0:
            raise RuntimeError("invalid native contact source ID")
        self._supervisor = supervisor
        self._id = identity
        self._course = course_identifier
        self._last_ms = None

    def snapshot(self):
        if self._supervisor.getBasicTimeStep() != 8:
            raise RuntimeError("native contact timestep changed")
        node = self._supervisor.getFromId(self._id)
        if node is None or node.getId() != self._id:
            raise RuntimeError("native contact source disappeared")
        _valid_vehicle(node, self._course)
        milliseconds = _time_ms(self._supervisor.getTime())
        if self._last_ms is not None and milliseconds <= self._last_ms:
            raise RuntimeError("replayed or nonmonotonic native contacts")
        observed = node.getContactPoints(includeDescendants=True)
        if not isinstance(observed, (list, tuple)) or len(observed) > 4096:
            raise RuntimeError("invalid native contact collection")
        points = []
        for item in observed:
            coords = _strict_vector(item.point)
            node_id = item.node_id
            if type(node_id) is not int or not -(2**31) <= node_id < 2**31:
                raise RuntimeError("invalid native contact node ID")
            points.append(NativeContactPoint(coords, node_id))
        self._last_ms = milliseconds
        return NativeContactObservation(milliseconds, tuple(points))
