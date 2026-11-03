"""Host-only, *provisional* terminal geometry for a variable Grand Prix course.

The full-width closed H and three landing targets use the last leg's directed
frame; they are not native collision/sensor evidence or a mission evaluator.
Never pass these host-side coordinates to the pupil AST or Blockly runtime.
"""
from dataclasses import dataclass
from tools.grand_prix.route_v2 import Route

ARRIVAL_WIDTH = 1.80
ARRIVAL_LENGTH = .95
LANDING_TILE = .28
CLOSURE_SPAN = ARRIVAL_WIDTH + .04
HEIGHT = 1.30


@dataclass(frozen=True)
class TerminalBox:
    name: str
    x: float
    y: float
    z: float
    sx: float
    sy: float
    sz: float
    translucent: bool = False

    def vrml(self):
        """Visible physical Solid, with matching collider; no hidden wall."""
        dimensions = f'{self.sx:.6f} {self.sy:.6f} {self.sz:.6f}'
        color = ('.35 .65 .58' if self.translucent else '.75 .55 .25')
        transparency = ' transparency .65' if self.translucent else ''
        return (f'DEF {self.name} Solid {{ translation {self.x:.6f} '
                f'{self.y:.6f} {self.z:.6f} locked TRUE children [ Shape {{ '
                f'appearance PBRAppearance {{ baseColor {color} roughness .55'
                f'{transparency} }} geometry Box {{ size {dimensions} }} }} ] '
                f'boundingObject Box {{ size {dimensions} }} }}')


def _last_leg(route):
    if not isinstance(route, Route) or len(route.legs) != 3:
        raise TypeError('three-leg variable Route required')
    return route.legs[2]


def landing_footprint(route):
    """Widened 1.80m x 0.95m terminal area, bounded by the final H plane.

    This is a proposed *planar* area, NOT a modification of the existing
    historic-U oracle or proof that a drone can reach it in simulation.
    """
    leg = _last_leg(route)
    return tuple(leg.at(along, lateral) for along, lateral in (
        (leg.length - ARRIVAL_LENGTH, -ARRIVAL_WIDTH/2),
        (leg.length, -ARRIVAL_WIDTH/2),
        (leg.length, ARRIVAL_WIDTH/2),
        (leg.length - ARRIVAL_LENGTH, ARRIVAL_WIDTH/2),
    ))


def landing_targets(route):
    """Centre, 50cm left, 50cm right in *arrival* orientation."""
    _last_leg(route)
    return tuple(route.landing_target(count) for count in (1, 2, 3))


def terminal_boxes(route):
    """Four aligned colliders: two uprights, a beam, a CLOSED H panel.

    Retain the existing gp-u-v1 dimensions; the translucent panel fills the
    entire 1.80m-wide terminal edge from the floor to 1.30m. Physical sensor
    detection, contact and impossibility of bypass still require native tests.
    """
    leg = _last_leg(route)
    horizontal = leg.direction % 2 == 0

    def make(name, lateral, z, longitudinal_size, transverse_size, height,
             translucent=False):
        x, y = leg.at(leg.length, lateral)
        sx, sy = ((longitudinal_size, transverse_size) if horizontal else
                  (transverse_size, longitudinal_size))
        return TerminalBox(name, x, y, z, sx, sy, height, translucent)

    return (
        make('GP_V2_FINAL_LEFT', -.87, HEIGHT/2, .08, .10, HEIGHT),
        make('GP_V2_FINAL_RIGHT', .87, HEIGHT/2, .08, .10, HEIGHT),
        make('GP_V2_FINAL_BEAM', 0., .75, .08, CLOSURE_SPAN, .12),
        make('GP_V2_FINAL_PANEL', 0., HEIGHT/2, .04, CLOSURE_SPAN,
             HEIGHT, True),
    )
