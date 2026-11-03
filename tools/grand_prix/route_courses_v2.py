"""Deterministic *provisional* H placements for variable Grand Prix routes.

Host-side geometry only: not a Webots scene, pupil AST, safety oracle, native
clearance proof, collision model or acceptance of a route under 210 s.
Reuse the gp-route-v2 segment frames so subsequent scene and oracle work can
consume identical directed gate coordinates.
"""
from dataclasses import dataclass
import hashlib
import re
from tools.grand_prix.route_v2 import Route, build_route

LOW_BEFORE = 0.55
LOW_AFTER = 0.55


@dataclass(frozen=True)
class GatePlacement:
    leg_index: int
    along: float
    position: tuple[float, float]
    direction: int


@dataclass(frozen=True)
class CoursePlan:
    route: Route
    gates: tuple[GatePlacement, ...]
    count: int

    @property
    def identifier(self):
        return f"{self.route.identifier}-H{self.count}"


def course_from_identifier(identifier):
    """Reconstruct one canonical host configuration, never pupil AST data.

    The launcher, world controllerArgs and evaluator can exchange this single
    versioned string instead of inventing separate seed/length/turn schemas.
    It identifies geometry, not a qualification or a current attempt. The
    activity/profile/world identity used by .wbb remains independent of it.
    """
    if type(identifier) is not str or len(identifier) > 80:
        raise ValueError('canonical gp-route-v2 course identifier required')
    match = re.fullmatch(
        r'gp-route-v2-L(2000|2500|3000)-(2000|2500|3000)-(2000|2500|3000)'
        r'-T([GD])([GD])-s(0|[1-9][0-9]{0,4})-H([123])', identifier)
    if match is None:
        raise ValueError('canonical gp-route-v2 course identifier required')
    first, second, third, turn0, turn1, seed, count = match.groups()
    course = plan_course(int(seed), tuple(int(v)/1000 for v in (
        first, second, third)), (turn0, turn1), int(count))
    if course.identifier != identifier:
        raise ValueError('course identifier is not canonical')
    return course


def plan_course(seed, lengths, turns, gate_count):
    """Provide reproducible directed H centres, not physically qualified gates.

    Each selected leg receives exactly one H. Provisional longitudinal ranges
    preserve the historical low-band widths, but native L-corner, H, landing,
    reset and swept-clearance proof must be supplied independently.
    """
    if type(gate_count) is not int or gate_count not in (1, 2, 3):
        raise ValueError("gate_count must be 1, 2 or 3")
    route = build_route(seed, lengths, turns)
    digest = hashlib.sha256(
        f"{route.identifier}:H{gate_count}".encode("ascii")
    ).digest()
    chosen = sorted(
        sorted(range(3), key=lambda index: (digest[index], index))[:gate_count]
    )
    gates = []
    for index in chosen:
        leg = route.legs[index]
        if index < 2:
            # 2 m: centres at 0.90/1.00/1.10, leaving >=0.35 m between
            # 0.55 m low-band ends and both leg junctions.
            along = round(0.90 + 0.10 * (digest[3 + index] % 3)
                          + (leg.length - 2.0) * 0.5, 3)
        else:
            # The last H must precede the terminal landing at length-0.70.
            # This is a candidate interval, not certified L/H clearance.
            along = round(0.60 + 0.05 * (digest[5] % 3)
                          + (leg.length - 2.0) * 0.25, 3)
        if not (LOW_BEFORE < along < leg.length - LOW_AFTER):
            raise ValueError("gate low-altitude band leaves the leg")
        gates.append(GatePlacement(index, along, leg.at(along), leg.direction))
    return CoursePlan(route, tuple(gates), gate_count)


def reference_course(index):
    """Twelve host-only, reproducible examples for later native qualification.

    Four G/D turn pairs each at 1, 2 and 3 H; includes all-2m and mixed
    2/2.5/3m legs. No scenario is passed to Blockly as an AST parameter.
    """
    if type(index) is not int or not 0 <= index < 12:
        raise ValueError("reference course index must be 0..11")
    lengths = (
        (2.0, 2.0, 2.0),
        (2.0, 2.5, 3.0),
        (3.0, 2.5, 2.0),
    )[index // 4]
    turns = (
        ("G", "G"), ("G", "D"), ("D", "G"), ("D", "D"),
    )[index % 4]
    return plan_course(index + 100, lengths, turns, 1 + index // 4)
