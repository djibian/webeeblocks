#!/usr/bin/env python3
"""Adversarial *fixture* checks: not a native engine or mutation qualification."""
import math
import struct
from types import SimpleNamespace

from tools.grand_prix.native_compact_colliders_v1 import (
    ENTRY, HEADER, TAIL, compare_native_canons, parse_native_inventory,
)

CANON = 'GP_V2_L_TEST'
SECOND = 'GP_V2_H_TEST'


def row(name, identifier, *, flags=51, position=(1., 2., 3.),
        physical=(.1, .2, .3), visual=None, rotation=(0., 0., 1., 0.)):
    if visual is None:
        visual = physical
    encoded = name.encode('ascii')
    assert len(encoded) < 48
    return ENTRY.pack(identifier, 7, 18, flags, encoded.ljust(48, b'\0'),
                      *(position + physical + visual + rotation))


def packet(rows, *, incarnation=bytes(range(1, 17)), version=1, count=None,
           clock=8., revision=1, root_hash=1234, proto_roots=0):
    if count is None:
        count = len(rows)
    return (HEADER.pack(version, count, 6, proto_roots, 12, clock, revision,
                        incarnation, root_hash) + b''.join(rows) +
            TAIL.pack(150000, 30000))


def decode(raw):
    return parse_native_inventory(raw, time_ms=8, supervisor_id=12)


def rejects(fn):
    try:
        fn()
    except (ValueError, RuntimeError):
        return
    raise AssertionError('malformed or noncanonical native collider observation accepted')


def check():
    target = [SimpleNamespace(name=CANON, position=(1., 2., 3.), size=(.1, .2, .3)),
              SimpleNamespace(name=SECOND, position=(1., 2., 3.), size=(.1, .2, .3))]
    a, b = row(CANON, 10), row(SECOND, 11)
    baseline = packet([a, b])
    observed = decode(baseline)
    assert observed['payload_bytes'] == HEADER.size + 2 * ENTRY.size + TAIL.size
    assert observed['native_producer_ns'] == 150000
    assert observed['native_serialization_ns'] == 30000
    assert compare_native_canons(observed, target)['canonical_count'] == 2

    # Adversarial negative colliders, corrupt wire and stale clock/provenance.
    for raw in (
        packet([a]), packet([a, row(CANON, 11)]),
        packet([row(CANON, 10, flags=50), b]),
        packet([row(CANON, 10, position=(1.1, 2., 3.)), b]),
        packet([row(CANON, 10, physical=(.4, .2, .3)), b]),
        packet([row(CANON, 10, visual=(.4, .2, .3)), b]),
        packet([row(CANON, 10, rotation=(0., 1., 0., .4)), b]),
        packet([a, b, row('GP_V2_FINAL_EXTRA', 13)]),
    ):
        rejects(lambda raw=raw: compare_native_canons(decode(raw), target))
    for raw in (
        baseline[:-1], baseline + b'X', packet([a, b], version=88),
        packet([a, b], count=129), packet([a, b], count=-1),
        packet([a, b], clock=16), packet([a, b], incarnation=bytes(16)),
        packet([a, b], revision=0), packet([a, row(SECOND, 10)]),
        packet([row(CANON, 10, physical=(math.inf, .2, .3)), b]),
        packet([a, b], root_hash=0),
    ):
        rejects(lambda raw=raw: decode(raw))

    # These counterexamples intentionally retain non-authoritative unknowns.
    floor = row('FLOOR_INTERNAL', 41, flags=4, physical=(0., 0., 0.))
    result = compare_native_canons(decode(packet([a, b, floor], proto_roots=2)), target)
    assert result['unknown_count'] >= 1 and result['proto_roots'] == 2
    outsider = row('FOREIGN_PHYSICAL', 42, flags=16)
    assert compare_native_canons(decode(packet([a, b, outsider])), target)['extra_root_count'] == 1

    # No mutation-interleaving or RESET freshness claim can follow from
    # identical geometry at the same simulated time.
    after_reset = decode(packet([a, b], incarnation=bytes(range(2, 18))))
    assert after_reset['incarnation'] != observed['incarnation']
    assert compare_native_canons(after_reset, target)['canonical_count'] == 2
    same_geometry_new_revision = decode(packet([a, b], revision=3))
    assert same_geometry_new_revision['revision'] != observed['revision']
    assert compare_native_canons(same_geometry_new_revision, target)['canonical_count'] == 2
    return 1


if __name__ == '__main__':
    print('compact collider wire fixture tests passed:', check(),
          '(NO native Floor/PROTO/RESET/mutation qualification)')
