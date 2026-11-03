"""Host-only physical open-H geometry for provisional variable courses (#808).

This does not assemble a Webots mission or authorize a simulated/real flight.
It only converts the exact host-side CoursePlan gate centres/directions into
visible Solid/Box objects. Never expose CoursePlan data to the pupil AST.
"""
from dataclasses import dataclass
import math

from tools.grand_prix.route_v2 import Route
from tools.grand_prix.route_courses_v2 import CoursePlan, GatePlacement, LOW_BEFORE, LOW_AFTER

POST_LENGTH = .48
POST_THICKNESS = .04
POST_OFFSET = .30
BEAM_SPAN = .56
BEAM_THICKNESS = .04
HEIGHT = 1.30
BEAM_BOTTOM = .62


@dataclass(frozen=True)
class OpenHBox:
    name: str
    x: float
    y: float
    z: float
    sx: float
    sy: float
    sz: float

    def vrml(self):
        """Visible, locked Solid whose Box collider matches its rendered Box."""
        size = f'{self.sx:.6f} {self.sy:.6f} {self.sz:.6f}'
        return (f'DEF {self.name} Solid {{ translation {self.x:.6f} '
                f'{self.y:.6f} {self.z:.6f} name "{self.name}" '
                'locked TRUE children [ Shape { '
                'appearance PBRAppearance { baseColor .75 .55 .25 roughness 1 } '
                f'geometry Box {{ size {size} }} }} ] '
                f'boundingObject Box {{ size {size} }} }}')


def open_h_boxes(course):
    """Exactly three tangible objects per H: left post, right post, top beam.

    A provisional CoursePlan is the sole source of coordinates. This geometry
    retains the historical 0.56 m horizontal and 0.62 m high open passage.
    Sensing, swept collisions, altitude bands and full mission safety remain
    separate native/oracle obligations.
    """
    if (not isinstance(course, CoursePlan) or
            not isinstance(course.route, Route) or
            len(course.route.legs) != 3 or
            type(course.count) is not int or course.count not in (1, 2, 3) or
            not isinstance(course.gates, tuple) or
            len(course.gates) != course.count):
        raise ValueError('one to three exact CoursePlan H placements required')

    indices = []
    result = []
    for gate in course.gates:
        if (not isinstance(gate, GatePlacement) or
                type(gate.leg_index) is not int or
                gate.leg_index not in (0, 1, 2) or
                type(gate.direction) is not int or
                type(gate.along) not in (float, int) or
                not math.isfinite(gate.along)):
            raise ValueError('invalid directed gate placement')
        leg = course.route.legs[gate.leg_index]
        if (gate.direction != leg.direction or
                not LOW_BEFORE < gate.along < leg.length - LOW_AFTER or
                gate.position != leg.at(gate.along)):
            raise ValueError('gate/frame mismatch or insufficient low-band margin')
        indices.append(gate.leg_index)

        def box(part, lateral, z, along_size, across_size, height):
            x, y = leg.at(gate.along, lateral)
            sx, sy = ((along_size, across_size) if leg.direction % 2 == 0
                      else (across_size, along_size))
            return OpenHBox(f'GP_V2_H_{leg.index}_{part}', x, y, z,
                            sx, sy, height)

        result.extend((
            box('LEFT', POST_OFFSET, HEIGHT / 2, POST_LENGTH, POST_THICKNESS, HEIGHT),
            box('RIGHT', -POST_OFFSET, HEIGHT / 2, POST_LENGTH, POST_THICKNESS, HEIGHT),
            box('BEAM', 0., (HEIGHT + BEAM_BOTTOM) / 2,
                BEAM_THICKNESS, BEAM_SPAN, HEIGHT - BEAM_BOTTOM),
        ))

    if indices != sorted(set(indices)):
        raise ValueError('H placements must be unique and leg ordered')
    return tuple(result)
