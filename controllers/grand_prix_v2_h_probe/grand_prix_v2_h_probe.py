"""Native R2025a full-course H sensor probe. Teleportation is not flight.

The physical L/open-H/closed-H scene is canonical. The pupil Runtime is off.
This probe measures native horizontal rays, NOT contacts, mission progress,
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
    evidence = dict(claim="full-course-native-H-rays-no-flight-no-contact",
                    configuration=course.identifier, webots="R2025a",
                    timestep_ms=step, opened=opened,
                    terminal=dict(box="GP_V2_FINAL_PANEL",
                                  low=terminal_low, high=terminal_high))
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
