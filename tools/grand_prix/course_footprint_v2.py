"""Shared full-course boundary for the variable GP world and oracle (#811).

Unlike the historical corridor-only primitive, this includes the widened
arrival and ends at the closed H plane. This geometry grants no progression,
gate crossing, low-flight exception or native flight qualification.
"""
import math
from tools.grand_prix.route_v2 import Route, WIDTH
from tools.grand_prix.route_terminal_v2 import ARRIVAL_LENGTH, ARRIVAL_WIDTH
from tools.grand_prix.corridor_sweep_v2 import (
    RADIUS, EPS, _boundary_edges, _swept_clearance,
)


def _bounds(points):
    return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))


def course_rectangles(route):
    """Closed union in world XY; last leg is clipped at its terminal H.

    The 0.60m corridors keep their 0.30m junction extensions. Only the last
    longitudinal end is clipped, because the H closes that end of the course.
    The arrival is the existing 1.80m x 0.95m rectangle, not a new tolerance.
    """
    if not isinstance(route, Route) or len(route.legs) != 3:
        raise ValueError('three-leg Route required')
    first, middle, last = route.legs
    terminal_corridor = _bounds(tuple(last.at(a, b) for a in (
        -WIDTH/2, last.length) for b in (-WIDTH/2, WIDTH/2)))
    arrival = _bounds(tuple(last.at(a, b) for a in (
        last.length-ARRIVAL_LENGTH, last.length)
        for b in (-ARRIVAL_WIDTH/2, ARRIVAL_WIDTH/2)))
    # The permitted route lengths keep the terminal widening separate from
    # earlier legs. Fail closed if a future geometry changes that premise.
    for rectangle in (first.bounds(), middle.bounds()):
        if (min(rectangle[2], arrival[2]) > max(rectangle[0], arrival[0]) and
                min(rectangle[3], arrival[3]) > max(rectangle[1], arrival[1])):
            raise ValueError('arrival overlaps an earlier corridor')
    return (first.bounds(), middle.bounds(), terminal_corridor, arrival)


def course_boundary_edges(route):
    """Single exact union boundary for visible tape and capsule enforcement."""
    return _boundary_edges(course_rectangles(route))


def swept_course_clearance(route, before, after):
    """Continuous XY clearance in metres; -1 means an endpoint is outside."""
    return _swept_clearance(course_rectangles(route), before, after)


def swept_capsule_inside_course(route, before, after):
    """Strict 0.09m craft-envelope containment, including concave vertices."""
    return swept_course_clearance(route, before, after) > RADIUS + EPS


def red_boundary_marks(route):
    """Non-colliding dashed tape from the exact *full* enforced boundary.

    Returns world-aligned (x, y, sx, sy) boxes for scene rendering. Includes
    start/end edges and arrival widening; no internal corridor/arrival seams.
    The final H may visually occlude its own floor tape.
    """
    marks = []
    for a, b in course_boundary_edges(route):
        length = math.dist(a, b)
        for index in range(math.ceil(length/.30)):
            offset = index*.30
            span = min(.18, length-offset)
            if span <= .015:
                continue
            t = (offset+span/2)/length
            x, y = (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)
            sx, sy = (span, .012) if a[1] == b[1] else (.012, span)
            marks.append((x, y, sx, sy))
    return tuple(marks)
