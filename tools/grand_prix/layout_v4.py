"""Owner's gp-v4 experimental dimensions; never input to a student AST."""
import hashlib
import math
from .layout import Box, Gate, Layout, TOP_BOTTOM, GAP

VERSION = 'gp-v4'
SIDE = 2.5
WIDTH = 1.0


def generate_v4(seed: int) -> Layout:
    if type(seed) is not int or not 0 <= seed <= 65535:
        raise ValueError('seed must be an integer in [0, 65535]')
    digest = hashlib.sha256(f'{VERSION}:{seed}'.encode()).digest()
    sides = sorted(range(4), key=lambda i: (digest[i], i))[:2 + digest[4] % 3]
    starts = [(0, 0, 0), (SIDE, 0, math.pi/2), (SIDE, SIDE, math.pi), (0, SIDE, -math.pi/2)]
    gates = []
    boxes = []
    for side, (x, y, heading) in enumerate(starts):
        x = round(x + 1.25*math.cos(heading), 6)
        y = round(y + 1.25*math.sin(heading), 6)
        if side in sides:
            gates.append(Gate(x, y, heading))
        else:
            horizontal = abs(math.cos(heading)) > .5
            boxes.append(Box(x, y, .25, .08 if horizontal else WIDTH,
                             WIDTH if horizontal else .08, .5))
    count = 1 + digest[9] % 3
    final = [Gate(0, round(-1.1-i*1.15, 6), -math.pi/2) for i in range(count)]
    final.append(Gate(0, round(final[-1].y-1.55, 6), -math.pi/2, True))
    bottom = final[-1].y - .6
    # Faces are at +/- .50 from each centerline. The junction is an ordinary
    # left corner with a forward exit; no special gate or semantic landmark.
    boxes.extend([
        Box(-.52, (SIDE+.52+bottom)/2, .65, .04, SIDE+.52-bottom, 1.3),
        Box(SIDE+.52, SIDE/2, .65, .04, SIDE+1.08, 1.3),
        Box(SIDE/2, SIDE+.52, .65, SIDE+1.08, .04, 1.3),
        Box((SIDE+1.04)/2, -.52, .65, SIDE+.04, .04, 1.3),
        Box(.52, (bottom-.52)/2, .65, .04, -.52-bottom, 1.3),
        Box(0, bottom-.02, .65, WIDTH, .04, 1.3),
        Box(SIDE/2, SIDE/2, .65, SIDE-WIDTH, SIDE-WIDTH, 1.3),
    ])
    for gate in [*gates, *final]:
        horizontal = abs(math.cos(gate.heading)) > .5
        for sign in (-1, 1):
            boxes.append(Box(round(gate.x-math.sin(gate.heading)*sign*.30, 6),
                             round(gate.y+math.cos(gate.heading)*sign*.30, 6), .65,
                             .48 if horizontal else .04, .04 if horizontal else .48, 1.3))
        height = 1.3 if gate.closed else 1.3-TOP_BOTTOM
        boxes.append(Box(gate.x, gate.y, height/2 if gate.closed else TOP_BOTTOM+height/2,
                         .04 if horizontal else GAP, GAP if horizontal else .04, height))
    return Layout(seed, tuple(gates), tuple(final), tuple(boxes),
                  version=VERSION, side=SIDE, width=WIDTH, landing_offset=.75)
