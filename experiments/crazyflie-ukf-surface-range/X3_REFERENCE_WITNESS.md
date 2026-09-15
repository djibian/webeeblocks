# X3 independent measured-guide reference witness

This document selects the concrete independent metric/time witness procedure for
the simplified #70 X3 props-off characterization. It is machine preparation only:
it does **not** request `TEST_REQUIRED`, authorize flashing, open Crazyradio, change
parameters, claim a physical result, or authorize motorized testing.

The selected witness is deliberately representable by the existing
`physical-csv-text-v1` evidence profile. Its canonical raw external witness is a
CSV of direct measured-guide / independent-clock observation intervals plus
bounded TXT/JSON metadata. No video or browser-only attachment is required for
this procedure.

## 1. Independent apparatus and datum

Use, and identify in retained metadata:

- one rigid metric guide/frame fixed to the room/world frame and readable at every
  predeclared vehicle plateau position; if more than one guide segment is needed,
  survey their common world datum before collection and retain that survey;
- one physical length standard or the same surveyed guide/frame to measure the
  relevant floor and raised-surface heights from that same world datum;
- one independent elapsed-time display/stopwatch whose clock is not the
  Crazyflie log clock, host monotonic clock, UKF/S3 state, downward ToF or the
  predictor under test;
- the exact Crazyflie body reference feature used for every guide reading.

The guide/frame must not support, constrain or drive the Crazyflie's vertical
motion. The props remain removed. The vehicle is hand-carried as required by the
pre-registration. Use separate manipulator and observer/recorder roles whenever
one person cannot manipulate the Crazyflie and read the guide/clock without
changing the apparatus or losing the declared observation bound; retain those
roles in metadata.

Before characterization, record the guide resolution, the surface-height
measurement resolution, the independent-clock display resolution, and a
predeclared conservative human reading/reaction allowance. These quantities are
uncertainty inputs; they are never narrowed after seeing a trial outcome.

## 2. Canonical raw witness CSV

Create `reference-witness.csv` from the packaged
`X3_REFERENCE_WITNESS_TEMPLATE.csv`. Keep its header and column order exactly:

`row_id,row_kind,scenario_id,trial_id,reference_time_low_s,reference_time_high_s,vehicle_z_low_m,vehicle_z_high_m,surface_z_low_m,surface_z_high_m,note`

The file is append-only during collection and is retained exactly as collected.
Rows are direct observation notes, not derived PASS/FAIL values. Empty metric
fields are allowed only for synchronization rows that do not assert vehicle or
surface height.

Required row kinds are:

- `sync`: an externally timed synchronization gesture, outside analyzed motion
  windows;
- `calibration_start` / `calibration_end`: bounds for the stationary calibration
  interval;
- `plateau_before` / `plateau_after`: independent guide/surface intervals that
  support the before/after metric values for an event;
- `event_start` / `event_end`: independent-clock bounds for the corresponding
  transition.

Every non-sync row has a unique `row_id`, scenario/trial identity and a specific
note sufficient to locate the physical observation. Record intervals
`[low, high]`; a point value is allowed only when the apparatus and declared
resolution genuinely justify identical endpoints. Uncertainty is represented by
widening the interval, never by storing a best estimate and discarding the bound.

At minimum, each retained trial has enough rows to support its before plateau,
transition start/end and after plateau. Retain every validly started trial as
required by `X3_CHARACTERIZATION_PREREGISTRATION.md`; do not delete unfavorable
rows or select a best trace.

## 3. Synchronizing the external clock to Crazyflie log time

The external stopwatch is independent, so the evidence needs physical events
observable in both clock domains. Use two or more synchronization gestures that
bracket the complete reference-time domain consumed by `metric_reference.py`:
one after raw capture has started but **before `calibration_start`**, and one after
the last interpreted transition while recording is still active. More anchors may
be retained. The first gesture is a clock anchor only; stationary calibration
starts after that gesture and remains entirely inside the bracketing sync domain.

For each sync gesture:

1. with props removed and outside an analyzed plateau/transition, make one short,
   deliberate angular hand gesture that is clearly observable in the raw
   `gyro.x/y/z` capture;
2. observe the same gesture on the independent stopwatch and record a `sync` row
   with a conservative reference-time interval including display resolution and
   the predeclared human observation/reaction allowance;
3. after collection, identify the bracketing raw `imu.csv` rows that contain the
   same gesture; do not use `stateEstimate.*`, S3 or downward range to choose the
   rows;
4. convert those bracketing Crazyflie log timestamps into the exact elapsed-device
   coordinate required by `metric_reference.py`: unwrap the shared 24-bit log
   timestamp as already done by the frozen pressure parser and subtract the first
   retained `barometer.csv` log timestamp, so `device_s=0` is exactly
   `first-barometer-log-row`;
5. keep the witness locator for the anchor as the exact `reference-witness.csv`
   sync row plus the exact `imu.csv` row range used to bound the device interval.

The raw `imu.csv` file remains part of the complete published capture and is
therefore hash-bound by the trusted raw-evidence publication bundle even though
the existing metric-reference input schema names only the barometer capture and
the external-reference file as source kinds.

The gesture-detection rule used to identify the IMU row range is chosen from
calibration only and frozen before untouched confirmation. It may use raw gyro
magnitude/sign and contiguous-sample requirements, but it must not use UKF/S3,
downward ToF, predictor output or confirmation outcomes.

Host receipt time may be used only as an integrity/cross-check already retained by
the capture; it is not substituted for device log time. An arbitrary pairing of
a stopwatch reading with a host receipt timestamp is not a valid clock anchor.

If the sync gestures are ambiguous, do not extrapolate or choose an optimistic
row: widen the device/reference interval if the retained evidence supports a
bound, otherwise the affected comparison is `UNPROVEN`.

## 4. Scenario observations

Use the scenario set and trial-retention rule from the pre-registration:

- stationary (`delta z = 0`, `delta h = 0`);
- terrain-only (approximately constant vehicle world Z, non-zero surface change);
- true vertical vehicle motion with comparable local-clearance change;
- mixed motion, including approximately `delta z = delta h`;
- both signs where practical.

For vehicle-Z plateaus, read the same body reference feature against the surveyed
world guide/frame before and after the transition and record conservative metric
intervals. For surface-height plateaus, measure the local surface from the same
world datum and record conservative intervals. These measurements are independent
of `stateEstimate.z`, S3 state, downward range and the predictor.

The guide is a discrete before/after metric reference, not a continuous ground
truth trajectory. Therefore this witness supports the pre-registered displacement
and transition-time questions only where its retained intervals and clock anchors
cover them. It must not be promoted into an unobserved continuous-Z claim.

## 5. Transformation into `metric-reference-input.v1`

After collection, retain the raw CSV unchanged and create the metric-reference
JSON beside it. The transformation is mechanical:

- list the continuous `barometer.csv` capture as source kind
  `barometer-capture` and `reference-witness.csv` as source kind
  `external-metric-reference`, each with its exact SHA-256;
- set `clock.model=affine`,
  `clock.device_origin=first-barometer-log-row`, and point
  `clock.barometer_source` at the exact continuous capture;
- for every `sync` row, use its reference-time interval and the elapsed-device
  interval derived from the exact bracketing IMU rows under section 3 to create
  one clock anchor; the witness locator names both exact row ranges;
- derive calibration start/end only from the corresponding retained witness rows;
- derive event start/end from `event_start` / `event_end` rows;
- derive `z_before_m` / `z_after_m` from the corresponding vehicle guide plateau
  intervals and `surface_before_m` / `surface_after_m` from the corresponding
  surface plateau intervals;
- the event witness locator lists the exact raw reference rows supporting those
  four metric intervals and transition-time intervals.

Do not midpoint intervals before invoking `metric_reference.py`. Do not narrow an
interval because the Crazyflie capture or predictor suggests a preferred value.
The existing processor must continue to reject inconsistent clocks, extrapolation,
missing coverage or changed source digests.

The produced JSON is an interpretation/specification; the CSV is the canonical
external observation witness. Retain both, plus the processor output, with the raw
Crazyflie capture through the trusted evidence publication path.

## 6. Calibration / freeze / confirmation boundary

Characterization may use calibration data to freeze:

- guide-reading convention and uncertainty calculation;
- human timing allowance;
- synchronization-gesture detector and row-bracketing rule;
- exact CSV-to-metric-reference transformation rule;
- all other processing/envelope choices permitted by the pre-registration.

Before untouched confirmation begins, durably freeze those choices and their
implementation/configuration digests. Confirmation rows are then collected and
processed without outcome-informed changes. If the witness or synchronization
uncertainty crosses the 5 cm or 1 s falsification quantity, the relevant result is
`UNPROVEN`, not PASS.

## 7. Durable publication boundary

The exact checkpoint evidence bundle must retain at least:

- the complete raw Crazyflie capture directory, including the exact IMU rows used
  for synchronization;
- `reference-witness.csv` unchanged from collection;
- metadata describing the guide/frame survey and datum, body reference,
  manipulator/observer roles, independent clock and predeclared
  resolutions/uncertainties;
- the exact metric-reference input JSON and output JSON;
- the frozen processing/reference/uncertainty configuration used for the phase;
- exact artifact/runtime/Git provenance required by the checkpoint mechanism.

All of these are CSV/TXT/JSON/LOG and therefore fit the already-reviewed
`physical-csv-text-v1` publication profile. No new evidence-profile capability is
needed for this selected procedure.

A future `x3-independent-props-off` checkpoint remains eligible only through the
trusted checkpoint mechanism when the repository-wide TEST_REQUIRED slot is free
and the complete exact procedure/artifact has been prepared. This document alone
creates no checkpoint and no physical verdict.

Refs: #70, `X3_CHARACTERIZATION_PREREGISTRATION.md`, `X3_CHECKPOINT_SUPPORT.md`,
`METRIC_REFERENCE.md`.
