"""Bounded simulation-only layout. No data here is an input to the student AST."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path

VERSION = 'gp-v2'
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
    version: str = VERSION
    side: float = SIDE
    width: float = WIDTH
    landing_offset: float = .25
    @property
    def identifier(self):
        return f'{self.version}-{self.seed}'


def generate(seed: int, version: str = VERSION) -> Layout:
    if version == 'gp-v4':
        from .layout_v4 import generate_v4
        return generate_v4(seed)
    if version == 'gp-v3':
        from .layout_compact import generate_compact
        return generate_compact(seed)
    if version != VERSION:
        raise ValueError('unknown Grand Prix geometry version')
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
    final = [Gate(0, -.46, -math.pi/2), Gate(0, -1.1, -math.pi/2, True)] if digest[9] % 2 else [Gate(0, -.8, -math.pi/2, True)]
    # Outer boundary, inner island and exit corridor. All have real collision boxes.
    boxes = [Box(-.42, 0, .65, .04, 3.68, 1.3), Box(1.82, .7, .65, .04, 2.28, 1.3),
             Box(.7, 1.82, .65, 2.28, .04, 1.3), Box(1.11, -.42, .65, 1.42, .04, 1.3),
             Box(.42, -1.12, .65, .04, 1.4, 1.3), Box(0, -1.82, .65, .8, .04, 1.3),
             Box(.7, .7, .65, .6, .6, 1.3)]
    # A side without a H contains a full-width low obstacle at the same slot.
    # Low flight and high flight therefore cannot both cross every layout:
    # low is required for H, high for the alternate observed geometry.
    for side in range(4):
        if side in sides: continue
        starts = [(0, 0, 0), (SIDE, 0, math.pi/2), (SIDE, SIDE, math.pi), (0, SIDE, -math.pi/2)]
        x,y,heading=starts[side]
        x+=.76*math.cos(heading);y+=.76*math.sin(heading)
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
    for x,y,color in [(0,0,'0.12 0.42 0.9'),(0,layout.final_gates[-1].y+layout.landing_offset,'0.10 0.72 0.28')]:
        lines.append(f'Pose {{ translation {x} {y} .002 children [ Shape {{ appearance PBRAppearance {{ baseColor {color} roughness 1 }} geometry Box {{ size .28 .28 .004 }} }} ] }}')
    version_arg = f' "{layout.version}"' if layout.version != VERSION else ''
    lines.extend([robot, f'DEF GP_EVALUATOR Robot {{ name "Grand Prix evaluator" controller "grand_prix_evaluator" controllerArgs [ "{layout.seed}"{version_arg} ] supervisor TRUE }}'])
    if layout.version == 'gp-v4':
        lines = [line.replace('Floor { size 6 6 }', 'Floor { translation 1 -1 0 size 8 12 }').replace('position -3.2 -3.2 3.4', 'position -7 -10 9').replace('\"gp-v4\" ]', '\"gp-v4\" \"180\" ]') for line in lines]
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--version',choices=('gp-v2','gp-v3','gp-v4'),default=VERSION)
    args=parser.parse_args();layout=generate(args.seed,args.version)
    args.output.write_text(world_text(layout))
    print(layout.identifier)

if __name__=='__main__':main()
