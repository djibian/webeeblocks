#!/usr/bin/env python3
from pathlib import Path

from controller import Supervisor

INITIAL = "WEBEEBLOCKS_CI_RESTART_INITIAL"
RESTARTED = "WEBEEBLOCKS_CI_RESTARTED_CONTROLLER"

robot = Supervisor()
time_step = int(robot.getBasicTimeStep())
target = robot.getFromDef("ROBOT")
project = Path(robot.getProjectPath())
controller_path = project / "controllers" / "my_controller" / "my_controller.py"

print("WEBEEBLOCKS_CI_RESTART_SUPERVISOR_STARTED", flush=True)

# Let the initial controller start and print its marker.
for _ in range(12):
    if robot.step(time_step) == -1:
        raise SystemExit(1)

controller_path.write_text(
    "from controller import Robot\n"
    "robot = Robot()\n"
    f"print('{RESTARTED}', flush=True)\n"
    "while robot.step(int(robot.getBasicTimeStep())) != -1:\n"
    "    pass\n",
    encoding="utf-8",
)

# Exercise the same Webots primitives present in the historical supervisor.
robot.simulationReset()
target.restartController()

for _ in range(30):
    if robot.step(time_step) == -1:
        break

robot.simulationQuit(0)
