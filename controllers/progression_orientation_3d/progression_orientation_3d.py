#!/usr/bin/env python3
"""Activity 3: independently observe ordered 3D waypoints and measured heading.

The scene-only supervisor observes the craft's physical pose, orientation,
velocity, and the existing exact-attempt customData protocol. It does not
read the student's program, issue flight commands, or inspect a solution AST.
"""
from __future__ import annotations

import math
import re

ORACLE = "progression-orientation-3d-v1"
SCENE_DEF = "WEBEEBLOCKS_ORIENTATION_SCENE"
SCENE_CHILDREN = 24
CHECKPOINTS = (
    (0.45, 0.0, 0.63, -math.pi / 2),
    (0.45, -0.45, 0.79, 0.0),
    (0.90, -0.45, 0.63, -math.pi / 2),
)
ARRIVAL = (0.90, -0.90)
HORIZONTAL_TOLERANCE = 0.105
ALTITUDE_TOLERANCE = 0.085
HEADING_TOLERANCE_RAD = 0.20
LANDING_TOLERANCE = 0.11
AIRBORNE_DELTA = 0.20
LANDED_DELTA = 0.07
MAX_LANDING_SPEED = 0.12
SETTLE_TIMEOUT_S = 1.5

ATTEMPT = re.compile(r"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 ([1-9][0-9]*)")
COMPLETION = re.compile(
    r"WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=([1-9][0-9]*) oracle="
    + re.escape(ORACLE)
)


def parse_attempt(value):
    match = ATTEMPT.fullmatch(value or "")
    return int(match.group(1)) if match else None


def parse_completion(value, attempt_id):
    match = COMPLETION.fullmatch(value or "")
    return bool(match and int(match.group(1)) == attempt_id)


def valid_numbers(*groups):
    try:
        return all(math.isfinite(float(v)) for group in groups for v in group)
    except (TypeError, ValueError, OverflowError):
        return False


def wrapped_error(actual, desired):
    return abs(math.atan2(math.sin(actual - desired), math.cos(actual - desired)))


def yaw_from_orientation(orientation):
    """Webots orientation matrix is row-major; local +X projected into world XY."""
    if orientation is None or len(orientation) != 9 or not valid_numbers(orientation):
        return None
    x_axis_x = float(orientation[0])
    x_axis_y = float(orientation[3])
    if math.hypot(x_axis_x, x_axis_y) < 0.5:
        return None
    return math.atan2(x_axis_y, x_axis_x)


class Attempt:
    def __init__(self, identity, origin_z):
        self.identity = identity
        self.origin_z = float(origin_z)
        self.stage = 0
        self.airborne = False
        self.completed_at = None
        self.result = None

    def sample(self, now, position, yaw, velocity, completed):
        if self.result is not None:
            return self.result
        if (position is None or len(position) < 3
                or velocity is None or len(velocity) < 3
                or yaw is None or not valid_numbers(position[:3], (yaw, now),
                                                      velocity[:3])):
            if completed or self.completed_at is not None:
                self.result = "not-achieved"
            return self.result
        x, y, z = map(float, position[:3])
        vx, vy, vz = map(float, velocity[:3])
        if z >= self.origin_z + AIRBORNE_DELTA:
            self.airborne = True
        if self.completed_at is None and not completed and self.airborne:
            if self.stage < len(CHECKPOINTS):
                cx, cy, cz, required_yaw = CHECKPOINTS[self.stage]
                if (abs(x - cx) <= HORIZONTAL_TOLERANCE
                        and abs(y - cy) <= HORIZONTAL_TOLERANCE
                        and abs(z - cz) <= ALTITUDE_TOLERANCE
                        and wrapped_error(yaw, required_yaw) <= HEADING_TOLERANCE_RAD):
                    self.stage += 1
        if completed and self.completed_at is None:
            self.completed_at = now
        if self.completed_at is None:
            return None
        if not self.airborne or self.stage != len(CHECKPOINTS):
            self.result = "not-achieved"
            return self.result
        landed = z <= self.origin_z + LANDED_DELTA
        stationary = math.hypot(vx, vy) <= MAX_LANDING_SPEED and abs(vz) <= MAX_LANDING_SPEED
        on_target = (abs(x - ARRIVAL[0]) <= LANDING_TOLERANCE
                     and abs(y - ARRIVAL[1]) <= LANDING_TOLERANCE)
        if landed and stationary and on_target:
            self.result = "achieved"
        elif now - self.completed_at >= SETTLE_TIMEOUT_S:
            self.result = "not-achieved"
        return self.result


def run():
    from controller import Supervisor

    supervisor = Supervisor()
    step = int(supervisor.getBasicTimeStep())
    if step <= 0:
        raise RuntimeError("orientation 3D invalid native timestep")
    scene = supervisor.getFromDef(SCENE_DEF)
    if (scene is None or scene.getTypeName() != "Group"
            or scene.getField("children") is None
            or scene.getField("children").getCount() != SCENE_CHILDREN):
        raise RuntimeError("orientation 3D scene identity unavailable")
    root_children = supervisor.getRoot().getField("children")
    craft = None
    for index in range(root_children.getCount()):
        node = root_children.getMFNode(index)
        name_field = node.getField("name")
        if name_field is not None and name_field.getSFString() == "Crazyflie WebeeBlocks":
            if craft is not None:
                raise RuntimeError("orientation 3D ambiguous craft")
            craft = node
    if craft is None:
        raise RuntimeError("orientation 3D craft unavailable")
    channel = craft.getField("customData")
    if channel is None:
        raise RuntimeError("orientation 3D outcome channel unavailable")
    origin = craft.getPosition()
    if origin is None or len(origin) != 3 or not valid_numbers(origin):
        raise RuntimeError("orientation 3D initial pose unavailable")
    origin_z = origin[2]
    active = None
    last_identity = 0
    print("WEBEEBLOCKS_ORIENTATION_3D_READY", flush=True)

    while supervisor.step(step) != -1:
        raw = channel.getSFString() or ""
        identity = parse_attempt(raw)
        if identity is not None and identity > last_identity:
            active = Attempt(identity, origin_z)
            last_identity = identity
            print(f"WEBEEBLOCKS_ORIENTATION_3D_ATTEMPT attempt={identity}", flush=True)
        if active is None:
            continue
        result = active.sample(
            supervisor.getTime(),
            craft.getPosition(),
            yaw_from_orientation(craft.getOrientation()),
            craft.getVelocity(),
            parse_completion(raw, active.identity),
        )
        if result is None:
            continue
        outcome = (
            f"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt={active.identity} "
            f"oracle={ORACLE} status={result}"
        )
        if raw != outcome:
            channel.setSFString(outcome)
            print(
                f"WEBEEBLOCKS_ORIENTATION_3D_RESULT attempt={active.identity} "
                f"status={result} checkpoints={active.stage}",
                flush=True,
            )


if __name__ == "__main__":
    run()
