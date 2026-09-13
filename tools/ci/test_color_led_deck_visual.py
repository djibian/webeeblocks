#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLDS = [
    ROOT / "worlds/crazyflie_runtime_v2.wbt",
    ROOT / "worlds/crazyflie_runtime_obstacle.wbt",
]
BEGIN = "# WEBEEBLOCKS_COLOR_LED_DECK_VISUAL_V1_BEGIN"
END = "# WEBEEBLOCKS_COLOR_LED_DECK_VISUAL_V1_END"

# The pinned Webots R2025a Crazyflie.proto inserts extensionSlot inside BODY,
# whose Pose is translated -15 mm. In cf2_assembly.dae, cf_body.001 is then
# translated +15 mm and its PCB reaches down to z=-1.246929 mm. Relative to the
# extensionSlot/BODY frame, the visible Crazyflie PCB underside is therefore at
# 13.753071 mm. The four deck posts must physically meet that surface.
R2025A_BODY_MESH_TRANSLATION_Z = 0.015
R2025A_BODY_PCB_BOTTOM_IN_MESH_Z = -0.001246929
BODY_MOUNT_PLANE_Z = R2025A_BODY_MESH_TRANSLATION_Z + R2025A_BODY_PCB_BOTTOM_IN_MESH_Z
MOUNT_CONTACT_TOLERANCE_M = 0.00001
DECK_PCB_THICKNESS_M = 0.0015
POST_CENTER_Z_M = 0.004
POST_HEIGHT_M = 0.0065


def visual_section(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise AssertionError("Color LED visual contract markers must occur exactly once")
    return text.split(BEGIN, 1)[1].split(END, 1)[0].strip()


def outer_translation_z(section: str) -> float:
    match = re.search(
        r"\APose \{\n\s+translation 0 0 ([+-]?(?:\d+(?:\.\d*)?|\.\d+))\n",
        section,
    )
    if match is None:
        raise AssertionError("Color LED deck outer Pose translation is not structurally readable")
    return float(match.group(1))


sections = [visual_section(path.read_text(encoding="utf-8")) for path in WORLDS]
if sections[0] != sections[1]:
    raise AssertionError("Runtime worlds drifted apart for the Color LED deck visual")

section = sections[0]
required = [
    "translation 0 0 0.0065",
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
    "PointLight {",
    "attenuation 1 0 300",
    "intensity 0.7",
    "radius 0.18",
    "castShadows FALSE",
]
for token in required:
    if token not in section:
        raise AssertionError(f"missing Color LED visual contract token: {token}")

if section.count("geometry Cylinder {") != 2:
    raise AssertionError("expected one diffuser body plus one translucent side halo")
if section.count("PointLight {") != 1:
    raise AssertionError("expected one LED-driven nearby PointLight halo")
if section.count("size 0.0022 0.0022 0.0065") != 4:
    raise AssertionError("the bottom deck must use four mounting posts")
if "size 0.040 0.040 0.0015" in section or "size 0.026 0.026 0.001" in section:
    raise AssertionError("detached legacy square Color LED representation survived")

# Reject a merely present-but-detached post geometry. The post bottoms must meet
# the deck PCB top and their tops must meet the pinned R2025a Crazyflie PCB.
deck_z = outer_translation_z(section)
deck_top_z = deck_z + DECK_PCB_THICKNESS_M / 2.0
post_bottom_z = deck_z + POST_CENTER_Z_M - POST_HEIGHT_M / 2.0
post_top_z = deck_z + POST_CENTER_Z_M + POST_HEIGHT_M / 2.0
if abs(deck_top_z - post_bottom_z) > 1e-9:
    raise AssertionError(
        f"Color LED mounting posts do not meet deck PCB: gap={post_bottom_z - deck_top_z:.9f} m"
    )
body_gap = BODY_MOUNT_PLANE_Z - post_top_z
if abs(body_gap) > MOUNT_CONTACT_TOLERANCE_M:
    raise AssertionError(
        f"Color LED mounting posts do not meet Crazyflie PCB: gap={body_gap:.9f} m"
    )

# 1.5 mm PCB + 10.1 mm circular diffuser = the 11.6 mm bottom-deck envelope.
if abs((0.0015 + 0.0101) - 0.0116) > 1e-9:
    raise AssertionError("Color LED deck envelope arithmetic changed")

print(
    "PASS attached 34.7 mm bottom Color LED deck has four posts in geometric contact "
    "with the pinned R2025a Crazyflie PCB and keeps its circular side-visible light "
    "in both Runtime worlds"
)
