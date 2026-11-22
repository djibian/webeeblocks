"""One-shot recovery geometry on A7's already attested static scene."""
import math
from types import SimpleNamespace

from tools.grand_prix.course_footprint_v2 import swept_course_clearance
from tools.grand_prix.oracle_u import RADIUS, swept_gap


def retreat_direction(attempt, observation):
    """Return the final leg's forward direction when a rear corridor is clear.

    Check the whole rear sweep against other obstacles from flight height
    down to the floor, and the descent column behind the closed H. The H
    itself may already overlap the mission envelope at the start of the
    retreat. Require the craft to be clear of physical contact, upstream
    of its colliders, and above its beam during the initial braking phase.
    """
    course = attempt.course
    if (course.progression is None or course.progression[0] != 7 or
            attempt.progress.leg.active_leg != len(course.route.legs) - 1 or
            observation.time_ms - attempt.last_ms != 8 or
            observation.contacts.points):
        return None
    pose = observation.kinematics.position
    speed = observation.kinematics.velocity
    leg = course.route.legs[-1]
    ux, uy = leg.forward
    # Limit recovery to the low-speed approach qualified by the native test.
    if math.hypot(*speed[:2]) > .15 or abs(speed[2]) > .03:
        return None
    target = (pose[0] - .12 * ux, pose[1] - .12 * uy)
    braking = (pose[0] + .027 * ux, pose[1] + .027 * uy)
    margin = RADIUS + .03  # Allow tracking error and sample skew.
    if swept_course_clearance(course.route, pose[:2], target) <= RADIUS + .005:
        return None
    terminal_hit = False
    along_axis = 0 if ux else 1
    forward = ux or uy
    for box in attempt.boxes:
        x, y, z = box.position
        sx, sy, sz = box.size
        collider = SimpleNamespace(x=x, y=y, z=z, sx=sx, sy=sy, sz=sz)
        horizontal = SimpleNamespace(x=x, y=y, z=0, sx=sx, sy=sy, sz=sz)
        if box.name.startswith('GP_V2_FINAL_'):
            depth = forward * (box.position[along_axis] - pose[along_axis])
            near_face = depth - box.size[along_axis] / 2
            if swept_gap((*target, attempt.origin_z), (*target, pose[2]), collider) <= margin:
                return None
            terminal_hit |= swept_gap(attempt.progress.pose, pose, collider) < RADIUS
            if box.name == 'GP_V2_FINAL_BEAM':
                if near_face <= .055 or pose[2] < z + sz / 2 + RADIUS:
                    return None
            elif swept_gap((*braking, 0), (*target, 0), horizontal) <= .055:
                # Pinned craft radius, including forward drift while braking
                # from the guarded speed. The beam is checked at flight height.
                return None
        else:
            # An XY capsule extruded down to the floor. Ignoring the box's
            # height is conservative for the concurrent retreat and descent.
            if swept_gap((*braking, 0), (*target, 0), horizontal) <= margin:
                return None
    return leg.direction if terminal_hit else None
