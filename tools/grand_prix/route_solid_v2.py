"""R2025a static scene for #808 variable L-corners; NOT a flight mission."""
from dataclasses import dataclass
import math
from pathlib import Path
from tools.grand_prix.route_v2 import Route, WIDTH, build_route

ROOT = Path(__file__).resolve().parents[2]
ARM, THICKNESS, HEIGHT = .60, .04, 1.30


@dataclass(frozen=True)
class Box:
    name: str
    x: float
    y: float
    sx: float
    sy: float

    def vrml(self):
        size = f'{self.sx:.6f} {self.sy:.6f} {HEIGHT:.6f}'
        return (f'DEF {self.name} Solid {{ translation {self.x:.6f} {self.y:.6f} {HEIGHT/2:.6f} '
                f'name "{self.name}" locked TRUE children [ Shape {{ '
                'appearance PBRAppearance { baseColor .76 .43 .19 roughness 1 } '
                f'geometry Box {{ size {size} }} }} ] boundingObject Box {{ size {size} }} }}')


def corner_boxes(route):
    if not isinstance(route, Route):
        raise TypeError('variable Route required')
    boxes = []
    for corner in route.corners:
        for index, (start, end) in enumerate(corner.arms):
            dx, dy = end[0] - start[0], end[1] - start[1]
            if (not math.isclose(abs(dx)+abs(dy), ARM, abs_tol=1e-8) or
                    abs(dx) > 1e-8 and abs(dy) > 1e-8):
                raise ValueError('L branches must be cardinal and exactly 0.60m')
            x = round((start[0]+end[0])/2, 6)
            y = round((start[1]+end[1])/2, 6)
            sx, sy = ((ARM, THICKNESS) if abs(dx)>1e-8 else (THICKNESS, ARM))
            boxes.append(Box(f'GP_V2_L_{corner.index}_{index}', x, y, sx, sy))
    if len(boxes) != 4:
        raise ValueError('two complete L corners required')
    return tuple(boxes)


def visual(name, x, y, sx, sy, color):
    return (f'DEF {name} Pose {{ translation {x:.6f} {y:.6f} .002 '
            'children [ Shape { '
            f'appearance PBRAppearance {{ baseColor {color} roughness 1 }} '
            f'geometry Box {{ size {sx:.6f} {sy:.6f} .004 }} }} ] }}')


@dataclass(frozen=True)
class RedDash:
    """Visible part of a corridor boundary; no collision geometry."""
    leg_index: int
    side: int
    step: int
    part: int
    start: float
    end: float
    x: float
    y: float
    sx: float
    sy: float


def red_dashes(route):
    """Clip each red boundary to the *outer boundary of the corridor union*.

    A side of one rectangular leg inside another rectangular leg is not a
    usable-course boundary. Subtract those *open interiors*, not arbitrary
    turns or a decorative hard-coded U mask. Valid for all cardinal G/D bends.
    """
    if not isinstance(route, Route):
        raise TypeError('variable Route required')
    result = []
    for leg in route.legs:
        horizontal = leg.direction % 2 == 0
        for side in (-1, 1):
            fixed = leg.at(0, side*WIDTH/2)[1 if horizontal else 0]
            for step in range(math.ceil(leg.length/.30)):
                start = step*.30
                end = min(start+.18, leg.length)
                if end-start <= .015:
                    continue
                visible = [(start, end)]
                for other in route.legs:
                    if other.index == leg.index:
                        continue
                    xmin, ymin, xmax, ymax = other.bounds()
                    if horizontal:
                        if not ymin+1e-9 < fixed < ymax-1e-9:
                            continue
                        low = leg.local((xmin, fixed))[0]
                        high = leg.local((xmax, fixed))[0]
                    else:
                        if not xmin+1e-9 < fixed < xmax-1e-9:
                            continue
                        low = leg.local((fixed, ymin))[0]
                        high = leg.local((fixed, ymax))[0]
                    low, high = sorted((low, high))
                    remaining = []
                    for left, right in visible:
                        if high <= left or low >= right:
                            remaining.append((left, right))
                        else:
                            if low > left:
                                remaining.append((left, min(low, right)))
                            if high < right:
                                remaining.append((max(high, left), right))
                    visible = remaining
                for part, (left, right) in enumerate(visible):
                    if right-left <= .015:
                        continue
                    x, y = leg.at((left+right)/2, side*WIDTH/2)
                    sx, sy = ((right-left, .012) if horizontal
                              else (.012, right-left))
                    result.append(RedDash(leg.index, side, step, part,
                                          left, right, x, y, sx, sy))
    return tuple(result)


def visual_guides(route):
    result = []
    for leg in route.legs:
        x, y = leg.at(leg.length/2)
        sx, sy = (leg.length, .025) if leg.direction%2==0 else (.025, leg.length)
        result.append(visual(f'GP_V2_WHITE_{leg.index}', x, y, sx, sy, '.96 .96 .96'))
    for dash in red_dashes(route):
        side = 'L' if dash.side == 1 else 'R'
        result.append(visual(f'GP_V2_RED_{dash.leg_index}_{side}_{dash.step}_{dash.part}',
                             dash.x, dash.y, dash.sx, dash.sy, '.95 .06 .06'))
    return tuple(result)


def static_world(route):
    """Observable static geometry; deliberately no flight controller or evaluator."""
    if not isinstance(route, Route):
        raise TypeError('variable Route required')
    template = (ROOT/'worlds/crazyflie_runtime_v2.wbt').read_text(encoding='utf-8')
    robot = template[template.index('Crazyflie {'):template.index('# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN')]
    if robot.count('controller "crazyflie_runtime_v2"') != 1 or robot.count('window "blockly_v2"') != 1:
        raise RuntimeError('Robot template changed; static composition refused')
    robot = robot.replace('controller "crazyflie_runtime_v2"', 'controller "<none>"')
    robot = robot.replace('window "blockly_v2"', 'window "<none>"')
    externs = [line.replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', 'webots://')
               for line in template.splitlines() if line.startswith('EXTERNPROTO ')]
    if len(externs) != 4:
        raise RuntimeError('unexpected R2025a PROTO inventory')
    xmin = min(leg.bounds()[0] for leg in route.legs)-.8
    ymin = min(leg.bounds()[1] for leg in route.legs)-.8
    xmax = max(leg.bounds()[2] for leg in route.legs)+.8
    ymax = max(leg.bounds()[3] for leg in route.legs)+.8
    cx, cy = (xmin+xmax)/2, (ymin+ymax)/2
    output = ['#VRML_SIM R2025a utf8', *externs,
              f'WorldInfo {{ basicTimeStep 8 randomSeed 1 title "L-corner STATIC {route.identifier}" }}',
              f'Viewpoint {{ orientation -0.45 0.47 0.76 1.05 position {cx-5:.3f} {cy-5:.3f} 7 }}',
              'TexturedBackground { }', 'TexturedBackgroundLight { }',
              f'Floor {{ translation {cx:.6f} {cy:.6f} 0 size {xmax-xmin:.6f} {ymax-ymin:.6f} }}']
    output.extend(visual_guides(route))
    output.extend(box.vrml() for box in corner_boxes(route))
    output.append(robot)
    text = '\n'.join(output)+'\n'
    if 'controller "grand_prix_u_flight"' in text or 'controller "grand_prix_u_evaluator"' in text:
        raise RuntimeError('static scene must not simulate a mission')
    return text


def example():
    return static_world(build_route(0, (2.,2.5,3.), ('G','D')))
