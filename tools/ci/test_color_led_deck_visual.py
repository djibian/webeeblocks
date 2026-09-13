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

# The pinned Webots R2025a Crazyflie mesh places cf_body.001 at +15 mm in the
# BODY/extensionSlot coordinate system. Its PCB vertices span +/-1.246929 mm in
# local Z, so this is the lower mounting surface the four visual posts must meet.
# Source: projects/robots/bitcraze/crazyflie/protos/meshes/cf2_assembly.dae at
# the same R2025a revision used by the Runtime worlds.
R2025A_BODY_PCB_BOTTOM_Z = 0.015 - 0.001246929
CONTACT_TOLERANCE = 0.00002
MAX_CONTACT_OVERLAP = 0.00025


def visual_section(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise AssertionError("Color LED visual contract markers must occur exactly once")
    return text.split(BEGIN, 1)[1].split(END, 1)[0].strip()


def one_float(pattern: str, text: str, label: str, flags: int = 0) -> float:
    match = re.search(pattern, text, flags)
    if match is None:
        raise AssertionError(f"missing Color LED geometry value: {label}")
    return float(match.group(1))


sections = [visual_section(path.read_text(encoding="utf-8")) for path in WORLDS]
if sections[0] != sections[1]:
    raise AssertionError("Runtime worlds drifted apart for the Color LED deck visual")

section = sections[0]
required = [
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

# Reject the exact failure observed on Windows: posts may exist structurally but
# still stop below the rendered Crazyflie PCB. Derive the actual post endpoints
# from the world geometry and require physical visual contact with the pinned
# R2025a body mounting plane, allowing only a tiny overlap to avoid render seams.
deck_z = one_float(
    r"\APose \{\s*\n\s*translation 0 0 ([-+0-9.eE]+)", section, "deck translation"
)
pcb_height = one_float(
    r"geometry Box \{\s*\n\s*size 0\.0347 0\.0347 ([-+0-9.eE]+)",
    section,
    "deck PCB height",
)
post_centers = [
    float(value)
    for value in re.findall(
        r"translation -?0\.0135 -?0\.0135 ([-+0-9.eE]+)", section
    )
]
post_heights = [
    float(value)
    for value in re.findall(r"size 0\.0022 0\.0022 ([-+0-9.eE]+)", section)
]
if len(post_centers) != 4 or len(post_heights) != 4:
    raise AssertionError("expected four measurable Color LED mounting posts")
if len(set(post_centers)) != 1 or len(set(post_heights)) != 1:
    raise AssertionError("Color LED mounting posts must share one vertical geometry")
post_center_z = post_centers[0]
post_height = post_heights[0]

pcb_top = deck_z + pcb_height / 2.0
post_bottom = deck_z + post_center_z - post_height / 2.0
post_top = deck_z + post_center_z + post_height / 2.0
if abs(post_bottom - pcb_top) > 1e-9:
    raise AssertionError(
        f"Color LED posts detached from their PCB: post bottom={post_bottom:.9f}, "
        f"PCB top={pcb_top:.9f}"
    )

contact_overlap = post_top - R2025A_BODY_PCB_BOTTOM_Z
if contact_overlap < -CONTACT_TOLERANCE:
    raise AssertionError(
        f"Color LED deck visibly detached from Crazyflie: {abs(contact_overlap):.6f} m gap"
    )
if contact_overlap > MAX_CONTACT_OVERLAP:
    raise AssertionError(
        f"Color LED mounting posts penetrate Crazyflie PCB by {contact_overlap:.6f} m"
    )
if pcb_top >= R2025A_BODY_PCB_BOTTOM_Z:
    raise AssertionError("Color LED PCB must remain below the Crazyflie mounting plane")

led_relative_z = one_float(
    r"LED \{\s*\n\s*translation 0 0 ([-+0-9.eE]+)", section, "LED translation"
)
diffuser_height = one_float(
    r"LED \{.*?geometry Cylinder \{\s*\n\s*height ([-+0-9.eE]+)",
    section,
    "diffuser height",
    re.DOTALL,
)
pcb_bottom = deck_z - pcb_height / 2.0
diffuser_top = deck_z + led_relative_z + diffuser_height / 2.0
if abs(diffuser_top - pcb_bottom) > 1e-9:
    raise AssertionError(
        f"Color LED diffuser detached from PCB: diffuser top={diffuser_top:.9f}, "
        f"PCB bottom={pcb_bottom:.9f}"
    )

# 1.5 mm PCB + 10.1 mm circular diffuser = the 11.6 mm bottom-deck envelope.
if abs((0.0015 + 0.0101) - 0.0116) > 1e-9:
    raise AssertionError("Color LED deck envelope arithmetic changed")

print(
    "PASS attached 34.7 mm bottom Color LED deck has four posts contacting the "
    "pinned R2025a Crazyflie PCB plus a side-visible controlled diffuser in both Runtime worlds"
)
