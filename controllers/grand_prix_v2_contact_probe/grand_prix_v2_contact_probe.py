"""Actual R2025a contact witness for one native L arm in a full inert course.

No motor commands, Blockly, evaluator, mission or attempt admission. A Supervisor
teleports the unpowered PROTO into a native L and reads real contact points.
These forced collisions never qualify an autonomous pupil flight or RESET.
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
from tools.grand_prix.route_solid_v2 import corner_boxes, HEIGHT
from tools.grand_prix.native_collider_contract_v2 import (
    canonical_native_boxes, verify_native_boxes,
)

CLAIM = "full-course-native-L-contact-teleport-no-flight"


def witness():
    index = int(os.environ["GP_V2_CONTACT_INDEX"])
    output = Path(os.environ["GP_V2_CONTACT_OUT"])
    course = reference_course(index)
    robot = Supervisor()
    step = int(robot.getBasicTimeStep())
    if step != 8:
        raise RuntimeError("expected R2025a 8-ms world")
    verify_native_boxes(robot, course, canonical_native_boxes(course))
    vehicle = robot.getSelf()
    if vehicle is None or vehicle.getTypeName() != "Crazyflie":
        raise RuntimeError("native contact witness must be the Crazyflie PROTO")
    fields = (vehicle.getField("translation"), vehicle.getField("rotation"))
    if any(field is None for field in fields):
        raise RuntimeError("native vehicle teleport fields absent")
    translation, rotation = fields
    target = corner_boxes(course.route)[0]
    collider = robot.getFromDef(target.name)
    if collider is None or collider.getTypeName() != "Solid":
        raise RuntimeError("native L collider absent")
    target_id = collider.getId()
    if type(target_id) is not int or target_id <= 0:
        raise RuntimeError("invalid real L node ID")

    def contacts(node, descendants):
        raw = node.getContactPoints(includeDescendants=descendants)
        if not isinstance(raw, (list, tuple)) or len(raw) > 2048:
            raise RuntimeError("invalid native contact collection")
        points = []
        for item in raw:
            coords = item.point
            identity = item.node_id
            if (not isinstance(coords, (list, tuple)) or len(coords) != 3 or
                    any(type(v) not in (int, float) or not math.isfinite(v)
                        for v in coords) or type(identity) is not int or
                    not -(2**31) <= identity < 2**31):
                raise RuntimeError("invalid native contact point")
            points.append(dict(point=[float(v) for v in coords], node_id=identity))
        return points

    def capture(position):
        translation.setSFVec3f(list(position))
        rotation.setSFRotation([0, 0, 1, 0])
        vehicle.resetPhysics()
        observations = []
        for _ in range(3):
            if robot.step(step) == -1:
                raise RuntimeError("Webots stopped during contact acquisition")
            ms = round(robot.getTime() * 1000)
            if ms % 8:
                raise RuntimeError("noncanonical native contact clock")
            # R2025a reports the contacted body's OWN Solid/descendant ID,
            # never its collision partner's ID (WbSolid::extractContactPoints).
            # Read both bodies at one tick and require reciprocal global points.
            observations.append(dict(time_ms=ms, contacts=contacts(vehicle, True),
                                     target_contacts=contacts(collider, False)))
        return observations

    free = capture((0., 0., HEIGHT / 2))
    # Deliberate controlled overlap of the unpowered robot with an actual L Solid.
    # Contact observations are real physics, not an intersection formula.
    collision = capture((target.x, target.y, HEIGHT / 2))
    result = dict(claim=CLAIM, configuration=course.identifier,
                  webots="R2025a", timestep_ms=8,
                  source="Robot.getContactPoints(includeDescendants=True)",
                  target_source="Solid.getContactPoints(includeDescendants=False)",
                  target=target.name, target_node_id=target_id,
                  free=free, collision=collision)
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, sort_keys=True, allow_nan=False)
    output.write_text(encoded + "\n", encoding="utf-8")
    print("GP_V2_CONTACT_NATIVE " + encoded, flush=True)
    if robot.step(step) == -1:
        raise RuntimeError("native contact stdout grace step interrupted")
    robot.simulationQuit(0)


if __name__ == "__main__":
    try:
        witness()
    except Exception:
        import traceback
        # simulationQuit(1) can retire the controller before Webots forwards
        # stderr. Seal the exact fatal traceback on disk first, in the same
        # per-invocation artifact as native.log; NEVER forge native.json.
        diagnostic = traceback.format_exc()
        try:
            failure = Path(os.environ["GP_V2_CONTACT_OUT"]).with_suffix(".failure.log")
            failure.parent.mkdir(parents=True, exist_ok=True)
            failure.write_text(diagnostic, encoding="utf-8")
            failure.chmod(0o644)  # root Docker writer, non-root host uploader
        except (OSError, KeyError):
            pass  # the original failure still governs process exit
        traceback.print_exc()
        try:
            Supervisor().simulationQuit(1)
        except Exception:
            pass
        raise
