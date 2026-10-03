#!/usr/bin/env python3
"""Read-only X3 estimator-health gate shared by preparation and acquisition.

The gate is deliberately broad. It rejects only an estimator that is already
non-finite or grossly incompatible with the stationary indoor hand-carried X3
test envelope. It is not a scientific acceptance criterion and must never be
retuned from characterization outcomes.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any

HEALTH_PERIOD_MS = 20
HEALTH_VARIABLES = (
    "stabilizer.roll",
    "stabilizer.pitch",
    "stateEstimate.z",
    "stateEstimate.vz",
)
PREPARATION_OBSERVE_SECONDS = 5.0
ACQUISITION_PREFLIGHT_SECONDS = 2.0
LIMITS = {
    "max_abs_roll_deg": 30.0,
    "max_abs_pitch_deg": 30.0,
    "max_abs_z_m": 10.0,
    "max_abs_vz_mps": 0.50,
    "max_z_span_m": 0.50,
}


class EstimatorHealthError(RuntimeError):
    pass


def evaluate_estimator_health(
    samples: list[dict[str, float]],
    *,
    duration_s: float,
) -> dict[str, Any]:
    minimum_samples = max(10, int(duration_s * 20))
    if len(samples) < minimum_samples:
        raise EstimatorHealthError(
            f"estimator health stream incomplete: {len(samples)} samples, "
            f"need at least {minimum_samples}"
        )

    values: dict[str, list[float]] = {name: [] for name in HEALTH_VARIABLES}
    for sample in samples:
        for name in HEALTH_VARIABLES:
            raw = sample.get(name)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise EstimatorHealthError(f"estimator health sample malformed: {name}")
            value = float(raw)
            if not math.isfinite(value):
                raise EstimatorHealthError(f"estimator health sample non-finite: {name}")
            values[name].append(value)

    summary = {
        "status": "HEALTHY",
        "observation_seconds": duration_s,
        "sample_count": len(samples),
        "limits": dict(LIMITS),
        "observed": {
            name: {"min": min(rows), "max": max(rows)}
            for name, rows in values.items()
        },
        "boundary": (
            "broad pre-acquisition sanity gate only; not scientific sufficiency, "
            "not a 5 cm / 1 s acceptance result"
        ),
    }

    roll = values["stabilizer.roll"]
    pitch = values["stabilizer.pitch"]
    z = values["stateEstimate.z"]
    vz = values["stateEstimate.vz"]

    failures = []
    if max(abs(v) for v in roll) > LIMITS["max_abs_roll_deg"]:
        failures.append("roll outside stationary preparation envelope")
    if max(abs(v) for v in pitch) > LIMITS["max_abs_pitch_deg"]:
        failures.append("pitch outside stationary preparation envelope")
    if max(abs(v) for v in z) > LIMITS["max_abs_z_m"]:
        failures.append("stateEstimate.z grossly divergent")
    if max(abs(v) for v in vz) > LIMITS["max_abs_vz_mps"]:
        failures.append("stateEstimate.vz incompatible with stationary preparation")
    if max(z) - min(z) > LIMITS["max_z_span_m"]:
        failures.append("stateEstimate.z drifted excessively during stationary gate")

    if failures:
        raise EstimatorHealthError("; ".join(failures))
    return summary


def observe_estimator_health(
    cf: object,
    log_config_class: object,
    *,
    duration_s: float,
) -> dict[str, Any]:
    samples: list[dict[str, float]] = []
    errors: list[str] = []
    lock = threading.Lock()

    config = log_config_class("X3_ESTIMATOR_HEALTH", HEALTH_PERIOD_MS)
    for name in HEALTH_VARIABLES:
        config.add_variable(name, "float")

    def received(_timestamp: int, data: dict[str, object], _config: object) -> None:
        with lock:
            samples.append({name: data.get(name) for name in HEALTH_VARIABLES})

    def failed(_config: object, message: str) -> None:
        with lock:
            errors.append(str(message))

    cf.log.add_config(config)
    config.data_received_cb.add_callback(received)
    config.error_cb.add_callback(failed)

    started = False
    try:
        config.start()
        started = True
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            with lock:
                if errors:
                    raise EstimatorHealthError(
                        "estimator health log failed: " + errors[0]
                    )
            time.sleep(0.02)
    finally:
        if started:
            try:
                config.stop()
            except Exception as exc:
                raise EstimatorHealthError(
                    f"estimator health log stop failed: {exc}"
                ) from exc

    with lock:
        snapshot = list(samples)
        if errors:
            raise EstimatorHealthError("estimator health log failed: " + errors[0])
    return evaluate_estimator_health(snapshot, duration_s=duration_s)


def self_test() -> None:
    good = [
        {
            "stabilizer.roll": 1.0,
            "stabilizer.pitch": -2.0,
            "stateEstimate.z": 0.72 + i * 0.0001,
            "stateEstimate.vz": 0.01,
        }
        for i in range(50)
    ]
    evaluate_estimator_health(good, duration_s=2.0)

    divergent = [dict(row) for row in good]
    divergent[-1]["stateEstimate.z"] = 57.0
    try:
        evaluate_estimator_health(divergent, duration_s=2.0)
    except EstimatorHealthError:
        pass
    else:
        raise AssertionError("grossly divergent estimator must fail closed")

    nonfinite = [dict(row) for row in good]
    nonfinite[-1]["stabilizer.pitch"] = float("nan")
    try:
        evaluate_estimator_health(nonfinite, duration_s=2.0)
    except EstimatorHealthError:
        pass
    else:
        raise AssertionError("non-finite estimator sample must fail closed")

    print("PASS: X3 estimator health gate rejects divergent/non-finite state")


if __name__ == "__main__":
    self_test()
