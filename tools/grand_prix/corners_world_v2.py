"""Physical L-corner *world fragment* for variable Grand Prix routes (#808).

A Solid with a boundingObject is deliberately generated for each arm.
This is not a full Webots world, a sensor qualification or a pupil-facing API.
"""
from dataclasses import dataclass
import math

from tools.grand_prix.route_v2 import Route, WIDTH

HEIGHT = 1.30  # from floor to above ordinary horizontal range sensor altitude
THICKNESS = 0.04


@dataclass(frozen=True)
class CornerBar:
    corner_index: int
    arm_index: int
    centre: tuple[float, float, float]
    size: tuple[float, float, float]

    @property
    def def_name(self):
        return f"GP_V2_L_CORNER_{self.corner_index}_ARM_{self.arm_index}"


def make_corner_bars(route):
    """Two orthogonal collidable 0.60 m bars at each *outer* turn corner."""
    if not isinstance(route, Route) or len(route.corners) != 2:
        raise ValueError("expected a validated three-leg variable route")
    bars = []
    for corner in route.corners:
        for arm_index, (start, end) in enumerate(corner.arms):
            dx, dy = end[0] - start[0], end[1] - start[1]
            horizontal = math.isclose(abs(dx), WIDTH, abs_tol=1e-6) and math.isclose(dy, 0, abs_tol=1e-6)
            vertical = math.isclose(abs(dy), WIDTH, abs_tol=1e-6) and math.isclose(dx, 0, abs_tol=1e-6)
            if horizontal == vertical:
                raise ValueError("corner arm must be cardinal and exactly 0.60 m")
            centre = (round((start[0] + end[0]) / 2, 6),
                      round((start[1] + end[1]) / 2, 6), HEIGHT / 2)
            size = (WIDTH, THICKNESS, HEIGHT) if horizontal else (THICKNESS, WIDTH, HEIGHT)
            bars.append(CornerBar(corner.index, arm_index, centre, size))
    if len(bars) != 4:
        raise ValueError("two independent corners with two bars each required")
    return tuple(bars)


def corner_world_fragment(route):
    """VRML for four visible, physical Solid colliders. No secret metadata."""
    lines = []
    for bar in make_corner_bars(route):
        x, y, z = bar.centre
        sx, sy, sz = bar.size
        size = f"{sx:.6f} {sy:.6f} {sz:.6f}"
        lines.append(
            f'DEF {bar.def_name} Solid {{ translation {x:.6f} {y:.6f} {z:.6f} '
            f'name "Cornière {bar.corner_index + 1}, branche {bar.arm_index + 1}" '
            'locked TRUE '
            'children [ Shape { appearance PBRAppearance { '
            'baseColor 0.94 0.32 0.14 roughness 1 } '
            f'geometry Box {{ size {size} }} }} ] '
            f'boundingObject Box {{ size {size} }} }}'
        )
    return "\n".join(lines) + "\n"
