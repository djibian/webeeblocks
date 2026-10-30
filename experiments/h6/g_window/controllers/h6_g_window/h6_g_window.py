#!/usr/bin/env python3
"""Real Supervisor API collision -> teleport -> global/node physics reset probe."""
import os
import sys
from controller import Supervisor

robot = Supervisor()
step = int(robot.getBasicTimeStep())
target = robot.getFromDef("TARGET")
if target is None:
    raise SystemExit("REFUSED: TARGET missing")
translation = target.getField("translation")
kind = os.environ.get("H6_G_WINDOW_PATH")
if kind not in ("global", "node"):
    raise SystemExit("REFUSED: H6_G_WINDOW_PATH must be global/node")
print("H6_G_WINDOW controller=started path=" + kind, flush=True)

# Read-only settle phase: require actual collision observation in native plugin,
# never claim a contact from elapsed time alone.
for i in range(36):
    if robot.step(step) == -1:
        raise SystemExit("REFUSED: premature simulation end")
print("H6_G_WINDOW controller=about_to_reset path=" + kind + " t=" + str(robot.getTime()), flush=True)
# Queue target relocation and physics reset in the SAME controller request.
translation.setSFVec3f([0.31, 0.17, 0.8])
if kind == "global":
    robot.simulationResetPhysics()
else:
    target.resetPhysics()
print("H6_G_WINDOW controller=requested path=" + kind, flush=True)
for i in range(8):
    if robot.step(step) == -1:
        raise SystemExit("REFUSED: missing post-reset steps")
print("H6_G_WINDOW controller=complete path=" + kind + " t=" + str(robot.getTime()), flush=True)
sys.stdout.flush()
robot.simulationQuit(0)
