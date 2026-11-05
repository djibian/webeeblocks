"""Native R2025a L-corner sensor witness in the complete course (#825).

Native full-scene collider attestation precedes L-only ray samples. No pupil
program, evaluator, mission admission, scoring or motor commands; teleportation
is NOT flight and does not qualify H perception/contact.
"""
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from controller import Supervisor
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.native_collider_contract_v2 import (
    canonical_native_boxes, verify_native_boxes,
)
from tools.grand_prix.route_solid_v2 import corner_boxes, HEIGHT


def close(actual, expected):
    return len(actual) == len(expected) and all(
        math.isfinite(a) and abs(a - b) < 1e-5 for a, b in zip(actual, expected)
    )


def face_normal(box, junction):
    # Select the face on the inward/corridor side of the *physical* arm.
    nx, ny = ((0., 1.) if box.sx > box.sy else (1., 0.))
    projection = (junction[0] - box.x) * nx + (junction[1] - box.y) * ny
    if abs(projection) < .01:
        raise RuntimeError('cannot orient arm probe toward junction: ' + box.name)
    sign = 1 if projection > 0 else -1
    return nx * sign, ny * sign


def witness():
    index = int(os.environ['GP_V2_L_NATIVE_INDEX'])
    output = Path(os.environ['GP_V2_L_NATIVE_OUT'])
    course = reference_course(index)
    robot = Supervisor()
    step = int(robot.getBasicTimeStep())
    if step != 8:
        raise RuntimeError('expected R2025a 8 ms step')
    # A scene containing just four Ls is insufficient: the same native L
    # measurements must be made with *every* canonical H and terminal Solid.
    verify_native_boxes(robot, course, canonical_native_boxes(course))
    self_node = robot.getSelf()
    translation, rotation = (self_node.getField(name) for name in ('translation', 'rotation'))
    if translation is None or rotation is None:
        raise RuntimeError('missing Supervisor pose fields')
    sensors = {}
    for side in ('front', 'back', 'left', 'right'):
        device = robot.getDevice('range_' + side)
        if device is None:
            raise RuntimeError('missing real native distance sensor: ' + side)
        device.enable(step)
        sensors[side] = device

    def observe(x, y, yaw):
        # No propellers or autonomous movement: deterministic static geometry
        # sample, with actual Webots R2025a physics and physical distance rays.
        translation.setSFVec3f([x, y, .65])
        rotation.setSFRotation([0, 0, 1, yaw])
        self_node.resetPhysics()
        for _ in range(3):
            if robot.step(step) == -1:
                raise RuntimeError('Webots ended before native sample')
        readings = {name: device.getValue() / 1000.0
                    for name, device in sensors.items()}
        if any(not math.isfinite(value) or not 0 <= value <= 2.001
               for value in readings.values()):
            raise RuntimeError('non-finite/out-of-range native horizontal sensor')
        return readings

    boxes = corner_boxes(course.route)
    records = []
    for corner in course.route.corners:
        for part, box in enumerate(boxes[corner.index * 2:corner.index * 2 + 2]):
            node = robot.getFromDef(box.name)
            if node is None or node.getTypeName() != 'Solid':
                raise RuntimeError('missing native L Solid: ' + box.name)
            locked = node.getField('locked')
            physical = node.getField('boundingObject')
            physical = physical.getSFNode() if physical is not None else None
            if (locked is None or locked.getSFBool() is not True or
                    physical is None or physical.getTypeName() != 'Box' or
                    not close(node.getPosition(), (box.x, box.y, HEIGHT / 2)) or
                    not close(physical.getField('size').getSFVec3f(),
                              (box.sx, box.sy, HEIGHT))):
                raise RuntimeError('native L pose/collider mismatch: ' + box.name)
            nx, ny = face_normal(box, corner.junction)
            yaw = math.atan2(-ny, -nx)
            thickness = min(box.sx, box.sy)
            near = observe(box.x + nx * (thickness / 2 + .24),
                           box.y + ny * (thickness / 2 + .24), yaw)
            far = observe(box.x + nx * (thickness / 2 + .64),
                          box.y + ny * (thickness / 2 + .64), yaw)
            # A finite echo from the real arm must move farther when the
            # real drone moves away; a saturated/null stub cannot satisfy it.
            if not (.07 < near['front'] < .50 and
                    far['front'] > near['front'] + .20 and
                    far['front'] < 1.30):
                raise RuntimeError('L arm not discriminated by native front sensor: ' +
                                   box.name + ' ' + repr((near, far)))
            records.append(dict(corner=corner.index, part=part, box=box.name,
                                inward=(nx, ny), yaw=yaw,
                                near=near, far=far))

    result = dict(claim='L-only-native-teleport-perception-not-flight',
                  configuration=course.identifier, webots='R2025a',
                  timestep_ms=step, samples=records)
    if len(records) != 4:
        raise RuntimeError('incomplete native L sensor inventory')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, allow_nan=False, sort_keys=True) + '\n')
    print('GP_V2_L_NATIVE ' + json.dumps(result, allow_nan=False, sort_keys=True),
          flush=True)
    robot.step(step)
    robot.simulationQuit(0)


if __name__ == '__main__':
    try:
        witness()
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            Supervisor().simulationQuit(1)
        except Exception:
            pass
        raise
