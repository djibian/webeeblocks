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

# Pinned Webots R2025a cf2_assembly.dae, cf_body.001 PCB underside in the
# Crazyflie BODY/extensionSlot frame. A small tolerance covers mesh decimals.
R2025A_BODY_PCB_UNDERSIDE_Z = -0.001246929
MAX_VISIBLE_MOUNT_GAP = 0.00005
GEOMETRY_EPSILON = 1e-9


def visual_section(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise AssertionError("Color LED visual contract markers must occur exactly once")
    return text.split(BEGIN, 1)[1].split(END, 1)[0].strip()


def number(pattern: str, text: str, label: str) -> float:
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
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
if "size 0.040 0.040 0.0015" in section or "size 0.026 0.026 0.001" in section:
    raise AssertionError("detached legacy square Color LED representation survived")

# Parse the actual mounting geometry instead of accepting hard-coded tokens. The
# previous defect had four posts but still left about 4 mm of visible air between
# the deck PCB and the R2025a Crazyflie PCB.
deck_z = number(r"^Pose \{\s+translation 0 0 ([-+0-9.eE]+)", section, "deck z")
pcb_height = number(r"size 0\.0347 0\.0347 ([-+0-9.eE]+)", section, "deck PCB height")
post_matches = re.findall(
    r"Pose \{\s+translation ([-+0-9.eE]+) ([-+0-9.eE]+) ([-+0-9.eE]+)\s+children \[\s+"
    r"Shape \{\s+appearance PBRAppearance \{[^\n]+\}\s+"
    r"geometry Box \{ size 0\.0022 0\.0022 ([-+0-9.eE]+) \}",
    section,
    re.MULTILINE,
)
if len(post_matches) != 4:
    raise AssertionError("the bottom deck must have exactly four parsed mounting posts")
expected_xy = {
    (-0.0135, -0.0135),
    (-0.0135, 0.0135),
    (0.0135, -0.0135),
    (0.0135, 0.0135),
}
parsed_xy = {(float(x), float(y)) for x, y, _, _ in post_matches}
if parsed_xy != expected_xy:
    raise AssertionError(f"unexpected Color LED mounting-post positions: {sorted(parsed_xy)!r}")

deck_top = deck_z + pcb_height / 2.0
mount_gap = R2025A_BODY_PCB_UNDERSIDE_Z - deck_top
if abs(mount_gap) > MAX_VISIBLE_MOUNT_GAP:
    raise AssertionError(
        "Color LED deck is visibly detached from the pinned R2025a Crazyflie PCB: "
        f"gap={mount_gap * 1000.0:.3f} mm (limit {MAX_VISIBLE_MOUNT_GAP * 1000.0:.3f} mm)"
    )

for x_text, y_text, z_text, height_text in post_matches:
    post_z = float(z_text)
    post_height = float(height_text)
    post_bottom = deck_z + post_z - post_height / 2.0
    post_top = deck_z + post_z + post_height / 2.0
    if abs(post_bottom - deck_top) > GEOMETRY_EPSILON:
        raise AssertionError(
            f"mounting post at ({x_text}, {y_text}) does not start on the deck PCB"
        )
    if post_top <= R2025A_BODY_PCB_UNDERSIDE_Z:
        raise AssertionError(
            f"mounting post at ({x_text}, {y_text}) does not overlap the Crazyflie PCB"
        )

led_z = number(r"LED \{\s+translation 0 0 ([-+0-9.eE]+)", section, "LED z")
diffuser_height = number(r"geometry Cylinder \{\s+height ([-+0-9.eE]+)", section, "diffuser height")
deck_bottom = deck_z - pcb_height / 2.0
diffuser_top = deck_z + led_z + diffuser_height / 2.0
if abs(diffuser_top - deck_bottom) > GEOMETRY_EPSILON:
    raise AssertionError("Color LED diffuser no longer meets the underside of its deck PCB")

# 1.5 mm PCB + 10.1 mm circular diffuser = the 11.6 mm bottom-deck envelope.
if abs((pcb_height + diffuser_height) - 0.0116) > GEOMETRY_EPSILON:
    raise AssertionError("Color LED deck envelope arithmetic changed")

print(
    "PASS bottom Color LED deck is flush with the pinned R2025a Crazyflie PCB "
    f"(mount gap {mount_gap * 1_000_000.0:.1f} um), four posts bridge the interface, "
    "and the circular side-visible diffuser remains attached in both Runtime worlds"
)
