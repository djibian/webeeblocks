#!/usr/bin/env python3
import os
from pathlib import Path
from controller import Supervisor

robot = Supervisor()
step = int(robot.getBasicTimeStep())
led = robot.getDevice("color_led")
if led is None:
    raise RuntimeError("color_led device missing from rendered product geometry")

viewpoint = robot.getFromDef("VISUAL_VIEWPOINT")
if viewpoint is None:
    raise RuntimeError("fixed render Viewpoint missing")
position_field = viewpoint.getField("position")
orientation_field = viewpoint.getField("orientation")
fov_field = viewpoint.getField("fieldOfView")

self_node = robot.getSelf()
translation_field = self_node.getField("translation")
rotation_field = self_node.getField("rotation")

artifact_root = os.environ.get("WEBEEBLOCKS_CI_ARTIFACT_DIR")
if not artifact_root:
    raise RuntimeError("WEBEEBLOCKS_CI_ARTIFACT_DIR is required")
output = Path(artifact_root) / "color-led-render"
output.mkdir(parents=True, exist_ok=True)

views = (
    ("top", [0.0, 0.0, 0.55], [0.0, 0.0, 1.0, 0.0]),
    ("three-quarter", [-0.32, -0.32, 0.34], [0.8125199201, -0.3365567706, -0.4759631495, 1.4322826425]),
    ("side", [0.0, -0.45, 0.18], [1.0, 0.0, 0.0, 1.5707963268]),
)

def capture(view_name, position, orientation, suffix, value):
    translation_field.setSFVec3f([0.0, 0.0, 0.18])
    rotation_field.setSFRotation([0.0, 0.0, 1.0, 0.0])
    self_node.resetPhysics()
    position_field.setSFVec3f(position)
    orientation_field.setSFRotation(orientation)
    fov_field.setSFFloat(0.55)
    led.set(value)
    if robot.step(step) == -1:
        raise RuntimeError("simulation ended before render capture")
    target = output / f"{view_name}-{suffix}.jpg"
    robot.exportImage(str(target), 100)
    if robot.step(step) == -1:
        raise RuntimeError("simulation ended while exporting render evidence")
    print(f"COLOR_LED_RENDER view={view_name} state={suffix} value=0x{value:06x}", flush=True)

for name, position, orientation in views:
    capture(name, position, orientation, "off", 0x000000)
    capture(name, position, orientation, "blue", 0x0000FF)

led.set(0)
robot.step(step)
robot.simulationQuit(0)
