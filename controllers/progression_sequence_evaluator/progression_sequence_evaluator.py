#!/usr/bin/env python3
"""Live-world evaluator for progression Activity 1.

This controller observes only Webots world/vehicle state. It never inspects the
Blockly workspace, AST or interpreter trace. The Runtime-v2 controller publishes
the current attempt identity in the Crazyflie's customData field; this evaluator
rebinds to that identity after every successful Reset and publishes the bounded
mission-state oracle consumed by the generic Runtime-v2 outcome channel.
"""

from __future__ import annotations

from math import sqrt

from controller import Supervisor

ATTEMPT_PREFIX = "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 "
OUTCOME_PREFIX = "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1"
ORACLE = "progression-sequence-landing-v1"
CRAZYFLIE_NAME = "Crazyflie WebeeBlocks"

# Activity 1 deliberately uses a generous landing zone: parameter precision is
# reserved for Activity 2. The target sits directly ahead of the departure pad
# and before the existing obstacle corridor.
TARGET_CENTER_X = 0.23
TARGET_HALF_X = 0.16
TARGET_HALF_Y = 0.16
LANDED_MAX_Z = 0.12
STATIONARY_MAX_SPEED_M_S = 0.08


def parse_attempt(value: str) -> int | None:
    if not value.startswith(ATTEMPT_PREFIX):
        return None
    token = value[len(ATTEMPT_PREFIX):]
    try:
        attempt = int(token)
    except ValueError:
        return None
    return attempt if attempt >= 1 else None


def mission_status(position, velocity) -> str:
    x, y, z = (float(position[0]), float(position[1]), float(position[2]))
    speed = sqrt(sum(float(component) ** 2 for component in velocity[:3]))
    inside_target = (
        abs(x - TARGET_CENTER_X) <= TARGET_HALF_X
        and abs(y) <= TARGET_HALF_Y
    )
    landed = z <= LANDED_MAX_Z
    stationary = speed <= STATIONARY_MAX_SPEED_M_S
    return "achieved" if inside_target and landed and stationary else "not-achieved"


def find_named_top_level_robot(supervisor: Supervisor, name: str):
    root = supervisor.getRoot()
    children = root.getField("children") if root is not None else None
    if children is None:
        raise RuntimeError("world children unavailable")
    for index in range(children.getCount()):
        node = children.getMFNode(index)
        if node is None:
            continue
        name_field = node.getField("name")
        if name_field is not None and name_field.getSFString() == name:
            return node
    raise RuntimeError(name + " unavailable")


robot = Supervisor()
step = int(robot.getBasicTimeStep())
crazyflie = find_named_top_level_robot(robot, CRAZYFLIE_NAME)
custom_data = crazyflie.getField("customData")
if custom_data is None:
    raise RuntimeError("Crazyflie customData unavailable")

current_attempt = None
last_publication = None

while robot.step(step) != -1:
    value = custom_data.getSFString() or ""
    observed_attempt = parse_attempt(value)
    if observed_attempt is not None and observed_attempt != current_attempt:
        current_attempt = observed_attempt
        last_publication = None
        print(
            f"WEBEEBLOCKS_SEQUENCE_EVALUATOR observe attempt={current_attempt}",
            flush=True,
        )

    if current_attempt is None:
        continue

    status = mission_status(crazyflie.getPosition(), crazyflie.getVelocity())
    publication = (
        f"{OUTCOME_PREFIX} attempt={current_attempt} oracle={ORACLE} status={status}"
    )
    if publication == last_publication:
        continue
    custom_data.setSFString(publication)
    last_publication = publication
    position = crazyflie.getPosition()
    print(
        "WEBEEBLOCKS_SEQUENCE_EVALUATOR "
        f"publish attempt={current_attempt} status={status} "
        f"x={float(position[0]):.4f} y={float(position[1]):.4f} "
        f"z={float(position[2]):.4f}",
        flush=True,
    )
