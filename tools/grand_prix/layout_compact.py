"""Explicit compact calibration candidate; preserves H and alternate low obstacles.

The legacy gp-v2 generator and worlds remain unchanged. Parameters are evaluator
geometry, never AST inputs. This is not a native timing or competition proof.
"""
import hashlib
import math
from .layout import Box, Gate, Layout, TOP_BOTTOM, GAP

VERSION = 'gp-v3'
SIDE = 1.0

def generate_compact(seed: int) -> Layout:
    if type(seed) is not int or not 0 <= seed <= 65535:
        raise ValueError('seed must be an integer in [0, 65535]')
    # Explicit versioned hash, independent of Python's random/hash versions.
    digest = hashlib.sha256(f'{VERSION}:{seed}'.encode()).digest()
    sides = sorted(range(4), key=lambda i: (digest[i], i))[:2 + digest[4] % 3]
    gates = []
    for side in sorted(sides):
        distance = .60
        starts = [(0, 0, 0), (SIDE, 0, math.pi/2), (SIDE, SIDE, math.pi), (0, SIDE, -math.pi/2)]
        x, y, heading = starts[side]
        gates.append(Gate(round(x + distance*math.cos(heading), 6), round(y + distance*math.sin(heading), 6), heading))
    final = [Gate(0, -.46, -math.pi/2), Gate(0, -1.1, -math.pi/2, True)] if digest[9] % 2 else [Gate(0, -.6, -math.pi/2, True)]
    # Outer boundary, inner island and exit corridor. All have real collision boxes.
    boxes = [Box(-.42, (SIDE-1.4)/2, .65, .04, SIDE+2.28, 1.3), Box(SIDE+.42, SIDE/2, .65, .04, SIDE+.88, 1.3),
             Box(SIDE/2, SIDE+.42, .65, SIDE+.88, .04, 1.3), Box((SIDE+.84)/2, -.42, .65, SIDE+.04, .04, 1.3),
             Box(.42, -1.12, .65, .04, 1.4, 1.3), Box(0, -1.82, .65, .8, .04, 1.3),
             Box(SIDE/2, SIDE/2, .65, SIDE-.8, SIDE-.8, 1.3)]
    # A side without a H contains a full-width low obstacle at the same slot.
    # Low flight and high flight therefore cannot both cross every layout:
    # low is required for H, high for the alternate observed geometry.
    for side in range(4):
        if side in sides: continue
        starts = [(0, 0, 0), (SIDE, 0, math.pi/2), (SIDE, SIDE, math.pi), (0, SIDE, -math.pi/2)]
        x,y,heading=starts[side]
        x+=.60*math.cos(heading);y+=.60*math.sin(heading)
        horizontal=abs(math.cos(heading))>.5
        boxes.append(Box(round(x,6),round(y,6),.25,.08 if horizontal else .8,.8 if horizontal else .08,.5))
    for gate in [*gates, *final]:
        # Plates extend 24 cm before/after the traverse. The sensor rays see
        # them before the front plane, unlike a thin H with no approach length.
        horizontal = abs(math.cos(gate.heading)) > .5
        for sign in (-1, 1):
            x = gate.x - math.sin(gate.heading) * sign * .30
            y = gate.y + math.cos(gate.heading) * sign * .30
            boxes.append(Box(round(x,6), round(y,6), .65, .48 if horizontal else .04, .04 if horizontal else .48, 1.3))
        height = 1.3 if gate.closed else 1.3-TOP_BOTTOM
        boxes.append(Box(gate.x,gate.y,height/2 if gate.closed else TOP_BOTTOM+height/2,
                         .04 if horizontal else GAP,GAP if horizontal else .04,height))
    return Layout(seed,tuple(gates),tuple(final),tuple(boxes),version=VERSION,side=SIDE)

