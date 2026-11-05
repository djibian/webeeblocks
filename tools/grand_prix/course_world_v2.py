"""Inert R2025a CoursePlan scene: physical L/H/final H, no pupil mission.

A shared, deterministic source for native geometry/contact probes (#824/#825).
No active flight controller, evaluator, Blockly admission, sensor qualification
or pedagogical PASS follows from this static scene.
"""
from pathlib import Path

from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier, LOW_BEFORE, LOW_AFTER
from tools.grand_prix.route_solid_v2 import corner_boxes, visual
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes, landing_targets, LANDING_TILE
from tools.grand_prix.course_footprint_v2 import course_rectangles, red_boundary_marks
from tools.grand_prix.native_collider_contract_v2 import required_box_names, canonical_native_boxes

ROOT = Path(__file__).resolve().parents[2]


def static_course_world(course):
    """Compose one inspectable but non-executable variable course scene.

    Reconstruct the canonical configuration and all collider names before
    emitting VRML. Do not silently fall back to the historical U geometry.
    The Robot remains inert until a separately qualified evaluator, native
    controller and attempt-bound admission are integrated.
    """
    if type(course) is not CoursePlan or course_from_identifier(course.identifier) != course:
        raise ValueError("canonical CoursePlan required for the static world")
    template = (ROOT / "worlds/crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    marker = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN"
    if marker not in template or "Crazyflie {" not in template:
        raise RuntimeError("pinned Webots robot template missing")
    robot = template[template.index("Crazyflie {"):template.index(marker)]
    if (robot.count('controller "crazyflie_runtime_v2"') != 1 or
            robot.count('window "blockly_v2"') != 1):
        raise RuntimeError("unexpected Webots robot/controller template")
    robot = robot.replace('controller "crazyflie_runtime_v2"', 'controller "<none>"')
    robot = robot.replace('window "blockly_v2"', 'window "<none>"')
    externs = tuple(
        line.replace("https://raw.githubusercontent.com/cyberbotics/webots/R2025a/", "webots://")
        for line in template.splitlines() if line.startswith("EXTERNPROTO ")
    )
    if len(externs) != 4:
        raise RuntimeError("unexpected R2025a PROTO inventory")
    solids = corner_boxes(course.route) + open_h_boxes(course) + terminal_boxes(course.route)
    if (tuple(box.name for box in solids) != required_box_names(course) or
            len(solids) != len(canonical_native_boxes(course))):
        raise RuntimeError("incomplete variable physical collider inventory")

    bounds = course_rectangles(course.route)
    xmin = min(rect[0] for rect in bounds) - .8
    ymin = min(rect[1] for rect in bounds) - .8
    xmax = max(rect[2] for rect in bounds) + .8
    ymax = max(rect[3] for rect in bounds) + .8
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    output = [
        "#VRML_SIM R2025a utf8", *externs,
        f'WorldInfo {{ basicTimeStep 8 randomSeed 1 optimalThreadCount 1 title "Grand Prix STATIC — {course.identifier}" }}',
        f'Viewpoint {{ orientation -0.45 0.47 0.76 1.05 position {cx-5:.3f} {cy-5:.3f} 7 }}',
        "TexturedBackground { }", "TexturedBackgroundLight { }",
        f'Floor {{ translation {cx:.6f} {cy:.6f} 0 size {xmax-xmin:.6f} {ymax-ymin:.6f} }}',
    ]

    for leg in course.route.legs:
        x, y = leg.at(leg.length / 2)
        sx, sy = ((leg.length, .025) if leg.direction % 2 == 0
                  else (.025, leg.length))
        output.append(visual(f"GP_V2_WHITE_{leg.index}", x, y, sx, sy, ".96 .96 .96"))
    for index, (x, y, sx, sy) in enumerate(red_boundary_marks(course.route)):
        output.append(visual(f"GP_V2_COURSE_RED_{index}", x, y, sx, sy,
                             ".95 .06 .06"))
    output.append(visual("GP_V2_START", 0., 0., LANDING_TILE, LANDING_TILE,
                         ".12 .42 .90"))
    for number, (x, y) in enumerate(landing_targets(course.route), start=1):
        output.append(visual(f"GP_V2_TARGET_{number}", x, y,
                             LANDING_TILE, LANDING_TILE, ".10 .72 .28"))

    # Yellow bands visualize the existing 0.55 m before/after H limits;
    # they are never physical barriers or an oracle accessible to Blockly.
    for index, gate in enumerate(course.gates):
        leg = course.route.legs[gate.leg_index]
        pitch = .60 / 8
        for side, along in (("BEFORE", gate.along - LOW_BEFORE),
                            ("AFTER", gate.along + LOW_AFTER)):
            for dash in range(8):
                lateral = -.30 + (dash + .5) * pitch
                x, y = leg.at(along, lateral)
                sx, sy = ((.012, pitch / 2) if leg.direction % 2 == 0
                          else (pitch / 2, .012))
                output.append(visual(f"GP_V2_BAND_{index}_{side}_{dash}",
                                     x, y, sx, sy, ".98 .85 .10"))
    output.extend(box.vrml() for box in solids)
    output.append(robot)
    result = "\n".join(output) + "\n"
    if ('controller "grand_prix_u_flight"' in result or
            'controller "grand_prix_route_flight"' in result or
            "GP_ROUTE_EVALUATOR" in result):
        raise RuntimeError("static course must never activate a mission")
    return result
