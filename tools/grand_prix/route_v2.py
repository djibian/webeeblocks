"""Pure geometry for candidate Grand Prix variable routes (#808).

No Webots objects, sensors, oracle verdicts or pupil/AST-facing metadata.
The historical gp-u-v1 generator is deliberately untouched until the
world-builder and independent oracle both consume this contract.
"""
from dataclasses import dataclass
import math

VERSION = 'gp-route-v2'
WIDTH = 0.60
ALLOWED_LENGTHS = (2.0, 2.5, 3.0)
# Cardinal index: east, north, west, south; G/D are left/right turns.
UNITS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def _add(a, b):
    return (round(a[0] + b[0], 6), round(a[1] + b[1], 6))


def _scale(a, t):
    return (round(a[0] * t, 6), round(a[1] * t, 6))


def _left(a):
    return (-a[1], a[0])


@dataclass(frozen=True)
class Leg:
    index: int
    start: tuple[float, float]
    end: tuple[float, float]
    direction: int
    length: float

    @property
    def forward(self):
        return UNITS[self.direction]

    def at(self, along, lateral=0.0):
        """World coordinate; lateral positive is the drone's left."""
        if type(along) not in (int, float) or not math.isfinite(along):
            raise ValueError('non-numeric along')
        if type(lateral) not in (int, float) or not math.isfinite(lateral):
            raise ValueError('non-numeric lateral')
        return _add(_add(self.start, _scale(self.forward, along)),
                    _scale(_left(self.forward), lateral))

    def local(self, point):
        """World point in the directed segment frame: (along, left)."""
        if (not isinstance(point, (tuple, list)) or len(point) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x) for x in point)):
            raise ValueError('world point must contain two finite numbers')
        v = (point[0] - self.start[0], point[1] - self.start[1])
        f = self.forward
        l = _left(f)
        return (round(v[0] * f[0] + v[1] * f[1], 6),
                round(v[0] * l[0] + v[1] * l[1], 6))

    def bounds(self):
        half = WIDTH / 2
        return (min(self.start[0], self.end[0]) - half,
                min(self.start[1], self.end[1]) - half,
                max(self.start[0], self.end[0]) + half,
                max(self.start[1], self.end[1]) + half)


@dataclass(frozen=True)
class Corner:
    index: int
    turn: str
    junction: tuple[float, float]
    outer: tuple[float, float]
    back_tip: tuple[float, float]
    onward_tip: tuple[float, float]

    @property
    def arms(self):
        """Two exact 0.60 m centreline edges for later physical Solid colliders."""
        return ((self.outer, self.back_tip), (self.outer, self.onward_tip))


@dataclass(frozen=True)
class Route:
    seed: int
    lengths: tuple[float, float, float]
    turns: tuple[str, str]
    legs: tuple[Leg, Leg, Leg]
    corners: tuple[Corner, Corner]

    @property
    def identifier(self):
        sizes = '-'.join(str(round(length * 1000)) for length in self.lengths)
        return f'{VERSION}-L{sizes}-T{"".join(self.turns)}-s{self.seed}'

    @property
    def terminal(self):
        return self.legs[-1].end

    def landing_target(self, crossings):
        """Terminal landing frame; 2=left, 3=right of final forward axis."""
        if type(crossings) is not int or crossings not in (1, 2, 3):
            raise ValueError('crossings must be 1, 2, or 3')
        return self.legs[-1].at(self.legs[-1].length - .70,
                                {1: 0.0, 2: .50, 3: -.50}[crossings])


def _outside_corner(i, turn, incoming, outgoing):
    # Outermost corner of the union of two half-width corridor rectangles.
    # G: outward is right of both directions; D: outward is left.
    sign = -1 if turn == 'G' else 1
    ni = _scale(_left(incoming.forward), sign * WIDTH / 2)
    no = _scale(_left(outgoing.forward), sign * WIDTH / 2)
    outer = _add(_add(incoming.end, ni), no)
    return Corner(i, turn, incoming.end, outer,
                  _add(outer, _scale(incoming.forward, -WIDTH)),
                  _add(outer, _scale(outgoing.forward, WIDTH)))


def build_route(seed, lengths, turns):
    """Construct a deterministic three-leg route, NOT a qualified Webots world.

    The seed is part of the identity for future deterministic H placement;
    this pure geometric function does not pretend to generate gates.
    """
    if type(seed) is not int or not 0 <= seed <= 65535:
        raise ValueError('seed must be an integer in [0, 65535]')
    if not isinstance(lengths, (tuple, list)) or len(lengths) != 3 or any(
            type(n) not in (int, float) or n not in ALLOWED_LENGTHS for n in lengths):
        raise ValueError('three independent lengths from 2, 2.5, 3 m required')
    if not isinstance(turns, (tuple, list)) or len(turns) != 2 or any(
            type(t) is not str or t not in ('G', 'D') for t in turns):
        raise ValueError('exactly two independent G/D turns required')
    lengths, turns = tuple(float(n) for n in lengths), tuple(turns)
    legs = []
    position = (0., 0.)
    direction = 0
    for i, length in enumerate(lengths):
        end = _add(position, _scale(UNITS[direction], length))
        legs.append(Leg(i, position, end, direction, length))
        position = end
        if i < 2:
            direction = (direction + (1 if turns[i] == 'G' else -1)) % 4
    corners = tuple(_outside_corner(i, turns[i], legs[i], legs[i + 1])
                    for i in range(2))
    # Never permit a course with the first and last corridor overlapping.
    a, b = legs[0].bounds(), legs[2].bounds()
    if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
        raise ValueError('nonadjacent corridors overlap')
    return Route(seed, lengths, turns, tuple(legs), corners)
