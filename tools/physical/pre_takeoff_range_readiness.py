#!/usr/bin/env python3
"""Read-only admission of AST-demanded ranges before a host-owned takeoff.

The caller is the lexical trusted-host takeoff transport, inside its existing
effect exclusion and after teacher approval. This is a necessary availability
check, not clearance, future availability, or sensor-producer freshness proof.
No sample is passed to the student interpreter or reused after takeoff.
"""
from __future__ import annotations

from prepare_x3_independent_capture import CflibParamAdapter
from probe_reference_hardware import _parse_uint
from range_observer import FreshRangeObserver, RangeObservation, range_mm_to_m, SUPPORTED_DIRECTIONS
from takeoff_command import _parse_ast_binding


class PreTakeoffRangeError(RuntimeError):
    pass


def demanded_range_directions(ast_binding: str) -> tuple[str, ...]:
    """Collect syntactic demand; never evaluate expressions or select a branch.

    Production has already validated the exact AST with the shared interpreter.
    Conservatively include nested/short-circuited expressions and both branches;
    checking only an observed branch would make sensor admission self-dependent.
    """
    pending = [_parse_ast_binding(ast_binding)["program"]]
    directions = set()
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("kind") == "range":
                if (set(value) != {"kind", "direction", "unit"}
                        or type(value["direction"]) is not str
                        or value["direction"] not in SUPPORTED_DIRECTIONS
                        or value["unit"] != "m"):
                    raise PreTakeoffRangeError("unsupported exact-AST range demand")
                directions.add(value["direction"])
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return tuple(direction for direction in SUPPORTED_DIRECTIONS if direction in directions)


def require_pre_takeoff_ranges(crazyflie, epoch_reader, ast_binding):
    """One post-request finite sample per demanded direction, with no retry.

    An unavailable first sample, stale epoch, malformed evidence, filter change,
    or uncertain observer closure vetoes takeoff. All calls are read-only PARAM
    or LOG operations; the enclosing host retains all effect authority.
    """
    directions = demanded_range_directions(ast_binding)
    if not directions:
        return ()
    epoch = epoch_reader()
    if type(epoch) is not str or not epoch.strip() or epoch != epoch.strip():
        raise PreTakeoffRangeError("pre-takeoff range connection epoch is unavailable")

    def verify_epoch():
        if epoch_reader() != epoch:
            raise PreTakeoffRangeError("connection epoch changed during pre-takeoff range check")

    adapter = CflibParamAdapter(crazyflie)

    def require_default_filter():
        verify_epoch()
        ctype, _, _ = adapter.describe("multiranger.filterMask")
        raw = adapter.read_fresh("multiranger.filterMask")
        verify_epoch()
        if ctype != "uint16_t" or _parse_uint(raw, "multiranger.filterMask") != 1:
            raise PreTakeoffRangeError("unchanged official RANGE_VALID-only filter required before takeoff")

    require_default_filter()
    samples = []
    for direction in directions:
        verify_epoch()
        observer = FreshRangeObserver(crazyflie, epoch_reader, direction)
        primary_error = None
        try:
            observer.open()
            if (observer.bound_crazyflie is not crazyflie
                    or observer.bound_connection_epoch != epoch
                    or observer.direction != direction):
                raise PreTakeoffRangeError("pre-takeoff range observer binding mismatch")
            sample = observer.read()
            if (type(sample) is not RangeObservation
                    or sample.connection_epoch != epoch or sample.direction != direction
                    or type(sample.firmware_timestamp_ms) is not int
                    or not 0 <= sample.firmware_timestamp_ms < (1 << 24)
                    or type(sample.range_m) is not float
                    or sample.range_m != range_mm_to_m(sample.raw_mm)):
                raise PreTakeoffRangeError("pre-takeoff range sample binding/value mismatch")
            verify_epoch()
            samples.append(sample)
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            # Cleanup is attempted exactly once, including a failed open/read.
            # Any cleanup exception propagates and vetoes the motor command.
            try:
                observer.close()
            except Exception as exc:
                if primary_error is not None:
                    raise PreTakeoffRangeError(
                        "pre-takeoff range cleanup uncertain: " + str(exc)
                    ) from primary_error
                raise
        verify_epoch()
    require_default_filter()
    return tuple(samples)
