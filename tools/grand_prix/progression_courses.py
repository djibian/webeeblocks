"""Deterministic host geometry for the Grand Prix classroom progression."""
from dataclasses import dataclass

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
    pad_distance_from_h: float = .70


_VARIANTS = {
    1: (_Variant((1.4, 1.8, 1.6), ('G', 'D')),),
    2: (_Variant((2.5,), gates=((0, .80),)),),
    3: (_Variant((1.5, 1.5, 1.5), ('G', 'G'),
                 ((0, .75), (1, .75), (2, .75)), first_direction=1,
                 # The last pad must be beyond the last H's clearing plane.
                 pad_distance_from_h=.225),),
    4: tuple(_Variant((length,), pads=(2,), required_pad=2)
             for length in (1., 1.4, 1.8)),
    5: tuple(_Variant((length, 2.5), (turn,), pads=(2, 3),
                      required_pad=3 if turn == 'G' else 2)
             for length, turn in ((1., 'G'), (1.2, 'D'), (1.4, 'G'),
                                  (1.6, 'D'), (1.8, 'G'))),
    6: (
        _Variant((2.25,), gates=((0, .75),)),
        _Variant((2.50,), gates=((0, .90),)),
        _Variant((2.75,), gates=((0, 1.05),)),
        _Variant((2.,)),
        # At 2.02 m the closed panel fell on the R2025a 2 m range limit.
        _Variant((2.01,)),
    ),
    7: (
        _Variant((1.5, 1.8), ('G',)),
        _Variant((2., 1.5), ('D',)),
        _Variant((2., 2.5), ('G',), ((0, .90),)),
        _Variant((1.8, 2.), ('D',), ((0, .85),)),
        _Variant((1.5, 2.5), ('G',), ((1, .85),)),
        _Variant((2.5, 2.), ('D',), ((1, .75),)),
        _Variant((2.5, 2.5), ('G',), ((1, 1.),)),
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
