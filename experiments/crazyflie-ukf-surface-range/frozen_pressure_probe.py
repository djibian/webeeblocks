#!/usr/bin/env python3
"""Frozen descriptive pressure probe for #70; never a physical/estimator verdict."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
from statistics import median


WINDOW_S = 0.5
POST_DELAY_S = 0.25
MAX_GAP_S = 0.04
MIN_WINDOW_ROWS = 20
KINDS = ("stationary", "terrain", "vertical", "mixed")
MODULUS = 1 << 24


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: finite number required")
    return float(value)


def read_barometer(raw: bytes) -> list[tuple[float, float]]:
    """Preserve raw bytes outside this function; unwrap only the device log clock."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    required = {"cf_timestamp_ms", "host_monotonic_s", "baro.asl", "baro.pressure", "baro.temp"}
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not required <= set(reader.fieldnames):
        raise ValueError("continuous barometer and device/receipt clocks required")
    samples = []
    previous = previous_host = None
    elapsed_ms = 0
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed CSV row")
        stamp = int(row["cf_timestamp_ms"])
        host = finite(float(row["host_monotonic_s"]), "host timestamp")
        values = [finite(float(row[name]), name) for name in ("baro.asl", "baro.pressure", "baro.temp")]
        if not 0 <= stamp < MODULUS or (previous_host is not None and host <= previous_host):
            raise ValueError("invalid device or nonincreasing receipt timestamp")
        if previous is not None:
            gap = (stamp - previous) % MODULUS
            if gap == 0 or gap >= MODULUS // 2 or gap / 1000 > MAX_GAP_S + 1e-9:
                raise ValueError("duplicate/backward timestamp or barometer gap over 40 ms")
            elapsed_ms += gap
        samples.append((elapsed_ms / 1000, values[0]))
        previous, previous_host = stamp, host
    if not samples:
        raise ValueError("empty barometer stream")
    return samples


def window(samples, start, end):
    # Half-open windows avoid counting one boundary sample twice.
    selected = [(t, y) for t, y in samples if start <= t < end]
    minimum = math.ceil((end - start) / WINDOW_S * MIN_WINDOW_ROWS - 1e-9)
    if len(selected) < minimum or selected[0][0] - start > MAX_GAP_S + 1e-9 or end - selected[-1][0] > MAX_GAP_S + 1e-9:
        raise ValueError("insufficient observed samples/edge coverage for a fixed window")
    return selected


def contrast(samples, before_start, after_start, slope):
    before = window(samples, before_start, before_start + WINDOW_S)
    after = window(samples, after_start, after_start + WINDOW_S)
    raw = median(y for _, y in after) - median(y for _, y in before)
    observed_separation = median(t for t, _ in after) - median(t for t, _ in before)
    drift = slope * observed_separation
    return {"before_s": [before_start, before_start + WINDOW_S],
            "after_s": [after_start, after_start + WINDOW_S],
            "rows_before": len(before), "rows_after": len(after),
            "observed_median_time_separation_s": observed_separation,
            "raw_delta_m": raw, "calibration_drift_m": drift,
            "drift_corrected_delta_m": raw - drift}


def analyze(samples, specification):
    if specification.get("schema") != "webeeblocks.x3.pressure-probe-input.v1":
        raise ValueError("unknown pressure probe input schema")
    calibration = specification["calibration"]
    c0 = finite(calibration["start_s"], "calibration start")
    c1 = finite(calibration["end_s"], "calibration end")
    if c0 < 0 or c1 - c0 < 30:
        raise ValueError("at least 30 s of prior stationary calibration required")
    baseline = window(samples, c0, c1)
    # Centered ordinary least squares. No IID standard error is inferred.
    tmean = sum(t - c0 for t, _ in baseline) / len(baseline)
    ymean = sum(y for _, y in baseline) / len(baseline)
    slope = sum((t - c0 - tmean) * (y - ymean) for t, y in baseline) / sum((t - c0 - tmean) ** 2 for t, _ in baseline)
    events = specification["events"]
    if not events:
        raise ValueError("at least one complete annotated episode required")
    results, identifiers = [], set()
    previous_end = c1
    for event in events:
        identifier, kind = event["id"], event["kind"]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers or kind not in KINDS:
            raise ValueError("unique event ID and known descriptive kind required")
        identifiers.add(identifier)
        start = finite(event["start_s"], "event start")
        end = finite(event["end_s"], "event end")
        if start < previous_end + 2 or end <= start:
            raise ValueError("ordered episodes with at least 2 s plateaus and positive duration required")
        previous_end = end
        # Every kind passes through this identical calculation; no UKF gate.
        before_start, after_start = start - WINDOW_S, end + POST_DELAY_S
        measured = contrast(samples, before_start, after_start, slope)
        separation = after_start - before_start
        span = separation + WINDOW_S
        pairs = []
        for index in range(math.floor((c1 - c0 + 1e-9) / span)):
            pair_start = c0 + index * span
            pairs.append(contrast(samples, pair_start, pair_start + separation, slope))
        residuals = [p["drift_corrected_delta_m"] for p in pairs]
        results.append({"id": identifier, "kind": kind, "start_s": start, "end_s": end,
                        "pressure_contrast": measured, "matched_calibration_pairs": pairs,
                        "empirical_residual_min_m": min(residuals) if residuals else None,
                        "empirical_residual_max_m": max(residuals) if residuals else None,
                        "pair_count": len(pairs), "effective_independent_count": None,
                        "uncertainty_bound_m": None,
                        "uncertainty_status": "UNPROVEN: finite calibration extrema are not a predictive bound"})
    return {"schema": "webeeblocks.x3.pressure-probe-result.v1", "status": "COMPUTED",
            "calibration_s": [c0, c1], "calibration_slope_m_per_s": slope,
            "calibration_rows": len(baseline), "events": results,
            "observed_kinds": sorted({e["kind"] for e in results}),
            "independent_displacement_verdict": "UNPROVEN", "physical_verdict": None,
            "scope": "descriptive pressure statistic; no IMU fusion, metric-reference verdict, terrain decision or confidence level",
            "timing_boundary": "window endpoint is end+0.75 s in log time, not a proven end-to-end latency"}


def run(spec_path: Path):
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes)
    source = spec["barometer"]
    path = Path(source["path"])
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("barometer path must stay inside the input directory")
    root = spec_path.parent.resolve()
    path = (root / path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("barometer input missing or outside the input directory")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) or digest != source["sha256"]:
        raise ValueError("barometer input digest mismatch")
    result = analyze(read_barometer(raw), spec)
    result["input_provenance"] = {"specification_sha256": hashlib.sha256(spec_bytes).hexdigest(),
                                  "barometer_sha256": digest, "barometer_bytes": len(raw),
                                  "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
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
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"UNPROVEN: {exc}; preserve raw inputs and any partial output\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
