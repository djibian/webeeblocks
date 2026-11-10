#!/usr/bin/env python3
"""Adversarial compact-v2 *fixtures*: not a native mutation or RESET proof."""
import math
from types import SimpleNamespace
from tools.grand_prix.native_compact_colliders_v1 import (
    ENTRY, HEADER, TAIL, compare_native_canons, parse_native_inventory,
)

CANON = 'GP_V2_L_TEST'
SECOND = 'GP_V2_H_TEST'
CANON_FLAGS = 1 | 2 | 16 | 32 | 128 | 2048
FLOOR_FLAGS = 1 | 8 | 16 | 256 | 512


def row(name, identifier, *, flags=CANON_FLAGS, position=(1., 2., 3.),
        physical=(.1, .2, .3), visual=None, rotation=(0., 0., 1., 0.)):
    if visual is None:
        visual = physical
    name = name.encode('ascii')
    assert len(name) < 48
    return ENTRY.pack(identifier, 7, 18, flags, name.ljust(48, b'\0'),
                      *(position + physical + visual + rotation))


def floor_record(*, flags=FLOOR_FLAGS, position=(0., 0., 0.),
                 physical=(12., 12., 0.), rotation=(0., 0., 1., 0.)):
    return row('', 30, flags=flags, position=position, physical=physical,
               rotation=rotation)


def roots():
    return (floor_record(),
            row('', 31, flags=8 | 16 | 1024),
            row('GP_ROUTE_EVALUATOR', 32, flags=16 | 8192))


def packet(rows, *, include_roots=True, incarnation=bytes(range(1, 17)),
           version=2, count=None, clock=8., revision=1,
           root_hash=1234, proto_roots=2):
    rows = tuple(rows) + (roots() if include_roots else ())
    if count is None:
        count = len(rows)
    return (HEADER.pack(version, count, 6, proto_roots, 12,
                        clock, revision, incarnation, root_hash) +
            b''.join(rows) + TAIL.pack(150000, 30000))


def decode(raw):
    return parse_native_inventory(raw, time_ms=8, supervisor_id=12)


def rejects(fn):
    try:
        fn()
    except (ValueError, RuntimeError):
        return
    raise AssertionError('corrupted or noncanonical compact observation accepted')


def check():
    targets = [SimpleNamespace(name=CANON, position=(1., 2., 3.), size=(.1, .2, .3)),
               SimpleNamespace(name=SECOND, position=(1., 2., 3.), size=(.1, .2, .3))]
    a, b = row(CANON, 10), row(SECOND, 11)
    baseline = packet((a, b))
    observed = decode(baseline)
    assert observed['payload_bytes'] == HEADER.size + 5 * ENTRY.size + TAIL.size
    assert observed['native_producer_ns'] == 150000
    assert observed['native_serialization_ns'] == 30000
    nominal = compare_native_canons(observed, targets,
                                    route_rectangles=((-.5, -.5, .5, .5),))
    assert nominal['canonical_count'] == 2 and nominal['floor_verified']
    assert nominal['full_coverage'] is False  # opaque PROTO remains unqualified

    # Strict canonical Box topology, visible Shape cardinality and tolerances.
    for raw in (
        packet((a,)), packet((a, row(CANON, 11))),
        packet((row(CANON, 10, flags=CANON_FLAGS ^ 128), b)),
        packet((row(CANON, 10, flags=CANON_FLAGS ^ 2048), b)),
        packet((row(CANON, 10, flags=CANON_FLAGS ^ 1), b)),
        packet((row(CANON, 10, position=(1.00001, 2., 3.)), b)),
        packet((row(CANON, 10, physical=(.4, .2, .3)), b)),
        packet((row(CANON, 10, visual=(.4, .2, .3)), b)),
        packet((row(CANON, 10, rotation=(0., 1., 0., .4)), b)),
        packet((a, b, row('GP_V2_FINAL_EXTRA', 13))),
    ):
        rejects(lambda raw=raw: compare_native_canons(
            decode(raw), targets, route_rectangles=((-.5, -.5, .5, .5),)))

    # Reject unlisted bodies, non-Box geometry and collision in a visual guide.
    outsider = row('FOREIGN_PHYSICAL', 41, flags=16)
    rejects(lambda: compare_native_canons(decode(packet((a, b, outsider))), targets))
    wrapped_box = row('UNLISTED_WRAP', 42, flags=16384)
    rejects(lambda: compare_native_canons(decode(packet((a, b, wrapped_box))), targets))
    guide = row('GP_V2_WHITE_COLLIDING', 43, flags=16 | 128)
    rejects(lambda: compare_native_canons(decode(packet((a, b, guide))), targets))

    # Floor Plane cannot be absent, duplicated, rotated, moved, unlocked,
    # changed to Box or reduced below route footprint.
    for floor in (
        floor_record(flags=FLOOR_FLAGS ^ 1),
        floor_record(flags=FLOOR_FLAGS ^ 256),
        floor_record(physical=(.1, .1, 0.)),
        floor_record(position=(0., 0., .1)),
        floor_record(rotation=(1., 0., 0., .2)),
    ):
        changed = (a, b, floor, roots()[1], roots()[2])
        rejects(lambda changed=changed: compare_native_canons(
            decode(packet(changed, include_roots=False)), targets,
            route_rectangles=((-1., -1., 1., 1.),)))
    rejects(lambda: compare_native_canons(
        decode(packet((a, b), include_roots=False)), targets))

    # Binary envelope provenance and malformed transport.
    for raw in (
        baseline[:-1], baseline + b'X', packet((a, b), version=77),
        packet((a, b), count=129), packet((a, b), count=-1),
        packet((a, b), clock=16), packet((a, b), incarnation=bytes(16)),
        packet((a, b), revision=0), packet((a, row(SECOND, 10))),
        packet((row(CANON, 10, physical=(math.inf, .2, .3)), b)),
        packet((a, b), root_hash=0),
    ):
        rejects(lambda raw=raw: decode(raw))

    # PROTO internals are inventoried, not silently certified as harmless.
    internal = row('PROTO_INTERNAL', 50, flags=4 | 32768)
    opaque = compare_native_canons(decode(packet((a, b, internal))), targets)
    assert opaque['proto_internal_count'] == 1 and not opaque['full_coverage']
    unexplained = row('UNKNOWN_INTERNAL', 51, flags=4 | 16384)
    rejects(lambda: compare_native_canons(decode(packet((a, b, unexplained))), targets))

    # A changed incarnation or revision must remain independently observable
    # even when serialized geometry has returned to precisely the same bytes.
    after_reset = decode(packet((a, b), incarnation=bytes(range(2, 18))))
    assert after_reset['incarnation'] != observed['incarnation']
    assert compare_native_canons(after_reset, targets)['canonical_count'] == 2
    restored = decode(packet((a, b), revision=3))
    assert restored['revision'] != observed['revision']
    assert compare_native_canons(restored, targets)['canonical_count'] == 2
    return 'PASS fixtures; NO native mutation/RESET or global safety qualification'


if __name__ == '__main__':
    print(check())
