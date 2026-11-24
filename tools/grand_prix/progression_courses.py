"""Deterministic host geometry for the Grand Prix classroom progression."""
from dataclasses import dataclass, replace

from tools.grand_prix.route_courses_v2 import CoursePlan, GatePlacement, course_from_identifier
from tools.grand_prix.route_v2 import _build_route


@dataclass(frozen=True)
class _Variant:
    lengths: tuple[float, ...]
    turns: tuple[str, ...] = ()
    gates: tuple[tuple[int, float], ...] = ()
    first_direction: int = 0
    pads: tuple[int, ...] = (1,)
    required_pad: int = 1
    pad_distance_from_h: float = .30


_VARIANTS = {
    1: (_Variant((1.4, 1.8, 1.6), ('G', 'D')),),
    2: (_Variant((2.5,), gates=((0, .80),)),),
    3: (_Variant((2.5, 2.5, 2.8), ('G', 'G'),
                 ((0, 1.25), (1, 1.25), (2, 1.25)), first_direction=1,
                 # Three 2.5m pupil legs end on the pad, with the closed H 0.30m farther.
                 pad_distance_from_h=.30),),
    4: tuple(_Variant((length,), pads=(2,), required_pad=2)
             for length in (1., 1.4, 1.8)),
    5: tuple(_Variant((length, 2.5), (turn,), pads=(2, 3),
                      required_pad=3 if turn == 'G' else 2,
                      pad_distance_from_h=.30)
             for length, turn in ((1., 'G'), (1., 'D'), (1.4, 'G'),
                                  (1.4, 'D'), (1.8, 'G'))),
    6: (
        # Owner-approved 2026-11-20: the initial frontal face alone must not
        # identify an open versus closed H. V2/V4 and V3/V5 share first faces.
        # Keep the pad 0.70 m before the closed H on every A6 variant.
        _Variant((2.25,), gates=((0, .75),), pad_distance_from_h=.50),
        _Variant((2.90,), gates=((0, 1.40),), pad_distance_from_h=.50),
        _Variant((3.00,), gates=((0, 1.50),), pad_distance_from_h=.50),
        _Variant((1.40,), pad_distance_from_h=.50),
        _Variant((1.50,), pad_distance_from_h=.50),
    ),
    7: (
        _Variant((1.5, 1.8), ('G',), pad_distance_from_h=.50),
        _Variant((2., 1.5), ('D',), pad_distance_from_h=.50),
        _Variant((2., 2.5), ('G',), ((0, .90),), pad_distance_from_h=.50),
        _Variant((1.8, 2.), ('D',), ((0, .85),), pad_distance_from_h=.50),
        _Variant((1.5, 2.5), ('G',), ((1, .85),), pad_distance_from_h=.50),
        _Variant((2.5, 2.), ('D',), ((1, .75),), pad_distance_from_h=.50),
        _Variant((2.5, 2.5), ('G',), ((1, 1.),), pad_distance_from_h=.50),
    ),
}


def progression_course(activity, variant=1):
    """Construct one canonical scene input. Variant numbers are one-based."""
    if type(activity) is not int or activity not in _VARIANTS:
        raise ValueError('progression activity must be 1..7')
    variants = _VARIANTS[activity]
    if type(variant) is not int or not 1 <= variant <= len(variants):
        raise ValueError(f'activity {activity} has variants 1..{len(variants)}')
    spec = variants[variant - 1]
    route = _build_route(variant, spec.lengths, spec.turns,
                         first_direction=spec.first_direction)
    if activity == 5:
        # At 2.26 m into the last leg the rear ray could see an arm at
        # +/-8.2 degrees. Set the entire L back along the outgoing axis,
        # preserving its shape, its frontal face and the course boundaries.
        corner, = route.corners
        last_leg = route.legs[-1]
        def set_back(point):
            along, lateral = last_leg.local(point)
            return last_leg.at(along - .10, lateral)
        route = replace(route, corners=(replace(corner, outer=set_back(corner.outer),
                        back_tip=set_back(corner.back_tip),
                        onward_tip=set_back(corner.onward_tip)),))
    gates = tuple(GatePlacement(index, along, route.legs[index].at(along),
                                route.legs[index].direction)
                  for index, along in spec.gates)
    return CoursePlan(route, gates, len(gates), (activity, variant), spec.pads,
                      spec.required_pad, spec.pad_distance_from_h)


def require_canonical_course_geometry(course):
    """Check host geometry without admitting a scene to the active Runtime."""
    if type(course) is not CoursePlan:
        raise ValueError('canonical CoursePlan required')
    if course.progression is None:
        expected = course_from_identifier(course.identifier)
    else:
        if type(course.progression) is not tuple or len(course.progression) != 2:
            raise ValueError('expected an activity and variant')
        expected = progression_course(*course.progression)
    if expected != course:
        raise ValueError('forged or inconsistent CoursePlan')
