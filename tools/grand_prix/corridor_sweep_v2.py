"""Exact horizontal swept corridor containment for candidate GP variable routes.

This is a *pure* radius-aware geometry primitive (#811), not the mission oracle.
It does not decide segment progress, H crossings, collisions, altitude, landing,
RESET or the independent 210000 ms LAND/failure. It does not include the
future widened terminal area; never substitute it for the full mission oracle.
"""
import math
from tools.grand_prix.route_v2 import Route

RADIUS = 0.09  # Fixed craft envelope from the existing GP simulation contract.
EPS = 1e-9


def _point(point):
    if (not isinstance(point, (tuple, list)) or len(point) != 2 or
            any(type(x) not in (float, int) or not math.isfinite(x) for x in point)):
        raise ValueError('two finite coordinates required')
    return tuple(float(v) for v in point)


def _corridors(route):
    if not isinstance(route, Route) or len(route.legs) != 3:
        raise ValueError('three-leg Route required')
    return tuple(tuple(leg.bounds()) for leg in route.legs)


def _inside(rectangles, point):
    x, y = point
    return any(xmin <= x <= xmax and ymin <= y <= ymax
               for xmin, ymin, xmax, ymax in rectangles)


def boundary_edges(route):
    """Exact exposed axis-aligned edges of the union of three rectangles.

    Splitting at every rectangle coordinate and probing both open half-planes
    removes internal seams at G/D bends without relying on seed or direction.
    """
    return _boundary_edges(_corridors(route))


def _boundary_edges(rectangles):
    """Exposed edges shared by corridor-only and full-course consumers."""
    xs = sorted({value for xmin, _, xmax, _ in rectangles for value in (xmin, xmax)})
    ys = sorted({value for _, ymin, _, ymax in rectangles for value in (ymin, ymax)})
    edges = []
    probe = 1e-7
    for x in xs:
        for ya, yb in zip(ys, ys[1:]):
            mid = (ya + yb) / 2
            if _inside(rectangles, (x-probe, mid)) != _inside(rectangles, (x+probe, mid)):
                edges.append(((x, ya), (x, yb)))
    for y in ys:
        for xa, xb in zip(xs, xs[1:]):
            mid = (xa + xb) / 2
            if _inside(rectangles, (mid, y-probe)) != _inside(rectangles, (mid, y+probe)):
                edges.append(((xa, y), (xb, y)))
    if len(edges) < 4:
        raise ValueError('invalid corridor union boundary')
    return tuple(edges)


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _distance_point_segment(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    norm = dx*dx + dy*dy
    if norm == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/norm))
    return math.hypot(p[0] - (a[0]+t*dx), p[1] - (a[1]+t*dy))


def _distance_segments(a, b, c, d):
    u = (b[0]-a[0], b[1]-a[1])
    v = (d[0]-c[0], d[1]-c[1])
    w = (c[0]-a[0], c[1]-a[1])
    denominator = _cross(u, v)
    if abs(denominator) > 1e-12:
        s, t = _cross(w, v)/denominator, _cross(w, u)/denominator
        if -EPS <= s <= 1+EPS and -EPS <= t <= 1+EPS:
            return 0.0
    return min(_distance_point_segment(a,c,d), _distance_point_segment(b,c,d),
               _distance_point_segment(c,a,b), _distance_point_segment(d,a,b))


def swept_corridor_clearance(route, before, after):
    """Smallest 2D clearance to the *union boundary*, in metres.

    Return -1 outside the union. Segment-to-boundary distances are continuous
    and exhaustive (no point sampling), including concave corner and shortcuts.
    """
    rectangles = _corridors(route)
    return _swept_clearance(rectangles, before, after)


def _swept_clearance(rectangles, before, after):
    before, after = _point(before), _point(after)
    if not _inside(rectangles, before) or not _inside(rectangles, after):
        return -1.0
    return min(_distance_segments(before, after, a, b)
               for a, b in _boundary_edges(rectangles))


def swept_capsule_inside_corridors(route, before, after):
    """Conservative non-permissive 0.09m capsule test for one sampled move.

    The moving disc must remain strictly inside the three-corridor union.
    This can reject geometrically legal terminal-pad motion until that area
    is explicitly modeled; it never authorizes flight or reports mission GO.
    """
    return swept_corridor_clearance(route, before, after) > RADIUS + EPS
