# X3 simplified props-off characterization pre-registration

This document implements the current owner scientific direction for #70 after the
independent X3 review. It is a **pre-registration/support definition only**. It
does not enable a checkpoint profile, request `TEST_REQUIRED`, authorize flashing,
or claim any physical or motorized capability.

The scientific sequence is:

`bounded characterization -> freeze observed-domain processing/envelopes -> separate confirmation -> scientific decision`

Characterization establishes empirical behavior in the tested domain. It does not
validate universal deterministic sensor/timing bounds, does not retroactively set
the frozen predictor's validation flags, and cannot by itself authorize motorized
testing.

## 1. Physical artifact boundary

Use the unchanged #251 props-off firmware/configuration unless deterministic
preparation proves a concrete acquisition defect that requires logging-only
instrumentation:

- firmware/request source: `6562ad827bf0c8bf2c9b609edad36f3e15652133`;
- `cf2.bin` SHA-256:
  `67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738`;
- `stabilizer.estimator=3`;
- `ukf.qualityGateTof=20`;
- `ukf.baroNoise=6.25`;
- `ukf.surfaceOffsetS3=1`;
- props removed for the complete characterization.

No estimator retuning, Runtime/controller change, `rangeUp` fusion, full `z/f/r`
expansion, or motorized action belongs to this experiment. A future logging-only
instrumented artifact, if objectively required, must receive a distinct exact
identity rather than replacing or repurposing #251.

## 2. Information to retain

Every characterization and confirmation trial must retain the raw information
needed to evaluate the complete independent IMU/barometer path and to reconstruct
the local-surface change separately:

- continuous pressure/barometer signal and temperature;
- `acc.x`, `acc.y`, `acc.z`;
- `gyro.x`, `gyro.y`, `gyro.z`;
- host and available device/log timing;
- downward range/local clearance;
- estimator/ToF diagnostics useful for interpretation, while keeping ToF and
  estimator state **out of the independent vehicle-Z prediction itself**;
- exact firmware/configuration and capture/runtime provenance;
- all retained trials, including failed/unfavorable trials.

The known pinned-2026.08 `usecTimestamp()` 84/85 scale defect must be handled only
where that timestamp semantics actually applies. It must not be copied onto
FreeRTOS/log timestamps by analogy.

Exact BMI088 INT2/INT3 electrical provenance, proof that
`sensorData.interruptTimestamp` is producer time, and the pre-LPF observer are not
prerequisites to this characterization unless new evidence makes one of them
causally necessary for a claim being tested.

## 3. Independent metric/time reference

The physical evidence must contain an independent reference for vehicle vertical
displacement and surface-height change, with an explicit uncertainty model and
durable Controller-readable witness. It must also contain enough clock anchoring
to align interpreted events with that reference and to state the synchronization
uncertainty.

The reference must not be derived from UKF/S3 state, the Crazyflie downward ToF,
or the predictor under test. Raw witness bytes/rows and the transformation from
those observations to metric/time reference values must be retained and
hash-bound through the repository's trusted evidence path.

If the chosen reference cannot yield an uncertainty interval narrow enough to
interpret a predeclared target, that comparison is `UNPROVEN`; do not narrow the
uncertainty after observing the outcome.

## 4. Scenarios and trial retention

Use separate calibration and untouched confirmation phases. The scenario set must
include at minimum:

1. stationary: `delta z = 0`, `delta h = 0`;
2. terrain-only: approximately `delta z = 0`, non-zero `delta h`;
3. true vertical vehicle motion with local-clearance change comparable to the
   terrain-only case;
4. mixed vehicle/surface motion, including a case with approximately
   `delta z = delta h` so local clearance changes little despite real vehicle
   displacement.

Exercise both displacement signs where practical. Predeclare the number/order of
trials or an outcome-independent stopping rule. Retain every validly started
trial; no best-trace selection is permitted.

## 5. Frozen characterization processing

Before looking at confirmation outcomes, freeze the processing applied to raw
records. At minimum it must specify:

- calibration interval and quantities estimated from calibration only;
- signal units, coordinate/sign conventions and gravity handling;
- resampling/alignment rules and treatment of missing/late samples;
- barometer conversion/filtering used by the independent path;
- IMU integration/filtering and any drift correction learned from calibration;
- event/window selection rules using reference-independent criteria where
  possible;
- how vehicle displacement `delta z_ind` and local-clearance change `delta c`
  combine into the surface-height estimate, e.g. `delta h = delta z_ind - delta c`;
- uncertainty propagation from the external metric/time reference and the
  observed calibration envelope;
- exact output tables/plots/statistics used for the decision.

The characterization phase may be used to choose/freeze empirical envelopes or
processing appropriate to the declared tested domain. Once frozen, the untouched
confirmation phase is evaluated with no parameter/window retuning from its
outcomes.

The existing frozen deterministic predictor remains available as a **conditional
confirmation tool**. Its fail-closed flags remain unchanged unless their own
stronger assumptions are independently established; this experiment does not
manufacture `declared_bounds_validated:true` or
`sensor_producer_timing_validated:true`.

## 6. Predeclared falsification quantities

Where the independent reference and synchronization semantics make them
meaningful, retain the existing experimental targets:

- vehicle-displacement error: at most **5 cm**;
- settling/usable discrimination: at most **1 s after transition end**.

These are characterization/confirmation falsification quantities, not classifier
thresholds and not flight-acceptance criteria. A valid confirmation
counterexample outside the target refutes that candidate in the declared domain.
An uncertainty interval crossing a target yields `UNPROVEN`, not PASS.

The experiment must also report scenario separation directly: terrain-only,
true-vertical and mixed cases must not be made distinguishable by post-hoc
scenario-specific tuning.

## 7. Characterization -> confirmation freeze rule

Before confirmation starts, durably record:

- exact raw/acquisition schema and artifact identity;
- exact reference method and uncertainty calculation;
- exact processing implementation/configuration and its digest;
- calibration-derived constants/envelopes;
- trial scenarios/order or stopping rule;
- acceptance/falsification calculations and output schema.

After that freeze, no change informed by confirmation outcomes may be applied to
the same confirmation set. Any substantive change starts a new candidate with new
confirmation data.

## 8. Evidence and human boundary

This document is not a human checkpoint request. A future props-off information
checkpoint is eligible only through the existing trusted checkpoint mechanism and
only after deterministic preparation can package the exact artifact, capture
support, reference witness procedure, evidence-publication path and executable
instructions.

Because only one unresolved `TEST_REQUIRED` may exist, this work must not create
or bypass a second request. Machine preparation and review may proceed silently.

The checkpoint's human result concerns whether the pre-registered evidence was
collected completely and faithfully. Scientific interpretation remains a separate
durable step over the published raw/reference evidence.

## 9. Decision after separate confirmation

The allowed scientific conclusions are deliberately bounded:

- continue toward an independent continuous vehicle-vertical estimate and, if
  needed, explicit terrain representation;
- reject the tested independent-information candidate in its declared domain; or
- identify one concrete missing information source that prevents a decision.

No characterization or confirmation result from this props-off experiment alone
justifies estimator retuning, terrain-classifier threshold tuning, motorized
flight, or a product world-altitude capability claim.

Refs: #70 and owner scientific direction
https://github.com/djibian/webeeblocks/issues/70#issuecomment-5664470710
