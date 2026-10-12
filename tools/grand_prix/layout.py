"""Bounded simulation-only layout. No data here is an input to the student AST."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path

VERSION = 'gp-v1'
SIDE = 1.4
WIDTH = .8
GAP = .56
TOP_BOTTOM = .62
ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Gate:
    x: float
    y: float
    heading: float
    closed: bool = False

@dataclass(frozen=True)
class Box:
    x: float
    y: float
    z: float
    sx: float
    sy: float
    sz: float

@dataclass(frozen=True)
class Layout:
    seed: int
    gates: tuple[Gate, ...]
    final_gates: tuple[Gate, ...]
    boxes: tuple[Box, ...]
    @property
    def identifier(self):
        return f'{VERSION}-{self.seed}'


def generate(seed: int) -> Layout:
    if type(seed) is not int or not 0 <= seed <= 65535:
        raise ValueError('seed must be an integer in [0, 65535]')
    # Explicit versioned hash, independent of Python's random/hash versions.
    digest = hashlib.sha256(f'{VERSION}:{seed}'.encode()).digest()
    sides = sorted(range(4), key=lambda i: (digest[i], i))[:2 + digest[4] % 3]
    gates = []
    for side in sorted(sides):
        distance = .76 if side == 3 else .76 + (digest[side + 5] % 2) * .06
        starts = [(0, 0, 0), (SIDE, 0, math.pi/2), (SIDE, SIDE, math.pi), (0, SIDE, -math.pi/2)]
        x, y, heading = starts[side]
        gates.append(Gate(round(x + distance*math.cos(heading), 6), round(y + distance*math.sin(heading), 6), heading))
    final = ([Gate(0, -.46, -math.pi/2)] if digest[9] % 2 else []) + [Gate(0, -1.1, -math.pi/2, True)]
    # Outer boundary, inner island and exit corridor. All have real collision boxes.
    boxes = [Box(-.42, 0, .65, .04, 3.68, 1.3), Box(1.82, .7, .65, .04, 2.28, 1.3),
             Box(.7, 1.82, .65, 2.28, .04, 1.3), Box(1.11, -.42, .65, 1.42, .04, 1.3),
             Box(.42, -1.12, .65, .04, 1.4, 1.3), Box(0, -1.82, .65, .8, .04, 1.3),
             Box(.7, .7, .65, .6, .6, 1.3)]
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
    return Layout(seed,tuple(gates),tuple(final),tuple(boxes))


def ray_distance(layout: Layout, x: float, y: float, z: float, heading: float) -> float | None:
    """Ideal pencil ray; None means saturation, never an opening certificate."""
    direction = (math.cos(heading),math.sin(heading),0)
    result = math.inf
    for box in layout.boxes:
        minimum, maximum = 0., math.inf
        for origin, direction_axis, center, size in zip((x,y,z),direction,(box.x,box.y,box.z),(box.sx,box.sy,box.sz)):
            lo, hi = center-size/2, center+size/2
            if abs(direction_axis) < 1e-9:
                if origin < lo or origin > hi: maximum=-1;break
            else:
                a,b=(lo-origin)/direction_axis,(hi-origin)/direction_axis
                minimum=max(minimum,min(a,b));maximum=min(maximum,max(a,b))
        if maximum >= minimum: result=min(result,minimum)
    return result if math.isfinite(result) and result < 1.99 else None


def local(gate: Gate, point):
    dx,dy=point[0]-gate.x,point[1]-gate.y
    return dx*math.cos(gate.heading)+dy*math.sin(gate.heading),-dx*math.sin(gate.heading)+dy*math.cos(gate.heading)


def world_text(layout: Layout):
    source=(ROOT/'worlds/crazyflie_runtime_v2.wbt').read_text()
    robot_start=source.index('Crazyflie {')
    robot_end=source.index('# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN')
    robot=source[robot_start:robot_end].replace('controller "crazyflie_runtime_v2"','controller "grand_prix_flight"').replace('window "blockly_v2"','window "grand_prix"')
    externs='\n'.join(line for line in source.splitlines() if line.startswith('EXTERNPROTO '))
    lines=['#VRML_SIM R2025a utf8',externs,
        f'WorldInfo {{ basicTimeStep 32 randomSeed 1 optimalThreadCount 1 title "Grand Prix — {layout.identifier}" }}',
        'Viewpoint { orientation -0.45 0.47 0.76 1.05 position -3.2 -3.2 3.4 follow "Crazyflie WebeeBlocks" }',
        'TexturedBackground { }','TexturedBackgroundLight { }','Floor { size 6 6 }']
    for i,box in enumerate(layout.boxes):
        position=f'{box.x:.6f} {box.y:.6f} {box.z:.6f}'
        size=f'{box.sx:.6f} {box.sy:.6f} {box.sz:.6f}'
        lines.append(f'DEF GP_BOX_{i} Solid {{ translation {position} name "Paroi {i}" children [ Shape {{ appearance PBRAppearance {{ baseColor 0.75 0.55 0.25 roughness 1 }} geometry Box {{ size {size} }} }} ] boundingObject Box {{ size {size} }} }}')
    for x,y,color in [(0,0,'0.12 0.42 0.9'),(0,-.85,'0.10 0.72 0.28')]:
        lines.append(f'Pose {{ translation {x} {y} .002 children [ Shape {{ appearance PBRAppearance {{ baseColor {color} roughness 1 }} geometry Box {{ size .28 .28 .004 }} }} ] }}')
    lines.extend([robot, f'DEF GP_EVALUATOR Robot {{ name "Grand Prix evaluator" controller "grand_prix_evaluator" controllerArgs [ "{layout.seed}" ] supervisor TRUE }}'])
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();layout=generate(args.seed)
    args.output.write_text(world_text(layout))
    print(layout.identifier)

if __name__=='__main__':main()
