#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source_path = ROOT / "worlds/crazyflie_runtime_v2.wbt"
target_path = ROOT / "worlds/.ci_color_led_visual_render.wbt"
source = source_path.read_text(encoding="utf-8")

# The fixed Color LED render proves the deck attached to the product Crazyflie.
# Product worlds may also host independent supervisor/evaluator robots. Remove
# only the explicitly bounded progression evaluator fixture before selecting the
# Crazyflie controller so unrelated product observers cannot make this visual
# probe ambiguous or execute alongside it.
sequence_begin = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN"
sequence_end = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_END"
if source.count(sequence_begin) != source.count(sequence_end):
    raise AssertionError("unbalanced sequence evaluator markers")
if source.count(sequence_begin) > 1:
    raise AssertionError("expected at most one sequence evaluator fixture")

visual_source = source
if sequence_begin in source:
    start = source.index(sequence_begin)
    end = source.index(sequence_end, start) + len(sequence_end)
    evaluator = source[start:end]
    if 'name "Progression sequence evaluator"' not in evaluator or 'controller "crazyflie_runtime_v2"' not in evaluator:
        raise AssertionError("unexpected sequence evaluator fixture")
    visual_source = source[:start] + source[end:]

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
    if visual_source.count(token) != 1:
        raise AssertionError(f"expected exactly one visual-source token: {token}")

if visual_source.count("Viewpoint {") != 1 or visual_source.count("Crazyflie {") != 1:
    raise AssertionError("Runtime render fixture expects one Viewpoint and one Crazyflie")

render = visual_source.replace("Viewpoint {", "DEF VISUAL_VIEWPOINT Viewpoint {", 1)
render = render.replace(
    'Crazyflie {\n  name "Crazyflie WebeeBlocks"',
    'Crazyflie {\n  translation 0 0 0.18\n  name "Crazyflie WebeeBlocks"',
    1,
)
render = render.replace('  controller "crazyflie_runtime_v2"\n', '  controller "color_led_visual_probe"\n', 1)
render = render.replace('  window "blockly_v2"\n', "", 1)

if render == visual_source:
    raise AssertionError("render fixture transformation was a no-op")
if 'controller "crazyflie_runtime_v2"' in render or 'window "blockly_v2"' in render:
    raise AssertionError("product controller/window leaked into fixed visual probe")
if render.count('controller "color_led_visual_probe"') != 1:
    raise AssertionError("fixed visual probe controller missing")
if sequence_begin in render or sequence_end in render or 'name "Progression sequence evaluator"' in render:
    raise AssertionError("unrelated sequence evaluator leaked into fixed visual probe")

target_path.write_text(render, encoding="utf-8")
print(target_path)
