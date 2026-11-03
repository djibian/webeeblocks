"""Complete static variable-course Webots geometry; deliberately no mission.

Build all physical L, open H and terminal H solids from one immutable
CoursePlan. Red dashed guides are rendered from the *same full-course*
boundary primitive used by the strict geometry oracle, not corridor-only tape.
This is host-only R2025a scene preparation, not native sensing, RESET, READY,
Blockly, simulator flight, deadline or landing qualification.
"""
from dataclasses import dataclass

from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier
from tools.grand_prix.route_solid_v2 import (
    HEIGHT as L_HEIGHT, corner_boxes, static_world, visual, visual_guides,
)
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes
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
    base = base.replace(old_guides_block, '\n'.join(whites + red) + '\n', 1)

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
