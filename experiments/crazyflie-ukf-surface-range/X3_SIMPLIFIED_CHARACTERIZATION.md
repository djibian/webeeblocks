# X3 simplified props-off characterization pre-registration

Status: **support-only / Lab-only / no checkpoint request**.

This document implements the current #70 owner scientific direction after the
independent X3 review. It pre-registers the smallest next information experiment;
it does not enable a trusted human-test profile, request `TEST_REQUIRED`, flash a
new firmware image, validate world-altitude control, or authorize motorized
flight.

## Scientific question

The next experiment no longer tries to prove a universal deterministic error
budget for every IMU/barometer timing sub-link before collecting data. It asks a
narrower empirical question:

> On the exact retained #251 props-off firmware/configuration, can the complete
> IMU + barometer information path estimate vehicle vertical displacement well
> enough, in a bounded classroom-like test domain, to separate vehicle motion
> from a change in the local surface below the Crazyflie?

The intended decomposition remains

`delta_h = delta_z_independent - delta_clearance`

where `delta_z_independent` is derived without using downward ToF, S3 state,
UKF Z/VZ or other suspect surface-relative estimator outputs. Downward range and
estimator diagnostics remain recorded only as comparison/diagnostic evidence.

Characterization produces **empirical envelopes for the tested domain**. It does
not validate the frozen predictor's existing deterministic-bound flags and does
not create a flight acceptance claim.

## Exact physical artifact boundary

Use the unchanged #251 artifact unless preparation discovers a concrete
acquisition defect that makes the required observations unavailable:

- WebeeBlocks source/request target:
  `6562ad827bf0c8bf2c9b609edad36f3e15652133`;
- exact `cf2.bin` SHA-256:
  `67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738`;
- `stabilizer.estimator=3`;
- `ukf.qualityGateTof=20`;
- `ukf.baroNoise=6.25`;
- `ukf.surfaceOffsetS3=1`;
- props removed throughout.

No estimator threshold/persistence tuning, no `qualityGateTof` or `baroNoise`
sweep, no `rangeUp` fusion, no Runtime/controller change and no motorized action
belongs to this experiment. The integrated pre-LPF observer is not required merely
to establish independence from suspect ToF. New firmware content is eligible only
if preparation proves one specific missing acquisition signal, and then it must be
logging-only, minimal and separately identified.

## Raw signals to retain

The existing `capture_independent_inputs.py` path is the default acquisition
closure. Retain every row, including startup and incomplete rows, for:

- continuous barometer altitude/pressure/temperature;
- `acc.x/y/z` and `gyro.x/y/z`;
- device log timestamps and host monotonic receipt times;
- downward range;
- roll/pitch;
- diagnostic UKF Z/VZ;
- `stabilizer.intToOut`;
- S3 state/reason/offset/barometer-delta/local-Flow/late-eligibility diagnostics.

Only the barometer + IMU path may contribute to the independent vehicle-Z
estimate. Downward range, UKF/S3 outputs and `intToOut` cannot be used to tune or
correct that estimate after outcomes are visible.

The pinned `usecTimestamp()` 84/85 rate defect remains relevant only to quantities
actually expressed on that TIM7 clock. Do not apply the 85/84 correction to the
FreeRTOS-based wireless log timestamp or host clock. The unresolved BMI088
INT2/INT3 provenance remains recorded as `UNPROVEN`, but resolving it is not a
prerequisite to this empirical characterization unless a later claim explicitly
depends on producer-time semantics.

## Independent metric/time reference

Before outcome data are interpreted, retain one Controller-readable independent
reference with explicit uncertainty for:

- vehicle world-Z before/after each event;
- local surface height before/after each event;
- at least two synchronization anchors bracketing every interpreted event set.

The preferred support path is the existing `METRIC_REFERENCE.md` schema with
hash-bound CSV/TXT/JSON witnesses representable by the integrated evidence
publication profile. A measured guide plus independently recorded metric/time
observations is sufficient if its uncertainty and exact observation locators are
retained. A camera is optional, not required. If visual bytes are used, a reviewed
canonical evidence profile capable of retaining those exact bytes must exist
before the checkpoint; a browser attachment alone is not canonical evidence.

Reference uncertainty is part of every comparison. UKF Z/VZ, S3 state, a
`recording-ready.json` receipt time or an arbitrary paired host timestamp is not
an independent metric/time reference.

## Pre-registered scenario matrix

All retained trials are published; there is no best-trace selection. Use a
stationary calibration segment of at least 30 s before interpreted events.
Where practical, retain both movement signs.

| Scenario | Reference condition | Discriminating purpose |
| --- | --- | --- |
| stationary | `delta_z = 0`, `delta_h = 0` within reference uncertainty | characterize drift/noise without motion or terrain change |
| terrain-only | `delta_z ~= 0`, non-zero `delta_h` | require independent vehicle-Z to remain near zero while clearance changes |
| true vertical | non-zero `delta_z`, `delta_h ~= 0`; choose magnitude so `delta_clearance` is comparable to terrain-only | test that vehicle motion is not misread as terrain |
| mixed | both `delta_z` and `delta_h` non-zero, including one case with `delta_z ~= delta_h` so clearance changes little | falsify a method that relies on clearance change alone |

The physical geometry, guide/reference values and their uncertainties must be
recorded before the corresponding confirmation outcomes are examined.

## Characterization then untouched confirmation

The experiment has two distinct phases.

### 1. Characterization

Use a predeclared subset of complete trials to measure the observable error of the
**complete** IMU/barometer information path against the independent reference.
This phase may determine empirical processing choices/envelopes only within the
predeclared family below. Every trial used for characterization remains published.

The candidate processing family is deliberately small:

1. convert accelerometer units and remove gravity using the retained attitude
   information required by the already frozen vertical calculation;
2. integrate the resulting vertical specific force over the retained device-time
   sequence without using ToF/UKF/S3 values;
3. use barometer pressure/altitude only through a fixed causal or fixed-window
   displacement correction selected during characterization;
4. compare predicted `delta_z` with the external reference over fixed before/after
   windows;
5. retain signed error, absolute error, event duration and data-quality/gap facts
   for every trial.

Characterization may select window lengths and empirical error envelopes from its
own designated trials. It may not tune firmware, alter the scenario labels,
exclude unfavorable retained trials, or use the later confirmation outcomes.

### 2. Freeze

Before any confirmation outcome is processed, durably freeze:

- the exact processing implementation/digest;
- all window lengths and event-selection rules;
- calibration constants and empirical error envelopes derived from the
  characterization subset;
- the exact list/digests of characterization versus confirmation raw files;
- reference uncertainty treatment;
- any data-quality rejection rule.

A rejected/incomplete trial remains visible and its rejection reason is retained.

### 3. Confirmation

Apply the frozen processing unchanged to the separately retained confirmation
trials. No post-hoc retuning, window movement, sign-dependent rule change or trace
selection is allowed.

The existing frozen deterministic predictor may also be run as a **conditional
confirmation tool**, but its flags remain truthful: characterization does not turn
`declared_bounds_validated`, `sensor_producer_timing_validated` or the physical
verdict into PASS.

## Predeclared falsification targets

Where the independent reference and clock envelopes make the comparison
meaningful, retain the existing #70 scientific targets:

- absolute vehicle displacement error at most **0.05 m** for the interpreted
  event displacement;
- useful convergence/recovery no later than **1.0 s** after the reference event
  end.

These are bounded scientific falsification targets, not firmware classifier
thresholds and not flight-acceptance criteria. Evaluate them with reference and
timing uncertainty included. If the admissible uncertainty interval crosses a
target, the result is `UNPROVEN`, not PASS. A valid confirmation counterexample
outside the target refutes the tested candidate in that characterized domain.

No characterization result, even favorable, authorizes motorized testing.

## Evidence and decision outputs

A future trusted checkpoint must durably publish, through the existing evidence
path:

- all raw capture files and immutable capture metadata;
- independent reference inputs/witnesses and exact source hashes;
- characterization/confirmation membership before confirmation analysis;
- frozen processing source/digest and configuration;
- derived characterization envelopes;
- untouched confirmation results;
- data-quality/rejection records;
- the exact checkpoint/request/tested Git identity.

The checkpoint's human PASS/FAIL concerns completion/usability of the requested
information capture, not proof that a terrain classifier or flight capability is
ready.

The subsequent #70 scientific decision must be exactly one of:

1. continue toward an independent continuous vertical estimate / explicit terrain
   representation because confirmation supports the information path in the
   tested domain;
2. reject the tested information-path candidate in that domain because a valid
   confirmation counterexample falsifies it; or
3. record one concrete missing information source if the evidence remains
   `UNPROVEN` for a specific identifiable reason.

## Checkpoint boundary

This pre-registration is deliberately non-notifying. A trusted
`x3-independent-props-off` checkpoint profile may be enabled only after the exact
artifact/support bundle and executable procedure are reviewed and deterministic
machine preparation passes. The ordinary human-checkpoint mechanism must also
observe its global single-open-request and fingerprint-deduplication rules.

Until then: no `CHECKPOINT_REQUEST`, no `TEST_REQUIRED`, no firmware flash, no
estimator/controller change and no motorized test.