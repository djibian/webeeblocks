"""Complete static variable-course Webots geometry; deliberately no mission.

Build all physical L, open H and terminal H solids from one immutable
CoursePlan. Red dashed guides are rendered from the *same full-course*
boundary primitive used by the strict geometry oracle, not corridor-only tape.
This is host-only R2025a scene preparation, not native sensing, RESET, READY,
Blockly, simulator flight, deadline or landing qualification.
"""
from dataclasses import dataclass

from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier, LOW_BEFORE, LOW_AFTER
from tools.grand_prix.route_solid_v2 import (
    HEIGHT as L_HEIGHT, corner_boxes, static_world, visual, visual_guides,
)
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes, landing_targets, LANDING_TILE
from tools.grand_prix.course_footprint_v2 import red_boundary_marks


@dataclass(frozen=True)
class CoursePhysicalBox:
    name: str
    position: tuple[float, float, float]
    size: tuple[float, float, float]


def _canonical(course):
    if type(course) is not CoursePlan:
        raise ValueError('canonical CoursePlan required')
    if course_from_identifier(course.identifier) != course:
        raise ValueError('forged or inconsistent CoursePlan')


def course_physical_boxes(course):
    """Canonical ordered native attestation input: four L, 3H, four terminal.

    Conversion into the chosen Supervisor attestation API happens later on
    the evaluator side; this pure host manifest does not authorize READY.
    """
    _canonical(course)
    result = []
    for box in corner_boxes(course.route):
        result.append(CoursePhysicalBox(box.name, (box.x, box.y, L_HEIGHT/2),
                                        (box.sx, box.sy, L_HEIGHT)))
    for box in open_h_boxes(course):
        result.append(CoursePhysicalBox(box.name, (box.x, box.y, box.z),
                                        (box.sx, box.sy, box.sz)))
    for box in terminal_boxes(course.route):
        result.append(CoursePhysicalBox(box.name, (box.x, box.y, box.z),
                                        (box.sx, box.sy, box.sz)))
    names = [box.name for box in result]
    if len(result) != 8 + 3*course.count or len(set(names)) != len(names):
        raise ValueError('incomplete or duplicate physical course manifest')
    return tuple(result)


def static_course_world(course):
    """Compose an unpowered observable course, not an active Grand Prix.

    Fail closed on changed upstream static-world anchors rather than partially
    rewriting an unknown robot, guides, obstacles or evaluator.
    """
    _canonical(course)
    route = course.route
    solids = (tuple(box.vrml() for box in corner_boxes(route)) +
              tuple(box.vrml() for box in open_h_boxes(course)) +
              tuple(box.vrml() for box in terminal_boxes(route)))
    if len(solids) != len(course_physical_boxes(course)):
        raise RuntimeError('composed physical inventory differs from manifest')
    base = static_world(route)

    old_guides = visual_guides(route)
    old_guides_block = '\n'.join(old_guides) + '\n'
    whites = tuple(item for item in old_guides
                   if item.startswith('DEF GP_V2_WHITE_'))
    if len(whites) != 3 or base.count(old_guides_block) != 1:
        raise RuntimeError('static scene guide anchors changed')
    red = tuple(visual(f'GP_V2_COURSE_RED_{index}', x, y, sx, sy, '.95 .06 .06')
                for index, (x, y, sx, sy) in enumerate(red_boundary_marks(route)))
    if not red:
        raise RuntimeError('empty complete-course boundary')

    # Teacher-visible start, direction-relative landing choices and the exact
    # 0.55 m low-flight band edges are decorative floor marks. They grant no
    # sensing API, safety exception or attempt/mission authority. Keep their
    # names distinct from the reserved GP_V2 physical inventory.
    overlay = [visual('GP_ROUTE_START', 0., 0., LANDING_TILE, LANDING_TILE,
                      '.12 .42 .90')]
    for number, (x, y) in enumerate(landing_targets(route), start=1):
        overlay.append(visual(f'GP_ROUTE_TARGET_{number}', x, y,
                              LANDING_TILE, LANDING_TILE, '.10 .72 .28'))
        # Keep the accepted 25 cm black/white 4x4 checkerboard inside the
        # 28 cm green tile, leaving a 15 mm border on every side. Pure Pose:
        # no collision, range API, landing permission or oracle inference.
        for col in range(4):
            for row in range(4):
                tx = x - .125 + (col + .5) * .0625
                ty = y - .125 + (row + .5) * .0625
                shade = '.06 .06 .06' if (col + row) % 2 == 0 else '.96 .96 .96'
                overlay.append(
                    f'DEF GP_ROUTE_TARGET_{number}_CELL_{col}_{row} Pose {{ '
                    f'translation {tx:.6f} {ty:.6f} .0042 children [ Shape {{ '
                    f'appearance PBRAppearance {{ baseColor {shade} roughness 1 }} '
                    'geometry Box { size .0625 .0625 .0002 } } ] }')
    for index, gate in enumerate(course.gates):
        leg = route.legs[gate.leg_index]
        pitch = .60 / 8
        for side, along in (('BEFORE', gate.along - LOW_BEFORE),
                            ('AFTER', gate.along + LOW_AFTER)):
            for dash in range(8):
                lateral = -.30 + (dash + .5) * pitch
                x, y = leg.at(along, lateral)
                sx, sy = ((.012, pitch / 2) if leg.direction % 2 == 0
                          else (pitch / 2, .012))
                overlay.append(visual(f'GP_ROUTE_BAND_{index}_{side}_{dash}',
                                      x, y, sx, sy, '.98 .85 .10'))
    base = base.replace(old_guides_block,
                        '\n'.join(whites + red + tuple(overlay)) + '\n', 1)

    l_solids = tuple(box.vrml() for box in corner_boxes(route))
    l_block = '\n'.join(l_solids) + '\n'
    if base.count(l_block) != 1:
        raise RuntimeError('static scene physical L anchor changed')
    additions = solids[len(l_solids):]
    base = base.replace(l_block, l_block + '\n'.join(additions) + '\n', 1)
    old_title = 'L-corner STATIC ' + route.identifier
    if base.count(old_title) != 1:
        raise RuntimeError('static scene world identity changed')
    base = base.replace(old_title, 'Grand Prix STATIC ' + course.identifier, 1)

    # Composition must remain inert until #824 establishes the native
    # attempt-bound evaluator and explicit post-RESET admission handshake.
    if (base.count('controller "<none>"') != 1 or
            base.count('window "<none>"') != 1 or
            'GP_ROUTE_EVALUATOR' in base or
            'controller "grand_prix_u_flight"' in base or
            'controller "grand_prix_route_v2"' in base):
        raise RuntimeError('static world accidentally has mission authority')
    return base
