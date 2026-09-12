#!/usr/bin/env python3
"""Frozen conditional X3 vertical replay predictor for #70.

This component never certifies a physical reference, timing model, sensor error
bound or flight capability. It excludes ToF-derived stateEstimate Z/VZ and S3
signals from the predicted vehicle displacement.
"""

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


G = 9.80665
MODULUS = 1 << 24
KINDS = ("stationary", "terrain", "vertical", "mixed")
WINDOW_S = 0.5
POST_DELAY_S = 0.25
BARO_MAX_GAP_S = 0.04
BARO_MIN_WINDOW_ROWS = 20
IMU_MAX_GAP_S = 0.05


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: finite number required")
    return float(value)


def nonnegative(value, name):
    value = finite(value, name)
    if value < 0:
        raise ValueError(f"{name}: nonnegative number required")
    return value


def interval(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name}: two explicit endpoints required")
    lo, hi = finite(value[0], name), finite(value[1], name)
    if lo > hi:
        raise ValueError(f"{name}: reversed interval")
    return lo, hi


def unwrap_rows(raw: bytes, required: tuple[str, ...], origin_stamp: int | None = None, max_gap_s: float | None = None):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    base = ("cf_timestamp_ms", "host_monotonic_s")
    required_headers = set(base + required)
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not required_headers <= set(reader.fieldnames):
        raise ValueError("required capture columns missing")
    parsed = []
    previous_stamp = previous_host = previous_elapsed_ms = None
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed CSV row")
        try:
            stamp = int(row["cf_timestamp_ms"])
            host = finite(float(row["host_monotonic_s"]), "host timestamp")
            values = tuple(finite(float(row[name]), name) for name in required)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"malformed capture value: {exc}") from exc
        if not 0 <= stamp < MODULUS or (previous_host is not None and host <= previous_host):
            raise ValueError("invalid device or nonincreasing host timestamp")
        if previous_stamp is not None:
            gap = (stamp - previous_stamp) % MODULUS
            if gap == 0 or gap >= MODULUS // 2:
                raise ValueError("duplicate/backward device timestamp")
            if max_gap_s is not None and gap / 1000.0 > max_gap_s + 1e-12:
                raise ValueError("capture gap exceeds frozen replay limit")
        if origin_stamp is None:
            origin_stamp = stamp
        elapsed_mod_ms = (stamp - origin_stamp) % MODULUS
        if elapsed_mod_ms == MODULUS // 2:
            raise ValueError("source cannot be aligned to the barometer clock origin")
        elapsed_ms = elapsed_mod_ms if elapsed_mod_ms < MODULUS // 2 else elapsed_mod_ms - MODULUS
        if previous_elapsed_ms is not None and elapsed_ms <= previous_elapsed_ms:
            raise ValueError("source cannot be aligned to the barometer clock origin")
        parsed.append((elapsed_ms / 1000.0, host, values))
        previous_stamp, previous_host, previous_elapsed_ms = stamp, host, elapsed_ms
    if not parsed:
        raise ValueError("empty required capture stream")
    return origin_stamp, parsed


def read_sources(barometer_raw: bytes, imu_raw: bytes):
    origin, barometer = unwrap_rows(barometer_raw, ("baro.asl",), max_gap_s=BARO_MAX_GAP_S)
    _, imu = unwrap_rows(imu_raw, ("acc.x", "acc.y", "acc.z"), origin, max_gap_s=IMU_MAX_GAP_S)
    return barometer, imu


def vertical_force_interval_g(ax, ay, az, specific_force_error_g, max_tilt_deg):
    """Conservative world-up specific-force bound without estimator attitude.

    The body/world vertical angle is only assumed to be within max_tilt_deg.
    No UKF/EKF attitude, ToF-derived state, S3 state or range value participates.
    """
    if max_tilt_deg >= 90:
        raise ValueError("tilt bound must stay below 90 deg for the body-Z cone model")
    alpha = math.radians(max_tilt_deg)
    c, s = math.cos(alpha), math.sin(alpha)
    e = specific_force_error_g
    zlo, zhi = az - e, az + e
    z_candidates = (zlo, zhi, zlo * c, zhi * c)
    horizontal_max = math.hypot(abs(ax) + e, abs(ay) + e)
    return min(z_candidates) - horizontal_max * s, max(z_candidates) + horizontal_max * s


def median_interval(pairs):
    return median(lo for lo, _ in pairs), median(hi for _, hi in pairs)


def preparation(barometer, imu, spec, reference):
    c0 = interval(reference["calibration_start_device_s"], "calibration start")
    c1 = interval(reference["calibration_end_device_s"], "calibration end")
    # Use only time guaranteed to be inside calibration for every admissible endpoint.
    guaranteed_start, guaranteed_end = c0[1], c1[0]
    if guaranteed_start < 0 or guaranteed_end - guaranteed_start < 30:
        raise ValueError("at least 30 s of guaranteed stationary calibration required")

    bounds = spec["declared_bounds"]
    sf_error = nonnegative(bounds["specific_force_error_g"], "specific-force error")
    tilt = nonnegative(bounds["max_body_z_tilt_deg"], "body-Z tilt bound")
    if tilt >= 90:
        raise ValueError("tilt bound must stay below 90 deg for the body-Z cone model")
    v0_error = nonnegative(bounds["initial_velocity_error_m_s"], "initial velocity error")
    baro_error = nonnegative(bounds["barometer_displacement_error_m"], "barometer displacement error")
    sensor_time_error = nonnegative(bounds["sensor_time_error_s"], "sensor time error")
    delivery_latency = nonnegative(bounds["delivery_latency_error_s"], "delivery latency error")

    force_samples = []
    nominal_samples = []
    for t, _, values in imu:
        if guaranteed_start <= t <= guaranteed_end:
            ax, ay, az = values
            nominal_samples.append(az)
            force_samples.append(vertical_force_interval_g(ax, ay, az, sf_error, tilt))
    if len(force_samples) < 100:
        raise ValueError("insufficient IMU calibration coverage")
    nominal_zero_g = median(nominal_samples)
    zero_lo_g, zero_hi_g = median_interval(force_samples)

    # A descriptive barometer drift slope, frozen to guaranteed prior calibration.
    bcal = [(t, values[0]) for t, _, values in barometer if guaranteed_start <= t <= guaranteed_end]
    if len(bcal) < 100:
        raise ValueError("insufficient barometer calibration coverage")
    tmean = sum(t for t, _ in bcal) / len(bcal)
    ymean = sum(y for _, y in bcal) / len(bcal)
    denom = sum((t - tmean) ** 2 for t, _ in bcal)
    if denom <= 0:
        raise ValueError("degenerate barometer calibration")
    baro_slope = sum((t - tmean) * (y - ymean) for t, y in bcal) / denom
    return {"guaranteed_calibration_s": [guaranteed_start, guaranteed_end],
            "nominal_zero_specific_force_g": nominal_zero_g,
            "zero_specific_force_interval_g": [zero_lo_g, zero_hi_g],
            "barometer_drift_m_per_s": baro_slope,
            "bounds": {"specific_force_error_g": sf_error,
                       "max_body_z_tilt_deg": tilt,
                       "initial_velocity_error_m_s": v0_error,
                       "barometer_displacement_error_m": baro_error,
                       "sensor_time_error_s": sensor_time_error,
                       "delivery_latency_error_s": delivery_latency}}


def candidate_window_starts(samples, lo, hi, width=WINDOW_S):
    if lo > hi:
        raise ValueError("reversed window-start range")
    starts = {lo, hi}
    for t, *_ in samples:
        for boundary in (t, t - width):
            if lo <= boundary <= hi:
                starts.add(boundary)
                lower = math.nextafter(boundary, -math.inf)
                upper = math.nextafter(boundary, math.inf)
                if lo <= lower <= hi:
                    starts.add(lower)
                if lo <= upper <= hi:
                    starts.add(upper)
    return sorted(starts)


def window_values(samples, start, width=WINDOW_S):
    end = start + width
    selected = [(t, values[0]) for t, _, values in samples if start <= t < end]
    if len(selected) < BARO_MIN_WINDOW_ROWS:
        raise ValueError("insufficient barometer rows in admissible fixed window")
    if selected[0][0] - start > BARO_MAX_GAP_S + 1e-12 or end - selected[-1][0] > BARO_MAX_GAP_S + 1e-12:
        raise ValueError("barometer edge coverage exceeds 40 ms")
    return selected


def median_over_window_range(samples, start_interval):
    value_medians, time_medians = [], []
    for start in candidate_window_starts(samples, *start_interval):
        selected = window_values(samples, start)
        value_medians.append(median(value for _, value in selected))
        time_medians.append(median(t for t, _ in selected))
    return (min(value_medians), max(value_medians)), (min(time_medians), max(time_medians))


def barometer_prediction(barometer, start, end, prep):
    # Include declared sensor timing uncertainty in the possible device-window position.
    te = prep["bounds"]["sensor_time_error_s"]
    before_starts = (start[0] - WINDOW_S - te, start[1] - WINDOW_S + te)
    after_starts = (end[0] + POST_DELAY_S - te, end[1] + POST_DELAY_S + te)
    before, before_times = median_over_window_range(barometer, before_starts)
    after, after_times = median_over_window_range(barometer, after_starts)
    # Preserve sampling-grid timing instead of assuming nominal window centers.
    sep = (after_times[0] - before_times[1], after_times[1] - before_times[0])
    slope = prep["barometer_drift_m_per_s"]
    drift = sorted((slope * sep[0], slope * sep[1]))
    error = prep["bounds"]["barometer_displacement_error_m"]
    predicted = (after[0] - before[1] - drift[1] - error,
                 after[1] - before[0] - drift[0] + error)
    return {"before_median_m": list(before), "after_median_m": list(after),
            "before_median_time_s": list(before_times), "after_median_time_s": list(after_times),
            "drift_m": drift, "delta_z_interval_m": list(predicted),
            "declared_unmodelled_error_m": error}


def projected_samples(imu, lo, hi, prep):
    sf_error = prep["bounds"]["specific_force_error_g"]
    tilt = prep["bounds"]["max_body_z_tilt_deg"]
    zero_lo, zero_hi = prep["zero_specific_force_interval_g"]
    zero_nom = prep["nominal_zero_specific_force_g"]
    values = []
    for t, _, raw in imu:
        if lo - 0.06 <= t <= hi + 0.06:
            ax, ay, az = raw
            nominal = (az - zero_nom) * G
            flo, fhi = vertical_force_interval_g(ax, ay, az, sf_error, tilt)
            values.append((t, nominal, (flo - zero_hi) * G, (fhi - zero_lo) * G))
    if len(values) < 2:
        raise ValueError("insufficient IMU event coverage")
    for left, right in zip(values, values[1:]):
        if right[0] - left[0] > IMU_MAX_GAP_S + 1e-12:
            raise ValueError("IMU gap over 50 ms")
    return values


def interpolate_projected(samples, t):
    if t < samples[0][0] or t > samples[-1][0]:
        raise ValueError("event boundary outside IMU coverage")
    for left, right in zip(samples, samples[1:]):
        if left[0] <= t <= right[0]:
            if t == left[0]:
                return left
            if t == right[0]:
                return right
            w = (t - left[0]) / (right[0] - left[0])
            return (t, *(left[j] + w * (right[j] - left[j]) for j in range(1, 4)))
    raise ValueError("event boundary lacks IMU bracket")


def integrate_projected(samples, start, end, prep):
    if end <= start:
        raise ValueError("positive event duration required")
    points = [interpolate_projected(samples, start)]
    points.extend(row for row in samples if start < row[0] < end)
    points.append(interpolate_projected(samples, end))
    v0 = prep["bounds"]["initial_velocity_error_m_s"]
    v = (-v0, v0)
    z = (0.0, 0.0)
    vn, zn = 0.0, 0.0
    for left, right in zip(points, points[1:]):
        dt = right[0] - left[0]
        an = 0.5 * (left[1] + right[1])
        alo = 0.5 * (left[2] + right[2])
        ahi = 0.5 * (left[3] + right[3])
        zn += vn * dt + 0.5 * an * dt * dt
        vn += an * dt
        z = (z[0] + v[0] * dt + 0.5 * alo * dt * dt,
             z[1] + v[1] * dt + 0.5 * ahi * dt * dt)
        v = (v[0] + alo * dt, v[1] + ahi * dt)
    return zn, z, points


def imu_segment(imu, start, end, prep):
    te = prep["bounds"]["sensor_time_error_s"]
    outer_start, outer_end = start[0] - te, end[1] + te
    samples = projected_samples(imu, outer_start, outer_end, prep)
    anchor_start, anchor_end = start[0], end[0]
    nominal, bounded, _points = integrate_projected(samples, anchor_start, anchor_end, prep)

    # The replay anchor is the lower supplied endpoint, not a hidden midpoint.
    # Bound any other admissible event/sensor timing by a deterministic
    # sensitivity envelope. This is conditional on the declared timing/error
    # bounds and does not turn log time into sensor producer time.
    v0 = prep["bounds"]["initial_velocity_error_m_s"]
    max_acc = max(max(abs(row[2]), abs(row[3])) for row in samples)
    duration_max = outer_end - outer_start
    start_shift = (start[1] - start[0]) + te
    end_shift = (end[1] - end[0]) + te
    shift = start_shift + end_shift
    timing_error = v0 * shift + max_acc * duration_max * shift + 0.5 * max_acc * shift * shift
    bounded = [bounded[0] - timing_error, bounded[1] + timing_error]
    return {"anchor_device_s": [anchor_start, anchor_end],
            "admissible_device_s": [outer_start, outer_end],
            "nominal_delta_z_m": nominal,
            "delta_z_interval_m": bounded,
            "timing_sensitivity_error_m": timing_error,
            "max_abs_vertical_accel_bound_m_s2": max_acc,
            "initial_velocity_interval_m_s": [-v0, v0]}


def intersect(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return None if lo > hi else [lo, hi]


def analyze(barometer, imu, spec, reference):
    if spec.get("schema") != "webeeblocks.x3.vertical-predictor-input.v1":
        raise ValueError("unknown vertical-predictor schema")
    if reference.get("schema") != "webeeblocks.x3.metric-reference-result.v1" or reference.get("status") != "COMPUTED_CONDITIONAL":
        raise ValueError("exact conditional metric-reference result required")
    prep = preparation(barometer, imu, spec, reference)
    events = reference.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("metric reference must contain at least one replay event")
    results, seen = [], set()
    previous_end = prep["guaranteed_calibration_s"][1]
    for event in events:
        identifier, kind = event["id"], event["kind"]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen or kind not in KINDS:
            raise ValueError("unique event ID and known descriptive kind required")
        seen.add(identifier)
        start = interval(event["start_device_s"], "event start")
        end = interval(event["end_device_s"], "event end")
        if start[0] < previous_end + 2 or end[0] <= start[1]:
            raise ValueError("events must remain ordered with two-second plateaus")
        previous_end = end[1]
        baro = barometer_prediction(barometer, start, end, prep)
        inertial = imu_segment(imu, start, end, prep)
        common = intersect(baro["delta_z_interval_m"], inertial["delta_z_interval_m"])
        latency = (POST_DELAY_S + WINDOW_S
                   + 2 * prep["bounds"]["sensor_time_error_s"]
                   + prep["bounds"]["delivery_latency_error_s"])
        width = None if common is None else common[1] - common[0]
        results.append({"id": identifier, "kind": kind,
                        "start_device_s": list(start), "end_device_s": list(end),
                        "barometer": baro, "inertial": inertial,
                        "conditional_delta_z_interval_m": common,
                        "consistency": "OVERLAP" if common is not None else "DISJOINT",
                        "conditional_uncertainty_width_m": width,
                        "conditional_half_width_m": None if width is None else width / 2,
                        "conditional_latency_upper_s": latency,
                        "conditional_half_width_within_5cm": common is not None and width / 2 <= 0.05 + 1e-12,
                        "conditional_latency_within_1s": latency <= 1.0 + 1e-12})
    return {"schema": "webeeblocks.x3.vertical-predictor-result.v1",
            "status": "COMPUTED_CONDITIONAL", "preparation": prep, "events": results,
            "declared_bounds_validated": False, "sensor_producer_timing_validated": False,
            "physical_reference_validated": bool(reference.get("physical_reference_validated", False)),
            "affine_clock_validated": bool(reference.get("affine_clock_validated", False)),
            "independent_displacement_verdict": "UNPROVEN",
            "physical_verdict": None,
            "scope": "offline barometer+raw-accelerometer vehicle-Z replay; ToF, estimator attitude/state and S3 excluded",
            "limits": ["Declared deterministic error/tilt bounds are inputs, not measurements or confidence intervals.",
                       "Crazyflie log timestamps are not per-sensor producer timestamps.",
                       "The 5 cm half-width and 1 s latency booleans are conditional budget checks, never PASS/FAIL.",
                       "No terrain delta, XY behavior, motorized behavior or flight authority is established."]}


def safe_source(root, source):
    relative = Path(source["path"])
    target = (root / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(root) or not target.is_file():
        raise ValueError("source must stay inside the specification directory")
    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if not isinstance(source.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) or digest != source["sha256"]:
        raise ValueError("source digest mismatch")
    return raw, digest


def run(path: Path):
    raw_spec = path.read_bytes()
    spec = json.loads(raw_spec)
    root = path.parent.resolve()
    sources = spec["sources"]
    if set(sources) != {"barometer", "imu", "metric_reference"}:
        raise ValueError("exact barometer/imu/metric_reference source set required; pose/ToF/estimator sources are forbidden")
    loaded = {name: safe_source(root, sources[name]) for name in sources}
    barometer, imu = read_sources(loaded["barometer"][0], loaded["imu"][0])
    reference = json.loads(loaded["metric_reference"][0])
    reference_sources = reference.get("input_provenance", {}).get("sources", [])
    bound_baro = [item for item in reference_sources
                  if isinstance(item, dict) and item.get("kind") == "barometer-capture"]
    if len(bound_baro) != 1 or bound_baro[0].get("sha256") != loaded["barometer"][1]:
        raise ValueError("metric reference is not bound to the supplied barometer capture")
    result = analyze(barometer, imu, spec, reference)
    result["input_provenance"] = {"specification_sha256": hashlib.sha256(raw_spec).hexdigest(),
                                  "sources": {name: digest for name, (_, digest) in loaded.items()},
                                  "predictor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
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