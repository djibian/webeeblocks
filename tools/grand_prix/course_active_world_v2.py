"""Host-only variable Grand Prix world composition, NOT a flight qualification.

This composes the already verified static CoursePlan scene with the *declared*
route flight, Robot Window, and non-colliding Supervisor identities. The active
evaluator publisher, fresh RESET/admission, real contacts and sensors, and the
Linux user journey are separate deliverables. This module NEVER runs Webots or
grants READY; without a live evaluator the native flight guard must refuse
TAKEOFF. Do not offer this scene from the user-facing launcher yet.
"""
from tools.grand_prix.course_static_world_v2 import static_course_world
from tools.grand_prix.route_courses_v2 import CoursePlan, course_from_identifier

FLIGHT_CONTROLLER = "grand_prix_route_flight"
ROBOT_WINDOW = "grand_prix_route_v2"
EVALUATOR_CONTROLLER = "grand_prix_route_evaluator"
EVALUATOR_DEF = "GP_ROUTE_EVALUATOR"

_INERT_FLIGHT = ('  controller "<none>"\n'
                 '  window "<none>"\n'
                 '  supervisor TRUE\n')


def active_course_world(course):
    """Serialize host-only WorldInfo, robot and evaluator for one CoursePlan.

    Physical L/H/final solids and course boundaries come exclusively from
    static_course_world, which rejects noncanonical or changed scene anchors.
    No hidden route/seed is included in Blockly or the pupil project.
    """
    if type(course) is not CoursePlan or course_from_identifier(course.identifier) != course:
        raise ValueError("canonical CoursePlan required")
    inert = static_course_world(course)
    title = "Grand Prix STATIC " + course.identifier
    if (inert.count(_INERT_FLIGHT) != 1 or
            inert.count('controller "<none>"') != 1 or
            inert.count('window "<none>"') != 1 or
            inert.count("controllerArgs") != 0 or
            inert.count(title) != 1 or
            not inert.endswith("}\n") or
            EVALUATOR_DEF in inert or
            'controller "grand_prix_u_flight"' in inert or
            'window "grand_prix_u"' in inert):
        raise RuntimeError("noncanonical static robot/evaluator anchors; refusing composition")

    identifier = course.identifier
    flight = (f'  controller "{FLIGHT_CONTROLLER}"\n'
              f'  window "{ROBOT_WINDOW}"\n'
              f'  controllerArgs [ "{identifier}" ]\n'
              '  supervisor TRUE\n')
    scene = inert.replace(_INERT_FLIGHT, flight, 1)
    scene = scene.replace(title, "Grand Prix variable EXPERIMENTAL " + identifier, 1)
    # The evaluator is a non-physical Robot; the already-validated collider
    # inventory and floor remain byte-identical to the static scene.
    evaluator = (
        f'DEF {EVALUATOR_DEF} Robot {{\n'
        '  name "Évaluateur Grand Prix variable"\n'
        '  supervisor TRUE\n'
        '  synchronization TRUE\n'
        f'  controller "{EVALUATOR_CONTROLLER}"\n'
        f'  controllerArgs [ "{identifier}" ]\n'
        '  description ""\n'
        '}\n'
    )
    return scene + evaluator
