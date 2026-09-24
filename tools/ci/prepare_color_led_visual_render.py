#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source_path = ROOT / "worlds/crazyflie_runtime_v2.wbt"
target_path = ROOT / "worlds/.ci_color_led_visual_render.wbt"
source = source_path.read_text(encoding="utf-8")

# The fixed Color LED render proves the deck attached to the product Crazyflie.
# Product worlds may also host independent supervisor/evaluator robots. Remove
# only explicitly bounded evaluator fixtures before selecting the Crazyflie
# controller so unrelated observers cannot make this visual probe ambiguous.
evaluators = (
    (
        "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN",
        "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_END",
        'name "Progression sequence evaluator"',
        '"sequence-evaluator-v1"',
    ),
    (
        "# WEBEEBLOCKS_PRECISE_EVALUATOR_V1_BEGIN",
        "# WEBEEBLOCKS_PRECISE_EVALUATOR_V1_END",
        'name "Progression precise movement evaluator"',
        '"precise-evaluator-v1"',
    ),
    (
        "# WEBEEBLOCKS_REPEAT_EVALUATOR_V1_BEGIN",
        "# WEBEEBLOCKS_REPEAT_EVALUATOR_V1_END",
        'name "Progression repeat evaluator"',
        '"repeat-evaluator-v1"',
    ),
    (
        "# WEBEEBLOCKS_SIMPLE_DECISION_EVALUATOR_V1_BEGIN",
        "# WEBEEBLOCKS_SIMPLE_DECISION_EVALUATOR_V1_END",
        'name "Progression simple decision evaluator"',
        '"simple-decision-evaluator-v1"',
    ),
    (
        "# WEBEEBLOCKS_REACTIVE_EVALUATOR_V1_BEGIN",
        "# WEBEEBLOCKS_REACTIVE_EVALUATOR_V1_END",
        'name "Progression reactive evaluator"',
        '"reactive-evaluator-v1"',
    ),
    (
        "# WEBEEBLOCKS_COMBINED_DECISIONS_EVALUATOR_V1_BEGIN",
        "# WEBEEBLOCKS_COMBINED_DECISIONS_EVALUATOR_V1_END",
        'name "Progression combined decisions evaluator"',
        '"combined-decisions-evaluator-v1"',
    ),
)

visual_source = source
for begin, end_marker, expected_name, expected_arg in evaluators:
    if visual_source.count(begin) != visual_source.count(end_marker):
        raise AssertionError(f"unbalanced evaluator markers: {begin}")
    if visual_source.count(begin) > 1:
        raise AssertionError(f"expected at most one evaluator fixture: {begin}")
    if begin not in visual_source:
        continue
    start = visual_source.index(begin)
    end = visual_source.index(end_marker, start) + len(end_marker)
    evaluator = visual_source[start:end]
    if expected_name not in evaluator or 'controller "crazyflie_runtime_v2"' not in evaluator or expected_arg not in evaluator:
        raise AssertionError(f"unexpected evaluator fixture: {begin}")
    visual_source = visual_source[:start] + visual_source[end:]

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
for begin, end_marker, expected_name, _ in evaluators:
    if begin in render or end_marker in render or expected_name in render:
        raise AssertionError("unrelated evaluator leaked into fixed visual probe")

target_path.write_text(render, encoding="utf-8")
print(target_path)
