"""Fail-closed R2025a live vehicle kinematics, without mission authority.

The evaluator must first independently verify the exact scene, collider inventory
and course identity. This sampler records actual Supervisor pose/orientation/
velocity at 8-ms steps; it cannot read another Robot's DistanceSensors and
NEVER establishes RESET, contacts, READY/ALIVE, outcome or pupil success.
"""
from dataclasses import dataclass
import math

from tools.grand_prix.route_courses_v2 import course_from_identifier
from tools.grand_prix.native_sfbbool_v2 import enabled


@dataclass(frozen=True)
class NativeKinematics:
    time_ms: int
    position: tuple[float, float, float]
    orientation: tuple[float, ...]
    velocity: tuple[float, ...]


def _vector(values, size, name):
    if (not isinstance(values, (list, tuple)) or len(values) != size or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in values)):
        raise RuntimeError('unavailable native ' + name)
    return tuple(float(value) for value in values)


def _orientation(values):
    matrix = _vector(values, 9, 'orientation')
    rows = (matrix[:3], matrix[3:6], matrix[6:])
    for i in range(3):
        for j in range(3):
            dot = sum(rows[i][k] * rows[j][k] for k in range(3))
            if abs(dot - (1. if i == j else 0.)) > 1e-6:
                raise RuntimeError('non-rigid native orientation')
    a, b, c = rows
    determinant = (a[0] * (b[1]*c[2]-b[2]*c[1]) -
                   a[1] * (b[0]*c[2]-b[2]*c[0]) +
                   a[2] * (b[0]*c[1]-b[1]*c[0]))
    if abs(determinant-1.) > 1e-6:
        raise RuntimeError('invalid native orientation handedness')
    return matrix


def _now_ms(time):
    if (type(time) not in (int, float) or not math.isfinite(time) or
            not 0 <= time <= 1e12):
        raise RuntimeError('invalid Webots native clock')
    millis = round(time * 1000)
    if abs(time * 1000 - millis) > 1e-4 or millis % 8:
        raise RuntimeError('noncanonical 8-ms native time')
    return millis


def _one_field(node, key):
    field = node.getField(key)
    if field is None:
        raise RuntimeError('missing native vehicle field ' + key)
    return field


def read_kinematics(node, ms, *, tracked_pose=False):
    """Read a verified vehicle's pose and velocity in world coordinates."""
    if tracked_pose:
        pose = _vector(node.getPose(), 16, 'world pose')
        position = (pose[3], pose[7], pose[11])
        orientation = _orientation(pose[:3] + pose[4:7] + pose[8:11])
    else:
        position = _vector(node.getPosition(), 3, 'position')
        orientation = _orientation(node.getOrientation())
    velocity = _vector(node.getVelocity(), 6, 'linear/angular velocity')
    return NativeKinematics(ms, position, orientation, velocity)


class NativeKinematicsSampler:
    """Strictly increasing native R2025a pose and velocity snapshots.

    This observation must be sampled after a Webots step, with scene/collider
    attestation separately established. A broken sample raises and must be a
    terminal rejection for the caller: no fallback to old or predicted pose.
    """
    def __init__(self, supervisor, course_identifier):
        if (type(course_identifier) is not str or
                course_from_identifier(course_identifier).identifier != course_identifier or
                supervisor.getBasicTimeStep() != 8):
            raise RuntimeError('noncanonical native route or timestep')
        children = supervisor.getRoot().getField('children')
        if children is None or not 0 < children.getCount() < 8192:
            raise RuntimeError('missing native root inventory')
        vehicles = []
        for index in range(children.getCount()):
            node = children.getMFNode(index)
            if node is None:
                raise RuntimeError('unreadable native root node')
            name = node.getField('name')
            if name is not None and name.getSFString() == 'Crazyflie WebeeBlocks':
                vehicles.append(node)
        if len(vehicles) != 1:
            raise RuntimeError('missing or duplicate native vehicle')
        vehicle = vehicles[0]
        if (not vehicle.isProto() or vehicle.getTypeName() != 'Crazyflie' or
                vehicle.getBaseTypeName() != 'Robot' or
                _one_field(vehicle, 'name').getSFString() != 'Crazyflie WebeeBlocks' or
                not enabled(_one_field(vehicle, 'supervisor').getSFBool()) or
                _one_field(vehicle, 'controller').getSFString() != 'grand_prix_route_flight' or
                _one_field(vehicle, 'window').getSFString() != 'grand_prix_route_v2'):
            raise RuntimeError('noncanonical native flight Robot')
        args = _one_field(vehicle, 'controllerArgs')
        if args.getCount() != 1 or args.getMFString(0) != course_identifier:
            raise RuntimeError('native vehicle course mismatch')
        identity = vehicle.getId()
        if type(identity) is not int or identity <= 0:
            raise RuntimeError('invalid native vehicle ID')
        self._robot = supervisor
        self._vehicle_id = identity
        self._course = course_identifier
        self._last_ms = None

    def snapshot(self):
        """Read the live vehicle node; return data ONLY (never READY)."""
        if self._robot.getBasicTimeStep() != 8:
            raise RuntimeError('changed native timestep')
        node = self._robot.getFromId(self._vehicle_id)
        if (node is None or node.getId() != self._vehicle_id or
                node.getTypeName() != 'Crazyflie' or
                node.getBaseTypeName() != 'Robot'):
            raise RuntimeError('native vehicle identity disappeared')
        # A stable node ID/type alone is not sufficient provenance: supervisors
        # may change a Robot's fields between native steps. Reject drift.
        if (not node.isProto() or
                _one_field(node, 'name').getSFString() != 'Crazyflie WebeeBlocks' or
                not enabled(_one_field(node, 'supervisor').getSFBool()) or
                _one_field(node, 'controller').getSFString() != 'grand_prix_route_flight' or
                _one_field(node, 'window').getSFString() != 'grand_prix_route_v2'):
            raise RuntimeError('native vehicle provenance changed')
        args = _one_field(node, 'controllerArgs')
        if args.getCount() != 1 or args.getMFString(0) != self._course:
            raise RuntimeError('native vehicle course changed')
        ms = _now_ms(self._robot.getTime())
        if self._last_ms is not None and ms <= self._last_ms:
            raise RuntimeError('replayed or nonmonotonic native pose')
        observation = read_kinematics(node, ms)
        self._last_ms = ms
        return observation
