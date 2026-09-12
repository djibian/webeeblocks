# Frozen conditional X3 vertical replay predictor

This is the next bounded offline component for #70 after the integrated input
collector, frozen pressure probe and conditional metric-reference processor. It
answers a narrower question than the firmware problem: **given pre-declared
error/timing bounds, do the raw barometer and raw accelerometer admit one
consistent vehicle vertical-displacement interval?** It does not classify
terrain, change the Crazyflie estimator, or establish physical flight capability.

The predictor is intentionally independent of the suspect ToF path. Its file
entry point accepts exactly three retained sources: the continuous barometer CSV,
the continuous IMU CSV and the exact `metric_reference.py` result. Pose, range,
`stateEstimate.z`, `stateEstimate.vz`, S3 diagnostics and estimator attitude are
not predictor inputs. The metric-reference result is used for calibration/event
time intervals only; the predictor does not use its reference Δz/Δh values to
construct its sensor prediction.

The pinned #251 capture format comes from Crazyflie firmware 2026.08
`54f31e243a0b28b67efef5ba20dbb6d9890a5478`. In that source `acc.x/y/z` are
body-frame acceleration in G and `baro.asl` is altitude in metres. The collector
still retains gyroscope and pose diagnostics, but this smallest replay does not
silently turn estimator attitude into independent evidence. Instead it carries a
pre-declared bound on the angle between body Z and world vertical.

## Frozen model

The input schema is `webeeblocks.x3.vertical-predictor-input.v1`:

```json
{
  "schema": "webeeblocks.x3.vertical-predictor-input.v1",
  "sources": {
    "barometer": {"path": "barometer.csv", "sha256": "<64 hex>"},
    "imu": {"path": "imu.csv", "sha256": "<64 hex>"},
    "metric_reference": {"path": "metric-reference.json", "sha256": "<64 hex>"}
  },
  "declared_bounds": {
    "specific_force_error_g": 0.0,
    "max_body_z_tilt_deg": 0.0,
    "initial_velocity_error_m_s": 0.0,
    "barometer_displacement_error_m": 0.0,
    "sensor_time_error_s": 0.0,
    "delivery_latency_error_s": 0.0
  }
}
```

The zero values above are syntax examples, **not recommended or validated
physical bounds**. Every bound must be justified and frozen before a confirmation
capture; event outcomes must never be used to narrow it. The result always keeps
`declared_bounds_validated:false` and `sensor_producer_timing_validated:false`.
A controller or human verdict must validate the bound provenance separately.

The supplied metric-reference result must be
`webeeblocks.x3.metric-reference-result.v1 / COMPUTED_CONDITIONAL`, and its
recorded barometer-capture digest must match the exact supplied barometer CSV.
This prevents combining event timing from one capture with sensor data from
another. Calibration uses only the device-time interval guaranteed to be inside
the reference calibration for every admissible clock mapping; at least 30 s must
remain.

### Barometer arm

For each event, the B− and B+ windows remain exactly those frozen in #70:
B− is 0.5 s immediately before event start and B+ is 0.5 s beginning 0.25 s
after event end. The allowed start/end intervals from the metric-reference result,
plus the declared sensor-time error, are preserved. The implementation enumerates
every discrete median regime induced by the logged samples, including both sides
of sample/window boundaries; it never substitutes an interval midpoint.

A linear pressure-altitude drift is fitted only on the guaranteed prior
calibration. Drift correction uses the observed median-sample-time interval, not
nominal window centres. `barometer_displacement_error_m` is an external
deterministic allowance that must cover everything the finite calibration fit
does not prove (drift-model error, pressure dynamics, sampling/producer effects,
etc.). The predictor does not derive a confidence level from calibration row
count or residual extrema.

### Inertial arm

The nominal diagnostic trace subtracts the calibration median from raw `acc.z`.
The bounded trace does not assume the vehicle is exactly level. For each raw
accelerometer sample it encloses world-up specific force over a cone whose half
angle is `max_body_z_tilt_deg`, while adding the declared per-axis
`specific_force_error_g`. The calibration-zero interval is subtracted from the
event interval, then the resulting acceleration envelope is integrated from an
initial velocity interval
`[-initial_velocity_error_m_s, +initial_velocity_error_m_s]`.

For uncertain event/log timing, the integration anchor is the **lower supplied
endpoint**, never a hidden midpoint. A conservative timing-sensitivity allowance
covers the remaining start/end interval and declared sensor-time error using the
maximum acceleration envelope over the admissible span. This is conditional
arithmetic, not proof that Crazyflie log timestamps are sensor-producer times.

This deliberately does not integrate estimator attitude or `stateEstimate.vz`.
A later candidate may use a more informative raw-gyro/attitude model only if its
producer timing, bias and coordinate assumptions are themselves bounded without
reintroducing the ToF-contaminated state.

### Combination and latency

If the deterministic barometer and inertial intervals overlap, their intersection
is retained as `conditional_delta_z_interval_m`. If they are disjoint, the result
is `DISJOINT` and no fused interval is manufactured. No bound is widened or tuned
from the event outcome.

The result reports two preregistered budget checks only:

- `conditional_half_width_within_5cm`: the overlapping interval has half-width at
  most 5 cm, conditional on all declared bounds being valid;
- `conditional_latency_within_1s`: the fixed B+ endpoint (0.75 s after the
  transition) plus declared timing/delivery allowances is at most 1 s.

These are **not** physical PASS/FAIL. In particular, interval half-width is not an
error measurement against the external metric reference, and the latency is not
validated end-to-end producer latency. Every output remains
`independent_displacement_verdict:UNPROVEN` and `physical_verdict:null`.

## Execution and checks

```sh
python3 experiments/crazyflie-ukf-surface-range/test_frozen_vertical_predictor.py
python3 experiments/crazyflie-ukf-surface-range/frozen_vertical_predictor.py \
  predictor-input.json --output predictor-result.json
```

The file entry point hash-binds all three inputs, refuses path escape and existing
output overwrite, aligns IMU to the first barometer Crazyflie log timestamp, and
fails closed on malformed/non-finite data, clock reversal, barometer gaps over
40 ms or IMU gaps over 50 ms. The synthetic controls verify signed replay,
conditional-bound widening, sensor disagreement, interval timing without
midpoint selection, source/digest binding and rejection of optimistic/invalid
inputs. They are component tests, not physical evidence.

## Remaining boundary

This component freezes the sensor predictor mechanics but does **not** validate
its declared bounds, physical-reference annotations, affine clock assumption or
sensor-producer timing. It also does not estimate terrain Δh, validate the mixed
case against a physical reference, publish raw physical evidence, prepare a human
checkpoint, flash firmware, retune #251, alter Runtime/controller behavior or
authorize motorized testing.

Before a new `TEST_REQUIRED` can be justified, the exact props-off support must
bind this predictor to the retained acquisition/reference inputs, pre-register
and justify its bound values, preserve the raw outputs durably, and make the
physical reference/timing observations executable under the current `AGENTS.md`.
