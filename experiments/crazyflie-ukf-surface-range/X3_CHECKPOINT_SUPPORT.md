# X3 independent-information checkpoint support boundary

This document is the post-#326 preparation boundary for #70. It does **not**
enable a human-checkpoint profile and it does not request a physical test.

The repository now contains the offline/acquisition components that were missing
after the archived-input audit:

- continuous barometer/IMU acquisition on the exact #251 physical firmware
  (`capture_independent_inputs.py`, integrated by #299);
- the frozen pressure-window calculation (`frozen_pressure_probe.py`, #300);
- hash-bound conditional external metric-reference envelopes
  (`metric_reference.py`, #311);
- the independent barometer/accelerometer replay with explicit deterministic
  timing/intersample bounds (`frozen_vertical_predictor.py`, #326);
- the logging-only pre-LPF/read-window observer for exact pinned Crazyflie source
  (`apply_x3_prelpf_timing_observer.py`, integrated by #339).

The generic Git-backed physical evidence path from #298 is also integrated. These
are component proofs only. They do not validate any real reference, clock model,
sensor bound or 5 cm / 1 s physical result.

## Physical artifact decision boundary

The exact #251 checkpoint binary remains the only currently established physical
artifact for this #70 line:

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
source and compiles. The diagnostic binary is not retained as the #251 artifact,
is not bound to `s3-props-off`, and no `x3-independent-props-off` trusted profile
is enabled for it. #342 additionally leaves the electrical source of
`sensorData.interruptTimestamp` UNPROVEN; neither that value nor the observer's
MCU read windows may be promoted to sensor producer timestamps.

There are therefore two reviewable future paths, and neither is selected merely
because the observer exists:

1. stay on exact #251 only if the pre-registered deterministic predictor bounds
   explicitly cover the existing post-firmware-LPF acceleration path together
   with all producer/filter/timing uncertainty; or
2. if those bounds cannot be justified tightly enough without pre-LPF evidence,
   prepare a **separate** exact instrumented physical artifact from the integrated
   #339 overlay, with a new artifact identity, exact source/applicator/binary
   digests, compatible capture support and a separately reviewed trusted
   checkpoint profile.

The choice must be made from pre-registered bound/reference feasibility, not from
the target terrain/mixed outcome. Never overwrite, rename or repurpose the #251
artifact or the historical `s3-props-off` identity to carry instrumented firmware.
No new flash content is authorized by this document.

## Existing #251 runtime closure

`tools/physical/run_x3_independent_capture.sh` defines the deterministic local
runner prepared for the exact #251 acquisition path. The bundle contract is
intentionally compatible with the already integrated read-only Crazyflie runtime
closure:

- Linux x86-64 / Python 3.10;
- exact cflib source commit
  `45fdb784c9d13074c42835f3b5ac1d12133bf873`;
- exact source tree
  `a78cf78d2b4aba51a0fa2b03de0260664b523401` and `cflib` subtree
  `750e850390753de14019f0e1f55d4fbc44317699`;
- the same four exact offline wheels already pinned by
  `tools/physical/reference_probe_lock.txt`;
- bundled #251 `cf2.bin`, `capture_independent_inputs.py`, `PROVENANCE.txt` and
  `SHA256SUMS`.

The runner verifies the complete bundle manifest, exact firmware hash, exact
runtime provenance and isolated cflib/wheel import closure before importing the
collector. `--verify-environment` performs those checks without radio/hardware.
The recording path requires an explicit Crazyradio URI, canonical checkpoint URL,
exact request SHA, duration and new output directory. It invokes the collector
with `--props-removed --installed-bin-confirmed`; it does not flash, write a
parameter, reset the estimator, issue commander motion, publish evidence or
manufacture a physical verdict.

This runner currently records the stock #251 log groups, not the `x3AccObs` /
`x3BaroObs` groups introduced by the #339 source overlay. If the instrumented path
is selected later, its capture client/bundle must be extended and reviewed under
that new exact artifact identity rather than treating this #251 runner as
implicitly compatible.

This runtime runner is support code only until a trusted checkpoint profile
packages and verifies the stated bundle. Do not treat the presence of the script
as an enabled `TEST_REQUIRED` path.

## Bound provenance is still a hard precondition

The independent replay consumes six pre-declared deterministic bounds:

1. `specific_force_error_g`;
2. `max_body_z_tilt_deg`;
3. `initial_velocity_error_m_s`;
4. `intersample_acceleration_error_m_s2`;
5. `barometer_displacement_error_m`;
6. `sensor_time_error_s`, plus the separate
   `delivery_latency_error_s` delivery allowance.

Before any confirmation checkpoint request, the exact numeric values and their
provenance must be frozen in durable project state **without using the target
terrain/mixed outcomes to narrow them**. In particular, the 10/20 ms logging
cadence and the existing gap checks do not bound between-sample acceleration;
`intersample_acceleration_error_m_s2` needs an independent physical/specification
basis. Likewise, Crazyflie log time is not a per-sensor producer timestamp, so a
small `sensor_time_error_s` cannot be inferred merely from the log period.

The #339 observer narrows one software-observability problem by retaining
acceleration before the Crazyflie 30 Hz software LPF and by retaining CPU register
read windows. It does not validate BMI088 internal sample/filter timing, BMP3xx
conversion/IIR timing, specific-force accuracy, physical motion between retained
samples or delivery latency. On the #251 path, any deterministic bound must also
cover the existing post-LPF acceleration semantics rather than pretending those
logs are raw sensor samples.

A future checkpoint candidate must therefore make the following reviewable before
it is enabled:

- exact bound values;
- a source/witness or explicitly pre-registered physical constraint supporting
  every value;
- which assumptions remain unvalidated and therefore keep the result
  `UNPROVEN`;
- proof that no value was selected from the target confirmation outcome;
- the exact physical artifact/capture path to which those bounds apply.

If a defensible bound cannot be supplied, the checkpoint remains ineligible; do
not substitute a favorable number just to make the 5 cm / 1 s conditional checks
pass.

## External metric reference and synchronization

The real checkpoint must retain an independent metric datum for vehicle Z and
surface height plus at least two clock anchors bracketing all interpreted events.
The witness must remain hash-bound and identify exact rows/frames/observations.
UKF/S3 state, the collector's `recording-ready.json`, host receipt timestamps or
an arbitrary paired timestamp are not an external metric reference.

The currently integrated `physical-csv-text-v1` evidence publication profile
accepts CSV/TXT/JSON/LOG, not raw video/image files. Therefore one of these must
be true **before** a checkpoint is requested:

- use a measured guide / metric observation protocol whose canonical raw witness
  is representable and retained as bounded text/CSV/JSON under that profile; or
- separately prepare and review a repository-controlled evidence profile that can
  durably retain the exact visual witness bytes.

A browser-only `user-attachments` upload is non-canonical and does not close this
precondition.

## One future information checkpoint only

Once artifact/capture selection, runtime packaging, bound provenance and metric-
reference publication are all reviewed and integrated, the next physical action
should be one bounded props-off information checkpoint, not another S3 tuning
loop. Its pre-registered procedure must retain enough prior stationary calibration
(at least 30 s for the current calculations) and apply the same calculation path
across stationary, terrain, true-vertical and mixed episodes, with both movement
signs where the event kind has a sign.

The raw capture must be published through the integrated generic evidence bridge
and bound to the exact checkpoint/request and tested Git SHA. Derived reference
and predictor JSON are separate from raw evidence; the owner-authoritative human
PASS/FAIL/NOT_NEEDED result remains separate again.

The checkpoint's informational PASS criterion must concern completeness and
usability of the pre-registered evidence path, not declare a terrain classifier
or flight capability. The predictor itself remains fail-closed:
`declared_bounds_validated:false`, `sensor_producer_timing_validated:false`,
`independent_displacement_verdict:UNPROVEN`, `physical_verdict:null` until the
corresponding real-world assumptions are independently established.

No `CHECKPOINT_REQUEST` is justified by this support-only change. After this
boundary is satisfied, the normal `AGENTS.md` trusted checkpoint mechanism is the
only path that may produce `TEST_REQUIRED`.