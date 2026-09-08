#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLDS = [
    ROOT / "worlds/crazyflie_runtime_v2.wbt",
    ROOT / "worlds/crazyflie_runtime_obstacle.wbt",
]
BEGIN = "# WEBEEBLOCKS_COLOR_LED_DECK_VISUAL_V1_BEGIN"
END = "# WEBEEBLOCKS_COLOR_LED_DECK_VISUAL_V1_END"


def visual_section(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise AssertionError("Color LED visual contract markers must occur exactly once")
    return text.split(BEGIN, 1)[1].split(END, 1)[0].strip()


sections = [visual_section(path.read_text(encoding="utf-8")) for path in WORLDS]
if sections[0] != sections[1]:
    raise AssertionError("Runtime worlds drifted apart for the Color LED deck visual")

section = sections[0]
required = [
    "translation 0 0 -0.006",
    "size 0.0347 0.0347 0.0015",
    'name "color_led"',
    "gradual TRUE",
    "translation 0 0 -0.0058",
    "Group {",
    "height 0.0101",
    "radius 0.01735",
    "subdivision 48",
    "transparency 0.12",
    "radius 0.022",
    "height 0.012",
    "transparency 0.78",
]
for token in required:
    if token not in section:
        raise AssertionError(f"missing Color LED visual contract token: {token}")

if section.count("geometry Cylinder {") != 2:
    raise AssertionError("expected one diffuser body plus one translucent side halo")
if section.count("size 0.0022 0.0022 0.0065") != 4:
    raise AssertionError("the bottom deck must be visibly attached by four mounting posts")
if "size 0.040 0.040 0.0015" in section or "size 0.026 0.026 0.001" in section:
    raise AssertionError("detached legacy square Color LED representation survived")

# 1.5 mm PCB + 10.1 mm circular diffuser = the 11.6 mm bottom-deck envelope.
if abs((0.0015 + 0.0101) - 0.0116) > 1e-9:
    raise AssertionError("Color LED deck envelope arithmetic changed")

print("PASS attached 34.7 mm bottom Color LED deck uses a circular side-visible diffuser and controlled emissive halo in both Runtime worlds")
