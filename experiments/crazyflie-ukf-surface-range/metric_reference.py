#!/usr/bin/env python3
"""Conditional clock/metric envelopes for X3 external reference annotations.

No physical truth, clock model, estimator performance or confidence level is
certified by this arithmetic. No reference value comes from UKF/S3 telemetry.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re

from frozen_pressure_probe import KINDS, read_barometer


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("numeric bound required")
    if not math.isfinite(value):
        raise ValueError("finite bound required")
    return Fraction(str(value))


def interval(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("two explicit interval endpoints required")
    lo, hi = map(number, value)
    if lo > hi:
        raise ValueError("reversed interval")
    return lo, hi


def enclosure(bounds):
    """Round outward only when conversion would exclude an exact endpoint."""
    result = []
    for index, exact in enumerate(bounds):
        value = float(exact)
        if not math.isfinite(value):
            raise ValueError("unrepresentable result")
        if index == 0 and Fraction(value) > exact:
            value = math.nextafter(value, -math.inf)
        elif index == 1 and Fraction(value) < exact:
            value = math.nextafter(value, math.inf)
        if not math.isfinite(value):
            raise ValueError("unrepresentable outward bound")
        result.append(value)
    return result


def clip(vertices, a, b, c):
    """Intersect the convex clock polygon with a*rate + b*offset <= c."""
    if not vertices:
        return []
    result = []
    previous = vertices[-1]
    dp = a * previous[0] + b * previous[1] - c
    for current in vertices:
        dc = a * current[0] + b * current[1] - c
        if (dp <= 0) != (dc <= 0):
            ratio = dp / (dp - dc)
            result.append(tuple(p + ratio * (q - p) for p, q in zip(previous, current)))
        if dc <= 0:
            result.append(current)
        previous, dp = current, dc
    return list(dict.fromkeys(result))


def witness(value, reference_ids):
    if not isinstance(value, dict) or value.get("source") not in reference_ids:
        raise ValueError("witness must name a retained external-reference source")
    if not isinstance(value.get("locator"), str) or not value["locator"].strip():
        raise ValueError("an inspectable witness locator is required")


def clocks(anchors, reference_ids):
    if not isinstance(anchors, list) or len(anchors) < 2:
        raise ValueError("at least two bracketing synchronization observations required")
    parsed = []
    for anchor in anchors:
        witness(anchor["witness"], reference_ids)
        r, d = interval(anchor["reference_s"]), interval(anchor["device_s"])
        if r[0] < 0 or d[0] < 0:
            raise ValueError("clock coordinates must be nonnegative elapsed seconds")
        if parsed and (r[0] <= parsed[-1][0][1] or d[0] <= parsed[-1][1][1]):
            raise ValueError("synchronization observations must be strictly ordered and disjoint")
        parsed.append((r, d))
    r0, d0 = parsed[0]
    r1, d1 = parsed[-1]
    amin = (d1[0] - d0[1]) / (r1[1] - r0[0])
    amax = (d1[1] - d0[0]) / (r1[0] - r0[1])
    bmin, bmax = d0[0] - amax * r0[1], d0[1] - amin * r0[0]
    polygon = [(amin, bmin), (amax, bmin), (amax, bmax), (amin, bmax)]
    for r, d in parsed:
        # A positive affine clock maps the reference interval onto a range
        # which must intersect the observed device interval.
        polygon = clip(polygon, -r[1], -1, -d[0])
        polygon = clip(polygon, r[0], 1, d[1])
    if not polygon:
        raise ValueError("synchronization observations admit no common affine clock")
    return polygon, (r0[1], r1[0])


def mapped(value, polygon, domain):
    lo, hi = interval(value)
    if lo < domain[0] or hi > domain[1]:
        raise ValueError("reference interval would extrapolate beyond synchronization observations")
    return (min(a * lo + b for a, b in polygon),
            max(a * hi + b for a, b in polygon))


def delta(before, after):
    return after[0] - before[1], after[1] - before[0]


def analyze(spec, duration, reference_ids):
    if spec.get("schema") != "webeeblocks.x3.metric-reference-input.v1":
        raise ValueError("unknown metric-reference schema")
    clock = spec["clock"]
    if clock.get("model") != "affine" or clock.get("device_origin") != "first-barometer-log-row":
        raise ValueError("explicit affine model and first-barometer-log-row origin required")
    polygon, domain = clocks(clock["anchors"], reference_ids)
    if any(interval(a["device_s"])[1] > duration for a in clock["anchors"]):
        raise ValueError("synchronization observation outside the recorded device interval")
    covered_end = min(duration, min(a * domain[1] + b for a, b in polygon))
    calibration = spec["calibration"]
    witness(calibration["witness"], reference_ids)
    c0 = mapped(calibration["start_reference_s"], polygon, domain)
    c1 = mapped(calibration["end_reference_s"], polygon, domain)
    if c0[0] < 0 or c1[0] - c0[1] < 30:
        raise ValueError("all admissible calibration endpoints must allow at least 30 seconds")
    events, seen = [], set()
    previous_end = c1[1]
    if not isinstance(spec["events"], list) or not spec["events"]:
        raise ValueError("at least one externally annotated episode required")
    for event in spec["events"]:
        identifier, kind = event["id"], event["kind"]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen or kind not in KINDS:
            raise ValueError("unique event identifier and known descriptive kind required")
        seen.add(identifier)
        witness(event["witness"], reference_ids)
        start = mapped(event["start_reference_s"], polygon, domain)
        end = mapped(event["end_reference_s"], polygon, domain)
        if start[0] < previous_end + 2 or end[0] <= start[1]:
            raise ValueError("uncertain episodes must remain ordered with two-second plateaus")
        if end[1] + Fraction(3, 4) > covered_end:
            raise ValueError("recording/synchronization does not cover every admissible post-event window")
        previous_end = end[1]
        zb, za = interval(event["z_before_m"]), interval(event["z_after_m"])
        hb, ha = interval(event["surface_before_m"]), interval(event["surface_after_m"])
        cb, ca = delta(hb, zb), delta(ha, za)
        if cb[0] < 0 or ca[0] < 0:
            raise ValueError("reference bounds allow vehicle below the measured surface")
        events.append({"id": identifier, "kind": kind, "witness": event["witness"],
                       "start_device_s": enclosure(start), "end_device_s": enclosure(end),
                       "before_window_start_s": enclosure(tuple(t - Fraction(1, 2) for t in start)),
                       "after_window_start_s": enclosure(tuple(t + Fraction(1, 4) for t in end)),
                       "reference_delta_z_m": enclosure(delta(zb, za)),
                       "reference_delta_surface_m": enclosure(delta(hb, ha)),
                       "reference_delta_clearance_m": enclosure(delta(cb, ca))})
    return {"schema": "webeeblocks.x3.metric-reference-result.v1", "status": "COMPUTED_CONDITIONAL",
            "calibration_start_device_s": enclosure(c0), "calibration_end_device_s": enclosure(c1),
            "clock_vertices_rate_offset": [[str(a), str(b)] for a, b in polygon],
            "clock_domain_reference_s": enclosure(domain), "events": events,
            "observed_kinds": sorted({e["kind"] for e in events}),
            "missing_kinds": sorted(set(KINDS) - {e["kind"] for e in events}),
            "physical_reference_validated": False, "affine_clock_validated": False,
            "independent_displacement_verdict": "UNPROVEN", "physical_verdict": None,
            "scope": "conditional external-reference envelopes; no sensor prediction or acceptance verdict",
            "limits": ["Bounds and physical stillness are annotations, not machine-verified measurements.",
                       "Clock interpolation assumes one positive affine clock between observed anchors.",
                       "Device log time is not sensor producer time; latency and aliasing remain unproven.",
                       "Interval arithmetic preserves supplied bounds; it assigns no confidence level.",
                       "Window start intervals must not be replaced silently by their midpoints."]}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def run(path):
    raw_spec = path.read_bytes()
    spec = json.loads(raw_spec, object_pairs_hook=unique_object)
    root = path.parent.resolve()
    sources, identities, reference_ids = {}, set(), set()
    for source in spec["sources"]:
        identifier = source["id"]
        if not isinstance(identifier, str) or not identifier or identifier in sources:
            raise ValueError("unique source identifier required")
        relative = Path(source["path"])
        target = (root / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(root) or not target.is_file():
            raise ValueError("source must be a retained file inside the specification directory")
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            stat_result = os.fstat(stream.fileno())
            identity = (stat_result.st_dev, stat_result.st_ino)
            if identity in identities:
                raise ValueError("one file cannot act as two independent sources")
            identities.add(identity)
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) or digest.hexdigest() != source["sha256"]:
            raise ValueError("source digest mismatch")
        if source["kind"] == "external-metric-reference":
            reference_ids.add(identifier)
        elif source["kind"] != "barometer-capture":
            raise ValueError("unknown source kind")
        sources[identifier] = (source, target)
    clock_source, clock_path = sources[spec["clock"]["barometer_source"]]
    if clock_source["kind"] != "barometer-capture" or not reference_ids:
        raise ValueError("separate barometer and external metric-reference files required")
    raw_baro = clock_path.read_bytes()
    if hashlib.sha256(raw_baro).hexdigest() != clock_source["sha256"]:
        raise ValueError("barometer changed during input inspection")
    samples = read_barometer(raw_baro)
    result = analyze(spec, number(samples[-1][0]), reference_ids)
    result["input_provenance"] = {"specification_sha256": hashlib.sha256(raw_spec).hexdigest(),
                                  "sources": [item[0] for item in sources.values()],
                                  "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                  "barometer_parser_sha256": hashlib.sha256(Path(__file__).with_name("frozen_pressure_probe.py").read_bytes()).hexdigest()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("specification", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run(args.specification)
        serialized = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        parser.exit(1, f"UNPROVEN: {exc}; retain raw inputs and any partial output\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
