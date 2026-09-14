# X3 independent-information checkpoint support boundary

This document is the current support boundary for #70 after the owner adopted the
independent review verdict **X3 VIABLE WITH SIMPLIFICATION**. It does **not**
enable a human-checkpoint profile, request `TEST_REQUIRED`, validate a physical
result or authorize motorized flight.

The pre-registered next scientific experiment is defined in
[X3_SIMPLIFIED_CHARACTERIZATION.md](X3_SIMPLIFIED_CHARACTERIZATION.md). The
sequence is now:

`pre-register bounded characterization -> props-off characterization against an independent metric/time reference -> freeze observed-domain processing/envelopes -> untouched confirmation -> scientific decision`.

Characterization produces empirical envelopes for the tested domain. It does not
retroactively validate the frozen predictor's deterministic-bound flags and it is
not a terrain-classifier or flight-capability acceptance test.

## Integrated support already available

The repository already contains the machine/acquisition components required to
prepare the simplified characterization:

- continuous barometer/IMU acquisition on the exact #251 physical firmware
  (`capture_independent_inputs.py`, integrated by #299);
- the frozen pressure-window calculation (`frozen_pressure_probe.py`, #300);
- hash-bound conditional external metric-reference envelopes
  (`metric_reference.py`, #311);
- the frozen independent barometer/accelerometer replay
  (`frozen_vertical_predictor.py`, #326);
- the logging-only pre-LPF/read-window observer for the exact pinned Crazyflie
  source (`apply_x3_prelpf_timing_observer.py`, integrated by #339);
- the generic Git-backed raw physical-evidence publication path from #298.

These are component proofs only. They do not validate any real metric reference,
clock assumption, sensor timing bound, 5 cm / 1 s result or physical capability.

## Physical artifact decision boundary

The exact #251 checkpoint binary remains the default artifact for the next
characterization:

- firmware source/request target:
  `6562ad827bf0c8bf2c9b609edad36f3e15652133`;
- exact `cf2.bin` SHA-256:
  `67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738`;
- `stabilizer.estimator=3`;
- `ukf.qualityGateTof=20`;
- `ukf.baroNoise=6.25`;
- `ukf.surfaceOffsetS3=1`;
- props removed throughout;
- no firmware retuning, estimator-structure change, Runtime/controller change or
  motorized action.

The #339 observer does **not** silently replace that artifact. Its canonical CI
path proves only that the logging overlay applies to the exact pinned Crazyflie
source and compiles. The diagnostic binary is not the #251 artifact and is not
implicitly checkpoint-qualified.

Under the current owner direction, the pre-LPF observer is no longer a
prerequisite merely to show that an independent displacement calculation excludes
suspect ToF. Stay on exact #251 unless checkpoint preparation exposes one concrete
missing acquisition fact that cannot be obtained otherwise. If new firmware
content becomes necessary, it must be logging-only and minimal, with a new exact
artifact identity and separate review. Never overwrite or repurpose the #251 or
historical `s3-props-off` identities.

The BMI088 INT2/INT3 electrical-source contradiction and exact producer-time
semantics remain `UNPROVEN`. They are not prerequisites to empirical
characterization unless a later scientific claim explicitly depends on them. The
known pinned-firmware `usecTimestamp()` 84/85 scale defect remains relevant to
values actually measured on that TIM7 clock; the correction must not be applied
to FreeRTOS/log timestamps or host time.

## Existing #251 runtime closure

`tools/physical/run_x3_independent_capture.sh` defines the deterministic local
runner for the exact #251 acquisition path. The bundle contract is compatible
with the integrated read-only Crazyflie runtime closure:

- Linux x86-64 / Python 3.10;
- exact cflib source commit
  `45fdb784c9d13074c42835f3b5ac1d12133bf873`;
- exact source tree
  `a78cf78d2b4aba51a0fa2b03de0260664b523401` and `cflib` subtree
  `750e850390753de14019f0e1f55d4fbc44317699`;
- the exact offline wheels pinned by `tools/physical/reference_probe_lock.txt`;
- bundled #251 `cf2.bin`, `capture_independent_inputs.py`, `PROVENANCE.txt` and
  `SHA256SUMS`.

The runner verifies the complete bundle manifest, firmware hash, runtime
provenance and isolated cflib/wheel import closure before importing the collector.
`--verify-environment` performs those checks without radio/hardware. Recording
requires an explicit Crazyradio URI, canonical checkpoint URL, exact request SHA,
duration and new output directory. It invokes the collector with
`--props-removed --installed-bin-confirmed`; it does not flash, write parameters,
reset the estimator, issue commander motion, publish evidence or manufacture a
physical verdict.

The current runner records the #251 log groups, not the `x3AccObs` / `x3BaroObs`
groups from the #339 source overlay. If a concrete acquisition defect later
selects the instrumented path, its capture client/bundle must be extended and
reviewed under that distinct exact artifact identity.

The runtime runner is support code only until the trusted checkpoint mechanism
packages and verifies it. The script's `x3-independent-props-off` string is
capture provenance, not an enabled `TEST_REQUIRED` path.

## Characterization is not deterministic-bound validation

The frozen vertical predictor consumes predeclared deterministic bounds for
specific-force/tilt/initial-velocity error, intersample acceleration, barometer
displacement, sensor-time error and delivery latency. Those fields remain useful
for the conditional confirmation tool and must remain fail-closed when their
provenance is not established.

The owner direction explicitly removes proof of tight deterministic values for
every one of those sub-links as a prerequisite to collecting the next useful
props-off information. Do not choose favorable numbers from the target outcome,
but do not block the empirical characterization merely because a universal
producer-time or worst-case sensor bound is still unavailable.

The simplified experiment instead measures the observable error of the complete
IMU/barometer information path against an independent reference in a bounded test
domain. Characterization may establish empirical processing choices/envelopes
only on its designated characterization trials. Those choices and file identities
must then be frozen before separate confirmation trials are processed.

Running the frozen deterministic predictor in parallel remains permitted as a
conditional diagnostic. Empirical characterization does not change truthful
outputs such as `declared_bounds_validated:false`,
`sensor_producer_timing_validated:false`,
`independent_displacement_verdict:UNPROVEN` or `physical_verdict:null` unless the
specific prerequisites for those fields are separately proven.

## External metric/time reference and synchronization

The real checkpoint must retain an independent metric datum for vehicle Z and
surface height plus at least two clock anchors bracketing all interpreted events.
The witness must remain hash-bound and identify exact rows/frames/observations.
UKF Z/VZ, S3 state, `recording-ready.json` or an arbitrary paired host timestamp
is not an external reference.

The preferred path uses the existing `METRIC_REFERENCE.md` schema and bounded
CSV/TXT/JSON witnesses accepted by the integrated physical-evidence publication
profile. A measured guide plus independently recorded metric/time observations is
acceptable when its explicit uncertainty and exact observation locators are
retained. A camera is optional. If raw visual bytes are used, a separately
reviewed canonical evidence profile capable of retaining those exact bytes must
exist before the checkpoint; a browser attachment is not canonical evidence.

The reference uncertainty participates in every 5 cm / 1 s comparison. An
admissible interval that crosses a target is `UNPROVEN`, not PASS.

## Pre-registered scenario and phase boundary

The exact scenario matrix and processing freeze rules are in
`X3_SIMPLIFIED_CHARACTERIZATION.md`. The future checkpoint must retain:

- at least 30 s stationary calibration;
- stationary (`delta_z=0`, `delta_h=0`);
- terrain-only (`delta_z~=0`, non-zero `delta_h`);
- true vertical motion with clearance change comparable to the terrain case;
- mixed motion, including a case with `delta_z~=delta_h` so local clearance
  changes little while the vehicle actually moves;
- both signs where practical;
- every retained trial, with no best-trace selection;
- a predeclared split between characterization and confirmation trials.

Characterization may select only the predeclared processing/window choices within
the registered family. Before confirmation, freeze exact implementation/digest,
window/event rules, calibration constants, empirical envelopes, reference
uncertainty treatment, data-quality rules and the exact raw-file membership of
both phases. Confirmation then runs unchanged, with no post-hoc retuning.

The retained 5 cm displacement-error and 1 s recovery quantities remain
scientific falsification targets where the reference/time semantics support them.
They are not classifier thresholds and not flight-acceptance criteria. A valid
confirmation counterexample refutes the tested candidate in that characterized
domain. A favorable characterization alone never authorizes motorized testing.

## One future information checkpoint only

The next #70 physical action should be one bounded props-off information
checkpoint, not another S3 tuning loop. Its informational human result concerns
completeness/usability of the pre-registered evidence capture, not a terrain
classifier or flight-capability PASS.

The raw capture, independent reference, characterization/confirmation membership,
frozen processing and untouched confirmation outputs must be durably published
through the integrated evidence bridge and bound to the exact checkpoint/request
and tested Git SHA. Derived calculations remain distinct from raw evidence and
from the owner-authoritative PASS/FAIL/NOT_NEEDED checkpoint result.

After that evidence exists, the scientific decision must be one of:

1. continue toward an independent continuous vertical estimate / explicit terrain
   representation;
2. reject the tested information-path candidate in its characterized domain; or
3. identify one concrete missing information source that keeps the result
   `UNPROVEN`.

No `CHECKPOINT_REQUEST` is justified by this support-only definition. A trusted
checkpoint profile may be enabled only after the exact artifact/support bundle
and executable procedure are reviewed and deterministic machine preparation
passes. The ordinary `AGENTS.md` mechanism must also enforce its one-open-request
and fingerprint-deduplication rules. Until then there is no `TEST_REQUIRED` from
this work.