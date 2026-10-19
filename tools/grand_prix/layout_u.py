"""gp-u-v1 geometry candidate for #587, never an input to the pupil AST.

All lengths are public experimental hypotheses, not flight qualifications.
The same side length and outer boundary apply to every seed.
"""
from dataclasses import dataclass
import argparse
import hashlib
import math
from pathlib import Path

VERSION = 'gp-u-v1'
RADIUS = .09
WIDTH = 1.
GAP = .56
TOP_BOTTOM = .62
WALL_HEIGHT = 1.3
ARRIVAL_WIDTH = 1.8
ARRIVAL_LENGTH = .95
LANDING_OFFSET = .70
LOW_BEFORE = .55
LOW_AFTER = .55
LOW_THRESHOLD = .60
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    z: float
    sx: float
    sy: float
    sz: float


@dataclass(frozen=True)
class Gate:
    x: float
    y: float
    heading: float
    side: int
    distance: float
    closed: bool = False


@dataclass(frozen=True)
class Layout:
    seed: int
    side: float
    gates: tuple[Gate, ...]
    final_gates: tuple[Gate, ...]
    walls: tuple[Box, ...]
    gate_boxes: tuple[Box, ...]
    polygon: tuple[tuple[float, float], ...]
    version: str = VERSION
    width: float = WIDTH
    landing_offset: float = LANDING_OFFSET

    @property
    def identifier(self):
        return f'{VERSION}-L{round(self.side * 1000)}-s{self.seed}'

    @property
    def boxes(self):
        return self.walls + self.gate_boxes

    def landing_target(self, crossings):
        if type(crossings) is not int or not 1 <= crossings <= 3:
            raise ValueError('invalid crossing count')
        # Arrival heading pi: left is south, right is north.
        offset = {1: 0., 2: -.5, 3: .5}[crossings]
        return LANDING_OFFSET, self.side + offset


def local(gate, point):
    dx, dy = point[0] - gate.x, point[1] - gate.y
    return (dx * math.cos(gate.heading) + dy * math.sin(gate.heading),
            -dx * math.sin(gate.heading) + dy * math.cos(gate.heading))


def generate(seed, side=2.):
    if type(seed) is not int or not 0 <= seed <= 65535:
        raise ValueError('seed must be an integer in [0, 65535]')
    if (isinstance(side, bool) or not isinstance(side, (float, int)) or
            not math.isfinite(side) or not 2 <= side <= 6 or
            abs(side * 1000 - round(side * 1000)) > 1e-8):
        raise ValueError('experimental side must be 2–6 m, in millimetres')
    side = round(side, 3)
    digest = hashlib.sha256(f'{VERSION}:{seed}'.encode()).digest()
    selected = sorted(sorted(range(3), key=lambda i: (digest[i], i))[:1 + digest[3] % 3])
    starts = [(0., 0., 0.), (side, 0., math.pi / 2), (side, side, math.pi)]
    gates = []
    for i in selected:
        # The third H precedes the terminal area. It never migrates into it.
        distance = (.60 + .05 * (digest[4+i] % 3) if i == 2 else
                    .85 + .10 * (digest[4+i] % 4))
        x, y, heading = starts[i]
        gates.append(Gate(round(x + distance * math.cos(heading), 6),
                          round(y + distance * math.sin(heading), 6), heading, i, distance))
    closed = Gate(0., side, math.pi, 2, side, True)
    # Interior free-floor polygon. No fourth corridor and no detached finale.
    # Terminal widening is identical for all seeds; the closing edge is the H.
    polygon = ((-.5, -.5), (side+.5, -.5), (side+.5, side+.5),
               (.95, side+.5), (.95, side+.9), (0., side+.9),
               (0., side-.9), (.95, side-.9), (.95, side-.5),
               (side-.5, side-.5), (side-.5, .5), (-.5, .5))
    walls = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if a[0] == b[0] == 0.:  # Full-width terminal barrier below.
            continue
        if a[1] == b[1]:
            walls.append(Box((a[0]+b[0])/2, a[1], .65, abs(b[0]-a[0])+.04, .04, 1.3))
        else:
            walls.append(Box(a[0], (a[1]+b[1])/2, .65, .04, abs(b[1]-a[1])+.04, 1.3))
    boxes = []
    for g in gates:
        horizontal = g.side != 1
        for sign in (-1, 1):
            boxes.append(Box(round(g.x-math.sin(g.heading)*sign*.30, 6),
                             round(g.y+math.cos(g.heading)*sign*.30, 6), .65,
                             .48 if horizontal else .04, .04 if horizontal else .48, 1.3))
        boxes.append(Box(g.x, g.y, (.62+1.3)/2, .04 if horizontal else GAP,
                         GAP if horizontal else .04, 1.3-.62))
    # Full arrival width, with no side or high bypass within the permitted z.
    boxes.append(Box(0., side, .65, .04, ARRIVAL_WIDTH+.04, WALL_HEIGHT))
    return Layout(seed, side, tuple(gates), (closed,), tuple(walls), tuple(boxes), polygon)


def world_text(layout, *, controller='<none>', window='<none>',
               evaluator=False, timestep=8):
    # 210000 ms is not divisible by 32 ms; 8 ms makes the required instant
    # realizable without rounding the deadline or changing controller limits.
    if timestep not in (8, 32):
        raise ValueError('unsupported experimental basic timestep')
    source = (ROOT / 'worlds/crazyflie_runtime_v2.wbt').read_text()
    robot = source[source.index('Crazyflie {'):source.index('# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN')]
    robot = robot.replace('controller "crazyflie_runtime_v2"', f'controller "{controller}"')
    robot = robot.replace('window "blockly_v2"', f'window "{window}"')
    externs = '\n'.join(line for line in source.splitlines() if line.startswith('EXTERNPROTO '))
    size = layout.side + 2.5
    lines = ['#VRML_SIM R2025a utf8', externs,
             f'DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo {{ basicTimeStep {timestep} randomSeed 1 optimalThreadCount 1 title "Grand Prix — {layout.identifier}" }}',
             'Viewpoint { orientation -0.45 0.47 0.76 1.05 position -5 -5 7 }',
             'TexturedBackground { }', 'TexturedBackgroundLight { }',
             f'Floor {{ translation {layout.side/2} {layout.side/2} 0 size {size} {size} }}']
    for i, b in enumerate(layout.boxes):
        dims = f'{b.sx:.6f} {b.sy:.6f} {b.sz:.6f}'
        lines.append(f'DEF GP_U_BOX_{i} Solid {{ translation {b.x:.6f} {b.y:.6f} {b.z:.6f} name "Paroi {i}" children [ Shape {{ appearance PBRAppearance {{ baseColor .75 .55 .25 roughness 1 }} geometry Box {{ size {dims} }} }} ] boundingObject Box {{ size {dims} }} }}')
    def mark(name, x, y, sx, sy, color):
        lines.append(f'DEF {name} Pose {{ translation {x:.6f} {y:.6f} .002 children [ Shape {{ appearance PBRAppearance {{ baseColor {color} roughness 1 }} geometry Box {{ size {sx:.6f} {sy:.6f} .004 }} }} ] }}')
    # White U reference is a visual aid, not an observed flight or oracle path.
    # It remains beneath the start/landing tiles and has no collision body.
    for idx, (x, y, sx, sy) in enumerate((
            (layout.side/2, 0., layout.side, .025),
            (layout.side, layout.side/2, .025, layout.side),
            ((layout.side+.70)/2, layout.side, layout.side-.70, .025))):
        lines.append(f'DEF GP_U_GUIDE_{idx} Pose {{ translation {x:.6f} {y:.6f} .0010 children [ Shape {{ appearance PBRAppearance {{ baseColor .96 .96 .96 roughness 1 }} geometry Box {{ size {sx:.6f} {sy:.6f} .0010 }} }} ] }}')
    mark('GP_U_START', 0, 0, .28, .28, '.12 .42 .9')
    for count in (1, 2, 3):
        x, y = layout.landing_target(count)
        mark(f'GP_U_TARGET_{count}', x, y, .28, .28, '.10 .72 .28')
    for i, g in enumerate(layout.gates):
        for kind, distance in (('BEFORE', -LOW_BEFORE), ('AFTER', LOW_AFTER)):
            x, y = g.x + distance*math.cos(g.heading), g.y + distance*math.sin(g.heading)
            # Eight yellow half-pitch dashes across each observed low-flight
            # boundary; positions/distances and legality remain unchanged.
            pitch = WIDTH / 8
            for dash in range(8):
                lateral = -WIDTH/2 + (dash + .5) * pitch
                mx = x - math.sin(g.heading) * lateral
                my = y + math.cos(g.heading) * lateral
                mark(f'GP_U_BAND_{i}_{kind}_{dash}', mx, my,
                     .012 if g.side != 1 else pitch/2,
                     pitch/2 if g.side != 1 else .012, '.98 .85 .1')
    args = f'controllerArgs [ "{layout.seed}" "{layout.side:.3f}" ]'
    robot = robot.replace(f'controller "{controller}"', f'controller "{controller}" {args}')
    lines.append(robot)
    if evaluator:
        lines.append(f'DEF GP_U_EVALUATOR Robot {{ name "Évaluateur Grand Prix" supervisor TRUE controller "grand_prix_u_evaluator" {args} }}')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--side', type=float, default=2.)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(world_text(generate(args.seed, args.side)))
