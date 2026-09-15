# X3 props-off characterization and untouched-confirmation procedure

This is the executable collection procedure for the simplified #70 X3 path. It
implements the already-reviewed pre-registration, support boundary and measured-
guide reference witness. It does **not** request `TEST_REQUIRED`, enable a
checkpoint profile, flash firmware, change parameters, authorize motors, validate
sensor/timing bounds, or claim a world-altitude capability.

The scientific sequence remains:

`characterization collection -> freeze -> untouched confirmation -> scientific decision`

The exact bundle is intentionally usable in more than one sitting. Characterization
and confirmation may belong to the same unresolved trusted checkpoint, but
confirmation must not start until the characterization-derived processing,
reference and uncertainty choices have been frozen and durably hash-bound. The
checkpoint target/artifact remains unchanged across that pause.

## 1. Exact artifact and safety boundary

Use only the bundle-proven exact #251 props-off artifact and configuration:

- `cf2.bin` SHA-256
  `67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738`;
- `stabilizer.estimator=3`;
- `ukf.qualityGateTof=20`;
- `ukf.baroNoise=6.25`;
- `ukf.surfaceOffsetS3=1`;
- props removed for every capture.

`run_x3_independent_capture.sh` records only. It never flashes the binary or
writes estimator parameters. Before a real capture, the operator must separately
know that the exact bundled binary is installed and must pass both explicit
runner confirmations. Any uncertainty about that identity makes the capture
procedurally invalid; retain it, do not reinterpret it as evidence.

No motors are used anywhere in this procedure. The Crazyflie is hand-carried.
No threshold, gate, persistence, Runtime/controller, `rangeUp` fusion or full
`z/f/r` estimator change is part of the experiment.

## 2. Hardware-free bundle verification

Before the physical session, from the bundle root run:

```sh
python3 -B verify_x3_characterization_bundle.py .
./run_x3_independent_capture.sh --verify-environment
```

Both must pass without hardware. A failure is a preparation defect, not a reason
to bypass verification or substitute a different runtime.

## 3. Predeclared apparatus and uncertainties

Before the first characterization capture, record in a retained UTF-8 JSON or TXT
file, without looking at event outcomes:

- the rigid world-fixed guide/frame and common world datum;
- the Crazyflie body reference feature read against that guide;
- floor and raised-surface measurement method;
- guide resolution;
- surface-height measurement resolution;
- independent stopwatch/display identity and resolution;
- conservative human reading/reaction allowance;
- manipulator and observer/recorder roles;
- the physical range of vehicle Z, surface height, hand-carried speed and tilt the
  experiment intends to cover.

Do not narrow any of those uncertainty terms after observing a result. The guide
must not support, constrain or drive the vehicle motion. If several guide sections
are used, retain their common-datum survey before collection.

## 4. Outcome-independent trial rule

The characterization phase and the untouched-confirmation phase use the same
predeclared schedule.

Each phase has three primary cycles. In every cycle execute one capture of each
scenario in this fixed order:

1. `stationary`;
2. `terrain`;
3. `vertical`;
4. `mixed`.

That gives twelve intended procedure-complete captures per phase. A capture that
was validly started is **always retained**, including failed, unfavorable or
procedurally invalid captures.

A capture may be replaced only for a collection/procedure defect established
without consulting the predictor or performance result, for example: runner
failure, wrong artifact identity, missing raw stream, ambiguous synchronization
gesture, incomplete witness rows, or reference/clock coverage that
`metric_reference.py` cannot interpret. After all three primary cycles, run
replacements in original missing-slot order. Stop replacing a scenario when it
has three procedure-complete captures, and start at most five captures for that
scenario in the phase. If three procedure-complete captures cannot be obtained
within five starts, the phase is incomplete. Do not change this rule because the
observed error looks good or bad.

A procedure-complete capture is not a scientific PASS. Procedure completeness
means only that the exact artifact/runtime and raw/reference evidence are intact
and mechanically interpretable under the pre-registered reference contract.

## 5. One capture

Use a fresh output directory for every started capture. Keep a separate copy of
`X3_REFERENCE_WITNESS_TEMPLATE.csv` beside that capture as
`reference-witness.csv`; never overwrite a prior capture or prior witness.

The recommended capture duration is 150 seconds, which stays within the runner's
30--300 second bounded interface and leaves operational margin around calibration,
events and the final synchronization gesture. The reference rows, not wall-clock
intent, determine whether the retained capture actually satisfies the processor's
coverage constraints.

Example invocation once a trusted X3 checkpoint exists:

```sh
./run_x3_independent_capture.sh \
  --uri 'radio://0/80/2M' \
  --checkpoint-url 'https://github.com/djibian/webeeblocks/issues/<CHECKPOINT>' \
  --request-sha '<EXACT_BUNDLE_TARGET_SHA>' \
  --seconds 150 \
  --output '<NEW_CAPTURE_DIRECTORY>' \
  --props-removed \
  --installed-bin-confirmed
```

The URI shown is only the current reference-radio example; the actual trusted
checkpoint procedure binds the applicable URI. Do not start a physical capture
without that checkpoint.

Use explicit operator gates rather than a memorized timed script. The prior #70
history already showed that a capture whose operator could not reliably follow a
timed choreography is not valid performance evidence.

For every capture:

1. start the raw capture and independent stopwatch;
2. after logging is visibly established, perform the first short angular `sync`
   gesture and record its conservative independent-clock interval;
3. return to the required stationary calibration pose;
4. record `calibration_start`, remain stationary for a **45 s target hold**, then
   record `calibration_end`;
5. keep at least 4 s of stable plateau before the first analyzed transition;
6. execute the scenario events below, recording guide/surface plateau intervals
   and conservative `event_start` / `event_end` intervals;
7. keep at least 4 s of stable plateau between analyzed transitions and after the
   final one;
8. perform a distinct final angular `sync` gesture late enough to bracket all
   interpreted reference time and the complete post-event window;
9. leave additional recording margin after the final gesture, then let the runner
   finish normally;
10. retain the raw capture and append-only witness exactly as collected.

The 45 s and 4 s values are operational margins, not substitutions for the exact
interval checks. The unchanged processor still decides whether every admissible
affine clock gives at least 30 s of guaranteed calibration, at least 2 s between
episodes, a positive event duration and `end_device_high + 0.75 s <= covered_end`.
If uncertainty defeats those checks, retain the capture and classify only its
**procedure** as invalid.

## 6. Scenario choreography

All vehicle-Z and surface-Z readings use the same surveyed world datum and the
same Crazyflie body reference feature. Downward ToF, UKF/S3 state and predictor
outputs never supply the independent reference values.

### `stationary`

Keep vehicle and surface unchanged. After calibration and a stable plateau, mark
one bounded `stationary` episode while continuing to hold the vehicle motionless.
Record independent before/after vehicle-Z and surface-Z intervals. This supplies
the required `delta z = 0`, `delta h = 0` control without manufacturing motion.

### `terrain`

Hold the Crazyflie body reference at approximately constant world Z using the
world guide. Move the local surface from floor to the raised surface, then after a
new stable plateau move it back from raised surface to floor. Record the two
opposite-sign terrain events separately. The vehicle is not intentionally moved
with the surface.

### `vertical`

Keep the local surface fixed. Hand-carry the Crazyflie vertically by approximately
the same magnitude as the terrain height change, hold a stable plateau, then
return in the opposite direction. Record both vertical events. The exact
before/after guide intervals, not the intended displacement, are the reference.

### `mixed`

Coordinate vehicle and surface motion so one event has approximately
`delta z = delta h`, leaving local clearance nearly unchanged despite real world-Z
motion. After a stable plateau, perform the opposite-sign return event. Record
both vehicle and surface intervals independently. Approximate equality is a
scenario-design goal only; the retained guide measurements define what actually
occurred.

Both displacement signs are therefore exercised within every non-stationary
procedure-complete capture without selecting traces after the outcome.

## 7. Mechanical reference processing

For every procedure-complete capture, mechanically transform the retained witness
into `webeeblocks.x3.metric-reference-input.v1` exactly as specified by
`X3_REFERENCE_WITNESS.md` and `METRIC_REFERENCE.md`.

Hash the exact raw sources in the specification, then run:

```sh
python3 -B metric_reference.py metric-reference-input.json \
  --output metric-reference-result.json
```

The result must be retained even though its physical and affine-clock validation
flags remain false. A failure to prove clock/reference admissibility is
`UNPROVEN`; it is never repaired by narrowing intervals from sensor or predictor
output.

The descriptive pressure probe may also be run against the same exact barometer
capture. It is context only and produces no physical verdict.

## 8. Characterization freeze

After the twelve required characterization slots plus any permitted replacements
have been collected and durably published, **stop physical collection**.
Confirmation must not start yet.

Using characterization data only, freeze the exact observed-domain processing
permitted by `X3_CHARACTERIZATION_PREREGISTRATION.md`. The durable freeze must
hash-bind at least:

- the exact raw/acquisition schema and exact artifact/runtime identity;
- the exact reference witness method and uncertainty calculation;
- the synchronization-gesture detector / IMU row-bracketing rule;
- the CSV-to-`metric-reference-input.v1` transformation;
- the exact vehicle-vertical processing implementation and configuration;
- all calibration-derived constants or empirical envelopes;
- all declared bounds supplied to `frozen_vertical_predictor.py`, if that
  conditional predictor is used;
- the scenario/trial rule from this procedure;
- the derived output schema and the calculations used for the 5 cm / 1 s
  falsification quantities.

The bundle contains the exact `frozen_vertical_predictor.py` and its frozen
contract so that this implementation can be selected without fetching additional
code. Its validation flags remain false unless their stronger assumptions are
independently established. Characterization may inform empirical observed-domain
choices, but it must not manufacture universal deterministic bounds.

The freeze artifact and every file it names must be retained through the trusted
CSV/TXT/JSON/LOG evidence path with explicit SHA-256 digests. Once frozen, no
confirmation outcome may change those bytes or parameters. Any substantive
outcome-informed change creates a new candidate and requires new confirmation
data.

## 9. Untouched confirmation

Only after the freeze is durably recorded, execute the confirmation phase with
exactly the same three-cycle scenario order and the same replacement rule from
section 4. Do not reopen characterization choices while confirmation captures are
being collected.

Process every procedure-complete confirmation capture using the exact frozen
reference, uncertainty and vehicle-vertical processing. Do not discard a valid
counterexample. Do not replace a trial because its scientific outcome is outside
the target.

The predeclared quantities remain:

- vehicle-displacement error no more than 5 cm where the independent reference
  and uncertainty make that comparison meaningful;
- usable discrimination/settling no more than 1 s after transition end where the
  timing reference makes that comparison meaningful.

An uncertainty interval crossing a target is `UNPROVEN`, not PASS. The
`conditional_half_width_within_5cm` field produced by the frozen predictor is not
itself a measured displacement-error PASS, and its latency field is not proof of
sensor-producer latency. Final scientific interpretation must compare the frozen
prediction with the independent physical reference under the stated uncertainty.

## 10. Evidence that must be published

The complete checkpoint evidence retains every started characterization and
confirmation trial, including procedural failures and unfavorable results, plus:

- raw `barometer.csv`, `imu.csv`, downward-range and estimator/context streams;
- each append-only `reference-witness.csv`;
- apparatus/datum/role/resolution/uncertainty metadata;
- exact metric-reference input and output JSON;
- exact pressure/predictor inputs and outputs actually used;
- the characterization freeze and every hash-bound processing/configuration file;
- the exact bundle `PROVENANCE.txt` and `MANIFEST.json`;
- a trial ledger identifying phase, cycle, scenario, start order and whether a
  replacement was required for a procedure-only defect.

The selected evidence is representable in the existing `physical-csv-text-v1`
profile. Browser-only attachments are not canonical evidence.

## 11. Decision boundary

A checkpoint PASS means only that this pre-registered evidence was collected
completely and faithfully. It does not mean the altitude problem is solved.

After untouched confirmation, the separate scientific decision remains bounded
to one of the already-authorized conclusions:

- continue toward an independent continuous vehicle-vertical estimate and, if
  needed, explicit terrain representation;
- reject the tested independent-information candidate in its declared domain; or
- identify one concrete missing information source that prevents a decision.

Nothing in this props-off procedure authorizes motorized testing, estimator
retuning, Runtime/controller changes, threshold tuning or a product world-altitude
claim.

Refs: #70, `X3_CHARACTERIZATION_PREREGISTRATION.md`,
`X3_CHECKPOINT_SUPPORT.md`, `X3_REFERENCE_WITNESS.md`,
`METRIC_REFERENCE.md`, `FROZEN_VERTICAL_PREDICTOR.md`.
