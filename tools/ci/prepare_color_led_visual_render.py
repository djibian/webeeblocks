#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source_path = ROOT / "worlds/crazyflie_runtime_v2.wbt"
target_path = ROOT / "worlds/.ci_color_led_visual_render.wbt"
source = source_path.read_text(encoding="utf-8")

required = [
    "# WEBEEBLOCKS_COLOR_LED_DECK_VISUAL_V1_BEGIN",
    "# WEBEEBLOCKS_COLOR_LED_DECK_VISUAL_V1_END",
    'name "color_led"',
    "gradual TRUE",
    "PointLight {",
    'controller "crazyflie_runtime_v2"',
    'window "blockly_v2"',
]
for token in required:
    if source.count(token) != 1:
        raise AssertionError(f"expected exactly one source token: {token}")

if source.count("Viewpoint {") != 1 or source.count("Crazyflie {") != 1:
    raise AssertionError("Runtime render fixture expects one Viewpoint and one Crazyflie")

render = source.replace("Viewpoint {", "DEF VISUAL_VIEWPOINT Viewpoint {", 1)
render = render.replace(
    'Crazyflie {\n  name "Crazyflie WebeeBlocks"',
    'Crazyflie {\n  translation 0 0 0.18\n  name "Crazyflie WebeeBlocks"',
    1,
)
render = render.replace('  controller "crazyflie_runtime_v2"\n', '  controller "color_led_visual_probe"\n', 1)
render = render.replace('  window "blockly_v2"\n', "", 1)

if render == source:
    raise AssertionError("render fixture transformation was a no-op")
if 'controller "crazyflie_runtime_v2"' in render or 'window "blockly_v2"' in render:
    raise AssertionError("product controller/window leaked into fixed visual probe")
if render.count('controller "color_led_visual_probe"') != 1:
    raise AssertionError("fixed visual probe controller missing")

target_path.write_text(render, encoding="utf-8")
print(target_path)
