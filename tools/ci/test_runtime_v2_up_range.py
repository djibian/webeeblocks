#!/usr/bin/env python3
"""Static wiring contract for the Runtime v2 upward Multi-ranger path."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runtime_worlds = [
    ROOT / "worlds" / "crazyflie_runtime_obstacle.wbt",
    ROOT / "worlds" / "crazyflie_runtime_v2.wbt",
]
controller = (ROOT / "controllers" / "crazyflie_runtime_v2" / "crazyflie_runtime_v2.c").read_text(encoding="utf-8")
backend = (ROOT / "plugins" / "robot_windows" / "blockly" / "webeeblocks" / "wwi_backend.js").read_text(encoding="utf-8")

for world_path in runtime_worlds:
    world = world_path.read_text(encoding="utf-8")
    assert 'name "range_up"' in world, world_path
    assert 'rotation 0 1 0 -1.57079632679' in world, world_path

assert 'wb_robot_get_device("range_up")' in controller
assert '!range_up' in controller
assert 'wb_distance_sensor_enable(range_up, step);' in controller
assert 'strcmp(request.direction, "up") == 0' in controller
assert 'range_sensor = range_up;' in controller
assert "rangeDirections: ['front', 'back', 'left', 'right', 'up']" in backend

print('PASS Runtime v2 upward Multi-ranger wiring contract')
