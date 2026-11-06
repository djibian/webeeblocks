"""Native R2025a full-course H sensor probe. Teleportation is not flight.

The physical L/open-H/closed-H scene is canonical. The pupil Runtime is off.
This probe measures native rays, open-passage clearance and reciprocal physical
beam/panel/post contacts, NOT mission progress, autonomous flight, READY/ALIVE or GUI.
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
    # Physical counter-test on the same pinned, unpowered full course: an
    # open H passage at 0.4 m must have NO real contact, while its overhead
    # beam at its actual height, and the closed terminal panel at 0.4 m,
    # must each report reciprocal, same-tick Robot/Solid ODE contacts.
    bound_field = self_node.getBaseNodeField("boundingObject")
    bound = bound_field.getSFNode() if bound_field is not None else None
    radius_field = bound.getField("radius") if bound is not None else None
    height_field = bound.getField("height") if bound is not None else None
    radius = radius_field.getSFFloat() if radius_field is not None else None
    height = height_field.getSFFloat() if height_field is not None else None
    if (bound is None or bound.getTypeName() != "Cylinder" or
            type(radius) not in (int, float) or
            type(height) not in (int, float) or
            not math.isclose(radius, .05, rel_tol=0, abs_tol=1e-9) or
            not math.isclose(height, .03, rel_tol=0, abs_tol=1e-9)):
        raise RuntimeError("pinned native Crazyflie Cylinder differs")

    def contact_points(node, descendants):
        raw = node.getContactPoints(includeDescendants=descendants)
        if not isinstance(raw, (list, tuple)) or len(raw) > 2048:
            raise RuntimeError("invalid native H contact collection")
        points = []
        for hit in raw:
            coords = hit.point
            identity = hit.node_id
            if (not isinstance(coords, (tuple, list)) or len(coords) != 3 or
                    any(type(v) not in (int, float) or not math.isfinite(v)
                        for v in coords) or
                    type(identity) is not int or
                    not -(2**31) <= identity < 2**31):
                raise RuntimeError("malformed native H contact point")
            points.append(dict(point=[float(v) for v in coords], node_id=identity))
        return points

    def contact_capture(position, collider):
        translation.setSFVec3f(list(position))
        rotation.setSFRotation([0, 0, 1, 0])
        self_node.resetPhysics()
        observations = []
        for _ in range(3):
            if robot.step(step) == -1:
                raise RuntimeError("native H contact acquisition interrupted")
            ms = round(robot.getTime() * 1000)
            if ms % step:
                raise RuntimeError("native H contact clock not on 8-ms grid")
            observations.append(dict(time_ms=ms,
                                     contacts=contact_points(self_node, True),
                                     target_contacts=contact_points(collider, False)))
        return observations

    contact_witnesses = []
    beam_boxes = {box.name: box for box in open_h_boxes(course)}
    for gate in course.gates:
        leg = course.route.legs[gate.leg_index]
        name = f"GP_V2_H_{gate.leg_index}_BEAM"
        beam = beam_boxes[name]
        collider = robot.getFromDef(name)
        if collider is None or collider.getTypeName() != "Solid":
            raise RuntimeError("native open-H beam missing")
        node_id = collider.getId()
        if type(node_id) is not int or node_id <= 0:
            raise RuntimeError("invalid native open-H beam ID")
        # Centre at 0.4 m passes below the 0.62 m opening limit.
        opening = leg.at(gate.along)
        passage = contact_capture([*opening, .40], collider)
        upstream = leg.at(gate.along - .24)
        free = contact_capture([*upstream, beam.z], collider)
        # Shallow 15-mm overlap against a longitudinal face of the beam.
        offset = min(beam.sx, beam.sy) / 2 + radius - .015
        collision = contact_capture(
            [beam.x + offset, beam.y, beam.z] if leg.direction % 2 == 0
            else [beam.x, beam.y + offset, beam.z], collider)
        contact_witnesses.append(dict(target=name, target_node_id=node_id,
                                      passage=passage, free=free, collision=collision))

    panel = next(box for box in terminal_boxes(course.route)
                 if box.name == "GP_V2_FINAL_PANEL")
    collider = robot.getFromDef(panel.name)
    if collider is None or collider.getTypeName() != "Solid":
        raise RuntimeError("native terminal H panel missing")
    node_id = collider.getId()
    if type(node_id) is not int or node_id <= 0:
        raise RuntimeError("invalid native terminal H panel ID")
    last_leg = course.route.legs[-1]
    free_point = last_leg.at(last_leg.length - .30)
    free = contact_capture([*free_point, .40], collider)
    offset = min(panel.sx, panel.sy) / 2 + radius - .015
    collision = contact_capture(
        [panel.x + offset, panel.y, .40] if last_leg.direction % 2 == 0
        else [panel.x, panel.y + offset, .40], collider)
    contact_witnesses.append(dict(target=panel.name, target_node_id=node_id,
                                  passage=None, free=free, collision=collision))

    # Each real vertical H post is independently collision-enabled; the
    # absence of a contact in the centre passage cannot prove that alone.
    # Move the unpowered Cylinder 15 mm into the inside lateral face.
    post_witnesses = []
    for gate in course.gates:
        leg = course.route.legs[gate.leg_index]
        centre = leg.at(gate.along)
        for part in ("LEFT", "RIGHT"):
            name = f"GP_V2_H_{gate.leg_index}_{part}"
            post = beam_boxes[name]
            collider = robot.getFromDef(name)
            if collider is None or collider.getTypeName() != "Solid":
                raise RuntimeError("native open-H post missing: " + name)
            node_id = collider.getId()
            if type(node_id) is not int or node_id <= 0:
                raise RuntimeError("invalid native open-H post ID")
            free = contact_capture([*centre, .40], collider)
            inset = (post.sy if leg.direction % 2 == 0 else post.sx) / 2 + radius - .015
            if leg.direction % 2 == 0:
                side = 1 if post.y > centre[1] else -1
                hit = [post.x, post.y - side * inset, .40]
            else:
                side = 1 if post.x > centre[0] else -1
                hit = [post.x - side * inset, post.y, .40]
            collision = contact_capture(hit, collider)
            post_witnesses.append(dict(target=name, target_node_id=node_id,
                                       free=free, collision=collision))

    evidence = dict(claim="full-course-native-H-rays-and-contact-no-flight",
                    configuration=course.identifier, webots="R2025a",
                    timestep_ms=step, opened=opened,
                    terminal=dict(box="GP_V2_FINAL_PANEL",
                                  low=terminal_low, high=terminal_high),
                    contact_source="Robot+Solid.getContactPoints R2025a",
                    contact_witnesses=contact_witnesses,
                    post_witnesses=post_witnesses)
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
