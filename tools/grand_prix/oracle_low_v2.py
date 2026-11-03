"""Pure directed low-flight zones for candidate variable Grand Prix routes.

Host/oracle side only: no pupil/Blockly/AST data and no assertion that a course
is natively flight-qualified. Other safety checks (swept track, contact,
sequence, clock and LAND) remain mandatory. The historical U oracle is intact.
"""
import math

from .oracle_u import (
    LOW_AFTER, LOW_BEFORE, LOW_THRESHOLD, RADIUS, clipped_interval,
)


def _local_exact(leg, point):
    """Directed coordinates without six-decimal display rounding.

    Geometric acceptance must never grow by a rounding tolerance: the pure
    route Leg.local() rounds to 1e-6, which is suitable for layout identities,
    but not for a strict boundary oracle.
    """
    fx, fy = leg.forward
    dx, dy = point[0] - leg.start[0], point[1] - leg.start[1]
    return dx * fx + dy * fy, -dx * fy + dy * fx


def low_segment_allowed_v2(a, b, route, gates, *, final=False, takeoff_until=None):
    """Verify that all strictly-low observed sweep is covered by safe zones.

    gates is a host-only sequence of objects with leg_index, along and
    direction (the last field is checked, not trusted as an independent frame).
    final is caller-authorized only after lawful route progression.
    takeoff_until is the caller's bounded fraction of this step within the
    already authorized 15 s initial takeoff exception; negative means expired.

    Retains gp-u-v1's 0.09 m craft radius, 0.55 m gate bands, final-region
    proportions and 0.14 m start radius, only rotating/translating by the
    current leg frame. The track/collider/clock oracles are separate.
    """
    if (len(a) != 3 or len(b) != 3 or type(final) is not bool or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in (*a, *b)) or
            (takeoff_until is not None and
             (type(takeoff_until) not in (int, float) or
              not math.isfinite(takeoff_until)))):
        return False
    if min(a[2], b[2]) >= LOW_THRESHOLD:
        return True
    low = clipped_interval((a[2],), (b[2],),
                           ((-math.inf, LOW_THRESHOLD),))
    intervals = []
    for gate in gates:
        index, along = gate.leg_index, gate.along
        if (type(index) is not int or index not in range(3) or
                type(along) not in (int, float) or not math.isfinite(along)):
            return False
        leg = route.legs[index]
        if (gate.direction != leg.direction or not 0 <= along <= leg.length):
            return False
        before = _local_exact(leg, a)
        after = _local_exact(leg, b)
        clipped = clipped_interval((before[0] - along, before[1]),
                                   (after[0] - along, after[1]),
                                   ((-LOW_BEFORE + RADIUS, LOW_AFTER - RADIUS),
                                    (-0.30 + RADIUS, 0.30 - RADIUS)))
        if clipped is not None:
            intervals.append(clipped)
    if final:
        leg = route.legs[2]
        clipped = clipped_interval(_local_exact(leg, a), _local_exact(leg, b),
                                   ((leg.length - .86, leg.length - .11),
                                    (-.81, .81)))
        if clipped is not None:
            intervals.append(clipped)
    if takeoff_until is not None:
        sx, sy = route.legs[0].start
        dx, dy = b[0] - a[0], b[1] - a[1]
        ax, ay = a[0] - sx, a[1] - sy
        aa = dx*dx + dy*dy
        bb = 2 * (ax*dx + ay*dy)
        cc = ax*ax + ay*ay - .14**2
        if not aa:
            if cc <= 0:
                intervals.append((0., min(1., takeoff_until)))
        else:
            disc = bb*bb - 4*aa*cc
            if disc >= 0:
                first = (-bb - math.sqrt(disc))/(2*aa)
                last = (-bb + math.sqrt(disc))/(2*aa)
                lo, hi = max(0., first), min(1., last, takeoff_until)
                if lo <= hi:
                    intervals.append((lo, hi))
    covered = low[0]
    for lo, hi in sorted(intervals):
        if hi < covered:
            continue
        if lo > covered:
            return False
        covered = max(covered, hi)
        if covered >= low[1]:
            return True
    return False
