"""Native R2025a full-course H sensor probe. Teleportation is not flight.

The physical L/open-H/closed-H scene is canonical. The pupil Runtime is off.
This probe measures native horizontal rays AND reciprocal ODE contacts, but NOT mission progress,
autonomous trajectories, READY/ALIVE or an accepted teacher GUI journey.
"""
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from controller import Supervisor
from tools.grand_prix.native_collider_contract_v2 import (
    canonical_native_boxes, verify_native_boxes,
)
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes


def witness():
    index = int(os.environ["GP_V2_H_NATIVE_INDEX"])
    course = reference_course(index)
    output = Path(os.environ["GP_V2_H_NATIVE_OUT"])
    robot = Supervisor()
    step = int(robot.getBasicTimeStep())
    if step != 8:
        raise RuntimeError("wrong Webots native timestep")
    # Native geometry is read back independently of the course construction.
    verify_native_boxes(robot, course, canonical_native_boxes(course))
    self_node = robot.getSelf()
    translation = self_node.getField("translation")
    rotation = self_node.getField("rotation")
    if translation is None or rotation is None:
        raise RuntimeError("native vehicle pose fields unavailable")
    sensors = {}
    for direction in ("front", "back", "left", "right"):
        device = robot.getDevice("range_" + direction)
        if device is None:
            raise RuntimeError("native Multi-ranger device unavailable: " + direction)
        device.enable(step)
        sensors[direction] = device

    def sample(leg, along, height):
        x, y = leg.at(along)
        yaw = leg.direction * math.pi / 2
        translation.setSFVec3f([x, y, height])
        rotation.setSFRotation([0, 0, 1, yaw])
        self_node.resetPhysics()
        for _ in range(3):
            if robot.step(step) == -1:
                raise RuntimeError("Webots quit before native ray measurement")
        values = {name: device.getValue() / 1000
                  for name, device in sensors.items()}
        if any(type(value) not in (int, float) or
               not math.isfinite(value) or not 0 <= value <= 2.001
               for value in values.values()):
            raise RuntimeError("invalid native horizontal ray")
        return values

    opened = []
    for gate in course.gates:
        leg = course.route.legs[gate.leg_index]
        # A real beam at z=.90 must be detectable from 24 cm upstream.
        # Below its physical .62 m underside the central opening should
        # produce a materially longer range; failure is UNQUALIFIED.
        if gate.along <= .24:
            raise RuntimeError("insufficient upstream H probe clearance")
        low = sample(leg, gate.along - .24, .40)
        high = sample(leg, gate.along - .24, .90)
        if not (.07 < high["front"] < .48 and
                low["front"] > high["front"] + .15):
            raise RuntimeError(
                "open H not discriminated by native vertical passage rays: " +
                str(gate.leg_index) + " " + repr((low, high)))
        opened.append(dict(leg=gate.leg_index,
                           box=f"GP_V2_H_{gate.leg_index}_BEAM",
                           low=low, high=high))
    leg = course.route.legs[-1]
    terminal_low = sample(leg, leg.length - .30, .40)
    terminal_high = sample(leg, leg.length - .30, .90)
    if not (.07 < terminal_low["front"] < .55 and
            .07 < terminal_high["front"] < .55):
        raise RuntimeError("terminal closed H not detected in native rays")
    # This remains a stationary teleportation probe: real ODE contacts
    # exercise the pinned unpowered Cylinder, never a trajectory or mission.
    bounds_field = self_node.getBaseNodeField("boundingObject")
    bounds = bounds_field.getSFNode() if bounds_field is not None else None
    physics_field = self_node.getBaseNodeField("physics")
    physics = physics_field.getSFNode() if physics_field is not None else None
    rfield = bounds.getField("radius") if bounds is not None else None
    hfield = bounds.getField("height") if bounds is not None else None
    radius = rfield.getSFFloat() if rfield is not None else None
    cylinder_height = hfield.getSFFloat() if hfield is not None else None
    if (bounds is None or bounds.getTypeName() != "Cylinder" or
            physics is None or physics.getTypeName() != "Physics" or
            type(radius) not in (int, float) or
            type(cylinder_height) not in (int, float) or
            not math.isclose(radius, .05, rel_tol=0, abs_tol=1e-9) or
            not math.isclose(cylinder_height, .03, rel_tol=0, abs_tol=1e-9)):
        raise RuntimeError("pinned R2025a vehicle collider/physics mismatch")

    def native_points(node, descendants):
        raw = node.getContactPoints(includeDescendants=descendants)
        if not isinstance(raw, (list, tuple)) or len(raw) > 2048:
            raise RuntimeError("invalid native contact collection")
        values = []
        for item in raw:
            point = item.point
            own_id = item.node_id
            if (not isinstance(point, (list, tuple)) or len(point) != 3 or
                    any(type(c) not in (float, int) or not math.isfinite(c) for c in point) or
                    type(own_id) is not int or not -(2**31) <= own_id < 2**31):
                raise RuntimeError("nonfinite or malformed native contact")
            values.append(dict(point=[float(c) for c in point], node_id=own_id))
        return values

    def native_solid(box):
        solid = robot.getFromDef(box.name)
        if solid is None or solid.getTypeName() != "Solid":
            raise RuntimeError("missing canonical native H collider " + box.name)
        own_id = solid.getId()
        if type(own_id) is not int or own_id <= 0:
            raise RuntimeError("invalid native H collider identity " + box.name)
        return solid, own_id

    def contact_capture(position, solids):
        translation.setSFVec3f(list(position))
        rotation.setSFRotation([0, 0, 1, 0])
        self_node.resetPhysics()
        observed = []
        for _ in range(3):
            if robot.step(step) == -1:
                raise RuntimeError("Webots quit before native H contact measurement")
            ms = round(robot.getTime() * 1000)
            if ms % 8:
                raise RuntimeError("noncanonical native H contact clock")
            observed.append(dict(time_ms=ms,
                contacts=native_points(self_node, True),
                target_contacts={box.name: native_points(solid, False)
                                 for box, solid in solids}))
        return observed

    def collision_position(box):
        # 15 mm superficial cylinder/Box overlap on the thinner XY face;
        # posts and closed panel are probed below the open-H beam (0.40m),
        # the beam at 0.90m. This is a native stimulus, never a forged hit.
        offset = min(box.sx, box.sy) / 2 + radius - .015
        z = .90 if box.name.endswith("_BEAM") else .40
        if box.sy < box.sx:
            return box.x, box.y + offset, z
        return box.x + offset, box.y, z

    contact_opened = []
    native_ids = set()
    for gate in course.gates:
        leg = course.route.legs[gate.leg_index]
        boxes = tuple(box for box in open_h_boxes(course)
                      if box.name.startswith(f"GP_V2_H_{gate.leg_index}_"))
        if len(boxes) != 3:
            raise RuntimeError("missing three native open-H Solids")
        pairs = tuple((box, native_solid(box)[0]) for box in boxes)
        passage = []
        for delta in (-.20, 0., .20):
            x, y = leg.at(gate.along + delta)
            passage.append(dict(offset_m=delta,
                observations=contact_capture((x, y, .40), pairs)))
        targets = []
        x, y = leg.at(gate.along)
        for box, solid in pairs:
            node_id = solid.getId()
            if node_id in native_ids:
                raise RuntimeError("duplicate native H collider identity")
            native_ids.add(node_id)
            targets.append(dict(target=box.name, target_node_id=node_id,
                free=contact_capture((x, y, .40), ((box, solid),)),
                collision=contact_capture(collision_position(box), ((box, solid),))))
        contact_opened.append(dict(leg=gate.leg_index,
                                   passage=passage, targets=targets))
    panel = terminal_boxes(course.route)[-1]
    terminal_solid, terminal_id = native_solid(panel)
    if terminal_id in native_ids or panel.name != "GP_V2_FINAL_PANEL":
        raise RuntimeError("invalid terminal H panel identity")
    leg = course.route.legs[-1]
    x, y = leg.at(leg.length - .30)
    contact_terminal = dict(target=panel.name, target_node_id=terminal_id,
        free=contact_capture((x, y, .40), ((panel, terminal_solid),)),
        collision=contact_capture(collision_position(panel),
                                  ((panel, terminal_solid),)))
    contact = dict(source="Robot.getContactPoints(includeDescendants=True)",
                   target_source="Solid.getContactPoints(includeDescendants=False)",
                   opened=contact_opened, terminal=contact_terminal)

    evidence = dict(claim="full-course-native-H-rays-and-reciprocal-contacts-no-flight",
                    configuration=course.identifier, webots="R2025a",
                    timestep_ms=step, opened=opened,
                    terminal=dict(box="GP_V2_FINAL_PANEL",
                                  low=terminal_low, high=terminal_high), contact=contact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, allow_nan=False, sort_keys=True) + "\n")
    print("GP_V2_H_NATIVE " + json.dumps(evidence, allow_nan=False, sort_keys=True),
          flush=True)
    robot.step(step)
    robot.simulationQuit(0)


if __name__ == "__main__":
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
