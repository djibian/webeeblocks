# X3 simplified characterization checkpoint support boundary

This document records the current support boundary for #70 after the owner
scientific decision `X3 VIABLE WITH SIMPLIFICATION`. It does **not** itself request
`TEST_REQUIRED`, authorize flashing, or claim a physical or motorized capability.

The scientific sequence is now:

`pre-register bounded characterization -> props-off characterization against an independent metric/time reference -> freeze observed-domain processing/envelopes -> separate confirmation without post-hoc tuning -> scientific decision`

Empirical characterization and deterministic confirmation are deliberately
separate. The existing frozen X3 predictor remains a valid conditional
confirmation tool, but its fail-closed validation flags are not prerequisites to
collecting the next useful characterization data and are not retroactively
satisfied by empirical results.

## Established support already in the repository

The repository already contains:

- continuous barometer/pressure/temperature and IMU acquisition on exact #251
  firmware (`capture_independent_inputs.py`);
- downward-range and estimator/ToF diagnostics retained for interpretation while
  excluded from the independent vehicle-Z prediction;
- the frozen pressure-window calculation (`frozen_pressure_probe.py`);
- hash-bound conditional external metric-reference processing
  (`metric_reference.py`);
- the frozen barometer/accelerometer vertical replay
  (`frozen_vertical_predictor.py`);
- the logging-only pre-LPF/read-window observer and later provenance diagnostics;
- the generic Git-backed physical-evidence publication path.

Those are support components, not physical proof. In particular they do not by
themselves validate an external reference, a clock model, sensor-producer timing,
tight deterministic error bounds, the 5 cm / 1 s targets, or a terrain/world-Z
capability.

## Physical artifact boundary

Use the unchanged #251 props-off firmware/configuration for the simplified
characterization unless deterministic preparation exposes a concrete acquisition
defect that cannot be closed without logging-only instrumentation:

- firmware/request source:
  `6562ad827bf0c8bf2c9b609edad36f3e15652133`;
- exact `cf2.bin` SHA-256:
  `67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738`;
- `stabilizer.estimator=3`;
- `ukf.qualityGateTof=20`;
- `ukf.baroNoise=6.25`;
- `ukf.surfaceOffsetS3=1`;
- props removed throughout.

No estimator retuning, S3 threshold/persistence tuning, `rangeUp` fusion, full
`z/f/r` expansion, Runtime/controller change or motorized action belongs to this
experiment.

The existing pre-LPF/timing observer does **not** silently replace #251. Exact
BMI088 INT2/INT3 electrical provenance and proof that
`sensorData.interruptTimestamp` is a sensor-production timestamp remain
`UNPROVEN`, but are no longer prerequisites to this characterization unless a
future claim specifically requires those semantics. If characterization
preparation proves that additional acquisition content is indispensable, any new
firmware must be logging-only and minimal, receive a distinct exact identity, and
be reviewed separately rather than repurposing #251.

The pinned-2026.08 `usecTimestamp()` 84/85 scale defect must be handled only for
observations that actually use that clock. It must not be transferred to
FreeRTOS/log timestamps by analogy.

## Existing #251 runtime/capture closure

`tools/physical/run_x3_independent_capture.sh` defines the deterministic local
runner for exact #251. Its support contract remains:

- Linux x86-64 / Python 3.10;
- exact cflib commit `45fdb784c9d13074c42835f3b5ac1d12133bf873`;
- exact cflib source tree `a78cf78d2b4aba51a0fa2b03de0260664b523401`;
- exact `cflib` subtree `750e850390753de14019f0e1f55d4fbc44317699`;
- exact offline wheel closure from `tools/physical/reference_probe_lock.txt`;
- bundled #251 `cf2.bin`, collector, provenance and manifest.

The runner verifies the bundle/runtime closure before acquisition.
`--verify-environment` is hardware-free. Recording requires an explicit Crazyradio
URI, canonical checkpoint URL, exact request SHA, duration and new output
directory, with explicit props-removed and exact-binary-installed confirmations.
It does not flash, write parameters, reset the estimator, issue commander motion,
publish evidence or manufacture a physical verdict.

The integrated collector already retains the minimum characterization information
required by the owner direction: continuous barometer/pressure/temperature,
`acc.xyz`, `gyro.xyz`, Crazyflie log timestamps plus host receipt timing,
downward range, pose and estimator/S3 diagnostics. The latter diagnostics are
context only and must remain excluded from the independent vehicle-Z prediction.

## Characterization does not require deterministic bound closure

The frozen vertical predictor consumes predeclared deterministic error/timing
bounds and must continue to fail closed while those assumptions are unvalidated.
That stronger contract is preserved for any future deterministic-confirmation
claim.

It is **not**, however, a prerequisite to the next props-off characterization to:

- prove exact BMI088 interrupt routing;
- prove a log/interrupt time is sensor-production time;
- establish universal deterministic specific-force, intersample or timing bounds;
- use the pre-LPF observer merely to establish independence from suspect ToF;
- derive hard guarantees from datasheet typical/RMS values or short calibration
  maxima;
- search historical archives again for signals already established as absent;
- tune `qualityGateTof`, `baroNoise`, S3 thresholds or persistence.

The characterization instead measures the observable error of the **complete
available IMU/barometer information path** against an independent external
reference in a declared physical domain. Calibration may be used to freeze
empirical observed-domain processing/envelopes. Those envelopes are not universal
deterministic guarantees and must not set
`declared_bounds_validated:true` or `sensor_producer_timing_validated:true`.

## Independent metric/time reference

The checkpoint evidence must include an independent reference for both vehicle
vertical displacement and surface-height change, with explicit metric and timing
uncertainty. The reference must not be derived from UKF/S3 state, downward ToF or
the predictor under test.

Raw reference witness bytes/rows and their transformation into metric/time values
must be retained and hash-bound through a trusted evidence path. The witness must
contain sufficient clock anchors to align interpreted events while preserving the
synchronization uncertainty.

If the selected reference cannot support an uncertainty interval narrow enough to
interpret a predeclared target, the result is `UNPROVEN`; uncertainty must not be
narrowed after observing the outcome.

The currently integrated `physical-csv-text-v1` publication profile accepts
CSV/TXT/JSON/LOG. Therefore preparation must either:

- define a measured-guide/reference protocol whose canonical raw witness is
  representable in those formats; or
- separately prepare and review a repository-controlled evidence profile capable
  of retaining the chosen raw visual/reference bytes.

A browser-only attachment is not canonical durable evidence.

## Calibration, characterization and untouched confirmation

The pre-registration in `X3_CHARACTERIZATION_PREREGISTRATION.md` is authoritative
for the simplified experiment design. The evidence procedure must keep distinct:

1. calibration data used to choose/freeze empirical processing and envelopes;
2. characterization trials used to establish the tested-domain behavior;
3. a later untouched confirmation set evaluated only after processing,
   uncertainty calculation, trial rules and output schema are frozen.

At minimum the scenarios distinguish:

- stationary: `delta z = 0`, `delta h = 0`;
- terrain-only: approximately `delta z = 0`, non-zero `delta h`;
- true vertical vehicle motion with local-clearance change comparable to the
  terrain case;
- mixed motion, including approximately `delta z = delta h`, where local
  clearance changes little despite real vehicle movement.

Use both signs where practical, retain every validly started trial, and use a
predeclared trial count/order or outcome-independent stopping rule. No best-trace
selection is permitted.

Before confirmation starts, durably freeze the exact acquisition schema/artifact,
reference method and uncertainty calculation, processing/configuration and digest,
calibration-derived constants/envelopes, scenario/trial rule, target calculations
and output schema. A substantive outcome-informed change starts a new candidate
and requires new confirmation data.

Where reference/timing semantics make them meaningful, retain the existing
falsification quantities:

- vehicle-displacement error <= 5 cm;
- usable discrimination/settling <= 1 s after transition end.

They are experiment targets, not classifier thresholds or flight-acceptance
criteria. A confirmation uncertainty interval crossing a target is `UNPROVEN`,
not PASS.

## Human-checkpoint and publication boundary

This support does not itself request a physical action. A future
`x3-independent-props-off` characterization checkpoint is eligible only through
the existing trusted human-checkpoint mechanism after deterministic preparation
can package and verify:

- exact #251 artifact/runtime/capture support (or one separately reviewed
  logging-only replacement if objectively required);
- the complete executable characterization procedure;
- the independent reference witness procedure and uncertainty schema;
- the trusted raw-evidence publication path;
- the exact tested Git SHA/profile/purpose and artifact provenance/digest.

The mechanism must also enforce the repository-wide one-unresolved-`TEST_REQUIRED`
rule. While another request is unresolved, X3 preparation may proceed but no
second request may be created or bypassed.

The human result for this checkpoint concerns complete, faithful collection of the
pre-registered evidence, not a terrain classifier or flight-capability PASS. Raw
capture/reference evidence must be durably published first; derived empirical
processing/results and any frozen-predictor output are separate; scientific
interpretation is a subsequent durable decision.

## Bounded scientific decision

After separate confirmation, #70 may durably conclude only one of:

- continue toward an independent continuous vehicle-vertical estimate and, if
  needed, explicit terrain representation;
- reject the tested independent-information candidate in its declared domain; or
- identify one concrete missing information source that prevents a decision.

No characterization/confirmation result from this props-off experiment alone
authorizes motorized testing, estimator retuning, Runtime/controller changes or a
world-altitude product claim.

Refs: #70 and owner scientific direction
https://github.com/djibian/webeeblocks/issues/70#issuecomment-5664470710
