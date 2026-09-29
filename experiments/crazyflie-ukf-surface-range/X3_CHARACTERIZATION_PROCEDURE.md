# X3 props-off characterization and untouched-confirmation procedure

This is the concrete collection procedure required by the simplified #70 X3
pre-registration. It closes the two remaining pre-acquisition proof gaps without
changing firmware, estimator parameters, Runtime/controller behavior or the
motorized boundary.

It does **not** request `TEST_REQUIRED`, authorize flashing or motors, claim a
world-altitude capability, or turn a characterization target into flight
acceptance.

The scientific sequence remains:

`characterization -> durable freeze -> untouched confirmation -> scientific decision`

## 1. Exact artifact and safety boundary

Use only the bundle-proven #251 props-off artifact/configuration:

- `cf2.bin` SHA-256
  `67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738`;
- `stabilizer.estimator=3`;
- `ukf.qualityGateTof=20`;
- `ukf.baroNoise=6.25`;
- `ukf.surfaceOffsetS3=1`;
- props removed for every capture.

No ToF/barometer/S3 retuning, Runtime/controller change, `rangeUp` fusion, full
`z/f/r` expansion or motorized action belongs to this experiment. The Crazyflie
is hand-carried.

Before a physical session, the packaged verifier and environment check must pass.
A preparation failure is not a reason to bypass verification or substitute a
new runtime.

## 2. Apparatus and uncertainty predeclaration

Before the first characterization capture, retain UTF-8 metadata identifying:

- the rigid world-fixed metric guide/frame and common world datum;
- the Crazyflie body reference feature read against that guide;
- floor and raised-surface measurement method;
- guide and surface-height resolution;
- independent stopwatch/display identity and resolution;
- conservative human reading/reaction allowance;
- manipulator and observer/recorder roles.

Do not narrow these uncertainty terms after observing a result. The guide must
not support, constrain or drive vehicle motion.

## 3. Fixed outcome-independent trial schedule

Characterization and untouched confirmation use the same predeclared schedule.

Each phase has **three primary cycles**. In every cycle execute one capture of
each scenario in this fixed order:

1. `stationary`;
2. `terrain`;
3. `vertical`;
4. `mixed`.

This gives twelve intended procedure-complete captures per phase. Every validly
started capture is retained, including unfavorable or procedurally invalid
captures. Never delete a trace or replace it because its scientific result looks
good or bad.

A capture may be replaced only for a collection/procedure defect established
without consulting predictor performance, for example: runner failure, wrong
artifact identity, missing raw stream, ambiguous synchronization gesture,
incomplete witness rows, or reference/clock coverage rejected by the frozen
reference processor.

After the three primary cycles, run replacements in original missing-slot order.
Stop replacing a scenario when it has three procedure-complete captures. Start at
most **five captures per scenario per phase**. If three procedure-complete
captures cannot be obtained within five starts, that phase is incomplete and the
scientific result remains `UNPROVEN` for that phase.

Procedure completeness is not a scientific PASS. It means only that the exact
artifact/runtime and raw/reference evidence are intact and mechanically
interpretable under the pre-registered contract.

## 4. One capture

Use a fresh output directory and a fresh append-only `reference-witness.csv` for
every started capture. Never overwrite a prior capture or witness.

For every capture:

1. start raw capture and the independent stopwatch;
2. after logging is established, perform the first externally timed angular
   synchronization gesture;
3. return to the stationary calibration pose and retain at least 30 s of
   guaranteed calibration after uncertainty propagation;
4. establish a stable pre-event plateau;
5. execute the predeclared scenario event(s), recording conservative independent
   `event_start` / `event_end`, vehicle-Z and surface-Z bounds;
6. after every analyzed transition, continuously observe the same vehicle body
   reference against the world guide long enough to cover the complete claimed
   post-transition timing window;
7. retain a conservative `z_after_m` interval that bounds that same body
   reference throughout the continuously observed hold;
8. record independent-clock bounds for the start and end of that hold and map
   them to `z_after_hold_start_reference_s` and
   `z_after_hold_end_reference_s` in the metric-reference input;
9. keep stable separation before the next event and perform a final
   synchronization gesture late enough to bracket every interpreted interval;
10. retain all raw and external-reference bytes exactly as collected.

### 4.1 Binding the continuous hold to the canonical witness CSV

The canonical CSV header from `X3_REFERENCE_WITNESS_TEMPLATE.csv` is unchanged.
For every analyzed event, append two additional direct-observation rows with
`row_kind` equal to `z_after_hold_start` and `z_after_hold_end`. Both rows must
carry the same `scenario_id` and `trial_id` as the event and must be named in the
event witness locator used by the metric-reference input.

- `z_after_hold_start` records the conservative independent-clock interval at
  which continuous observation of the post-transition body reference began;
- `z_after_hold_end` records the conservative independent-clock interval at
  which that continuous observation ended;
- both rows repeat the same conservative `vehicle_z_low_m` /
  `vehicle_z_high_m` envelope that bounds every observed value of that body
  reference throughout the complete hold; their notes state that the interval is
  a continuous-hold envelope rather than two isolated endpoint readings.

These two row kinds extend the witness vocabulary for this concrete procedure;
they do not change the CSV columns. The mechanical transformation maps their
reference-time intervals respectively to `z_after_hold_start_reference_s` and
`z_after_hold_end_reference_s`, and uses their shared vehicle-Z envelope as the
post-transition Z witness. If one conservative envelope cannot cover the whole
observed hold, or the two rows disagree, that event is procedurally incomplete
and its 1 s comparison remains `UNPROVEN`.

This is a bounded post-transition hold witness, not a continuous ground-truth
trajectory. It must not be promoted into a claim about unobserved motion outside
the retained hold interval.

The temporal reference requirement is fail-closed. Under **every** admissible
affine clock, the continuously observed vehicle-Z hold must begin no later than
`event_end + 0.25 s` and remain valid through at least
`event_end + 0.75 s`. `metric_reference.py` verifies this temporal coverage. If
the observer cannot maintain a defensible continuous Z bound through that
window, or clock uncertainty prevents proving coverage, the 1 s comparison is
`UNPROVEN`; do not substitute a later plateau reading.

This temporal check does not magically validate physical stillness. The guide
observation and its conservative interval remain an external physical witness;
the processor only proves that the declared witness interval covers the timing
window under all admissible affine clocks.

## 5. Scenario choreography

All vehicle-Z and surface-Z readings use the same world datum and body reference.
Downward ToF, UKF/S3 state and predictor output never supply independent reference
values.

### `stationary`

Keep vehicle and surface unchanged and retain the required before/after and
continuous post-window vehicle-Z bounds.

### `terrain`

Hold vehicle world Z approximately constant against the guide while moving the
local surface floor -> raised surface, then after a stable plateau raised surface
-> floor. Record the opposite-sign events separately.

### `vertical`

Keep the local surface fixed. Hand-carry the Crazyflie vertically by roughly the
terrain-height magnitude, hold, then return in the opposite direction. The guide
measurements, not intended displacement, are the reference.

### `mixed`

Coordinate vehicle and surface motion so one event is approximately
`delta z = delta h`, then perform the opposite-sign return after a stable plateau.
Record vehicle and surface intervals independently.

Both displacement signs are therefore exercised in every non-stationary
procedure-complete capture without selecting traces after the outcome.

## 6. Mechanical reference processing

For every procedure-complete capture, mechanically transform the retained witness
into `webeeblocks.x3.metric-reference-input.v1` according to
`X3_REFERENCE_WITNESS.md` and `METRIC_REFERENCE.md`, including the two mandatory
post-transition hold-time fields from section 4 and the exact witness rows from
section 4.1.

`metric_reference.py` must fail closed when the complete post-transition
vehicle-Z hold does not cover the analyzed timing window. Its result remains
`COMPUTED_CONDITIONAL`; it never creates a physical PASS.

## 7. Characterization freeze

After all required characterization slots plus any permitted replacements have
been collected and durably published, stop physical collection. Untouched
confirmation must not start until the allowed characterization-derived choices
are durably frozen and hash-bound.

The freeze records at least:

- exact acquisition schema and artifact/runtime identity;
- exact reference method and uncertainty calculation;
- synchronization-gesture detector / IMU row-bracketing rule;
- witness-to-metric-reference transformation;
- exact vehicle-vertical processing implementation/configuration actually chosen;
- calibration-derived constants or empirical envelopes;
- this scenario/trial schedule and replacement rule;
- calculations/output schema used for the 5 cm and 1 s falsification quantities.

The existing frozen deterministic predictor remains optional conditional support;
this procedure does not validate its stronger assumptions and does not require it
to be added to the characterization bundle.

## 8. Untouched confirmation

Only after the durable freeze, execute confirmation with the same three-cycle
scenario order and the same replacement rule. Process every procedure-complete
confirmation capture with the exact frozen reference, uncertainty and
vehicle-vertical processing. Do not discard a valid counterexample or replace a
trial because its scientific outcome is outside target.

The predeclared falsification quantities remain:

- vehicle-displacement error no more than 5 cm where the independent metric
  reference and uncertainty make that comparison meaningful;
- usable discrimination/settling no more than 1 s after transition end only where
  the independent timing **and continuous vehicle-Z hold** make that comparison
  meaningful.

An uncertainty interval crossing either target yields `UNPROVEN`, not PASS.

## 9. Durable evidence

Retain every started characterization and confirmation capture, including
procedure failures and unfavorable outcomes, plus:

- raw continuous Crazyflie streams;
- append-only external witness CSV, including every `z_after_hold_start` and
  `z_after_hold_end` row;
- apparatus/datum/role/resolution/uncertainty metadata;
- exact metric-reference input/output;
- exact processing inputs/outputs actually used;
- the characterization freeze and every hash-bound configuration/file;
- exact bundle provenance/manifest;
- a trial ledger recording phase, cycle, scenario, start order, procedure status
  and any procedure-only replacement reason.

## 10. Decision boundary

A future checkpoint PASS means only that the pre-registered evidence was collected
completely and faithfully. It does not mean the altitude problem is solved.

After untouched confirmation, the separate scientific decision remains bounded
to the conclusions already authorized by the X3 pre-registration. Nothing here
authorizes motorized testing, estimator retuning, threshold tuning or a product
world-altitude claim.

Refs: #70, `X3_CHARACTERIZATION_PREREGISTRATION.md`,
`X3_CHECKPOINT_SUPPORT.md`, `X3_REFERENCE_WITNESS.md`, `METRIC_REFERENCE.md`.
