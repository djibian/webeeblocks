#!/usr/bin/env python3
"""Activity-1 3D observable-world oracle, isolated from the hash-locked flight runtime.

The controller is spawned *inside* scene sequence-v1 and disappears on scene
switch. It reads only the real Supervisor pose/velocity and runtime customData,
never the pupil's program representation. It cannot command flight.
"""
import math
import re

ORACLE = "progression-sequence-3d-v1"
TARGET_X = 0.35
TARGET_Y = 0.28
TARGET_X_TOLERANCE = 0.09
TARGET_Y_TOLERANCE = 0.12
AIRBORNE_DELTA = 0.20
LANDED_DELTA = 0.07
MAX_LANDING_SPEED = 0.12
SETTLE_TIMEOUT = 1.5

ATTEMPT = re.compile(r"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 ([1-9][0-9]*)")
COMPLETION = re.compile(
    r"WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=([1-9][0-9]*) oracle="
    + re.escape(ORACLE)
)


def parse_attempt(payload):
    match = ATTEMPT.fullmatch(payload or "")
    return int(match[1]) if match else None


def parse_completion(payload, expected_attempt):
    match = COMPLETION.fullmatch(payload or "")
    return bool(match and int(match[1]) == expected_attempt)


class Attempt:
    """An independent finite-state observation for exactly one runtime attempt."""

    def __init__(self, identity, origin_z):
        self.identity = identity
        self.origin_z = origin_z
        self.airborne = False
        self.completed_at = None
        self.result = None

    def sample(self, now, position, velocity, completed):
        if self.result is not None:
            return self.result
        if (position is None or velocity is None or len(position) < 3
                or len(velocity) < 3 or not all(
                    math.isfinite(float(x)) for x in (*position[:3], *velocity[:3], now)
                )):
            # Unknown physical state cannot prove achievement.
            if completed or self.completed_at is not None:
                self.result = "not-achieved"
            return self.result

        x, y, z = position[:3]
        vx, vy, vz = velocity[:3]
        if z >= self.origin_z + AIRBORNE_DELTA:
            self.airborne = True
        if completed and self.completed_at is None:
            self.completed_at = now
        if self.completed_at is None:
            return None
        landed = z <= self.origin_z + LANDED_DELTA
        stationary = math.hypot(vx, vy) <= MAX_LANDING_SPEED and abs(vz) <= MAX_LANDING_SPEED
        in_pad = abs(x - TARGET_X) <= TARGET_X_TOLERANCE and abs(y - TARGET_Y) <= TARGET_Y_TOLERANCE
        if self.airborne and landed and stationary and in_pad:
            self.result = "achieved"
        elif now - self.completed_at >= SETTLE_TIMEOUT:
            self.result = "not-achieved"
        return self.result


def run():
    from controller import Supervisor

    supervisor = Supervisor()
    step = int(supervisor.getBasicTimeStep())
    if step <= 0:
        raise RuntimeError("sequence 3D invalid native timestep")
    scene = supervisor.getFromDef("WEBEEBLOCKS_SEQUENCE_SCENE")
    if scene is None or scene.getTypeName() != "Group" or scene.getField("children").getCount() != 18:
        raise RuntimeError("sequence 3D scene identity unavailable")
    children = supervisor.getRoot().getField("children")
    craft = None
    for index in range(children.getCount()):
        node = children.getMFNode(index)
        field = node.getField("name")
        if field is not None and field.getSFString() == "Crazyflie WebeeBlocks":
            if craft is not None:
                raise RuntimeError("sequence 3D ambiguous Crazyflie")
            craft = node
    if craft is None:
        raise RuntimeError("sequence 3D Crazyflie unavailable")
    channel = craft.getField("customData")
    if channel is None:
        raise RuntimeError("sequence 3D customData unavailable")
    initial = craft.getPosition()
    if initial is None or len(initial) != 3 or not all(math.isfinite(x) for x in initial):
        raise RuntimeError("sequence 3D initial native pose unavailable")
    origin_z = initial[2]
    current = None
    print("WEBEEBLOCKS_SEQUENCE_3D_READY target_x=0.350 target_y=0.280", flush=True)

    while supervisor.step(step) != -1:
        data = channel.getSFString() or ""
        identity = parse_attempt(data)
        if identity is not None and (current is None or current.identity != identity):
            current = Attempt(identity, origin_z)
            print(f"WEBEEBLOCKS_SEQUENCE_3D_ATTEMPT attempt={identity}", flush=True)
        if current is None:
            continue
        result = current.sample(
            supervisor.getTime(), craft.getPosition(), craft.getVelocity(),
            parse_completion(data, current.identity)
        )
        if result is None:
            continue
        outcome = (
            f"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt={current.identity} "
            f"oracle={ORACLE} status={result}"
        )
        if data != outcome:
            channel.setSFString(outcome)
            print(
                f"WEBEEBLOCKS_SEQUENCE_3D_RESULT attempt={current.identity} status={result}",
                flush=True,
            )


if __name__ == "__main__":
    run()
