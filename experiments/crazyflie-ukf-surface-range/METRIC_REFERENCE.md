# Conditional X3 metric-reference envelopes

The acquisition and frozen pressure probe do not establish external vehicle-Z,
surface height or synchronized event boundaries. This offline component preserves
explicit annotations for that missing reference and computes their conditional
time/displacement envelopes. It supplies no new physical observation or predictor.

The reference can come from a fixed camera with a metric scale or a measured
guide and retained observation notes. Keep the raw witness files and identify
the exact frames/rows supporting each annotation. Vehicle Z and surface height
must share one metric datum. Neither UKF Z/VZ, S3 decisions nor a "recording ready"
message supplies this external reference. Declaring a file external is not proof
of its independence, resolution, timing, stillness or accuracy.

## Input contract

The schema is `webeeblocks.x3.metric-reference-input.v1`. All intervals are
explicit `[lower, upper]` arrays, including point observations `[value, value]`.
Each source entry has `id`, relative `path`, exact `sha256`, and `kind` equal to
`barometer-capture` or `external-metric-reference`. Sources stay inside the
specification directory and each file has one identity. A witness is
`{"source": "<external source id>", "locator": "<specific frames/rows>"}`.

The other fields are:

| Field | Required information |
| --- | --- |
| `clock.model` | Explicit `affine` assumption |
| `clock.device_origin` | `first-barometer-log-row`, matching the frozen pressure probe |
| `clock.barometer_source` | ID of the hash-checked continuous capture CSV |
| `clock.anchors` | At least two ordered, disjoint synchronization observations; each has `reference_s`, `device_s`, and `witness` |
| `calibration` | `start_reference_s`, `end_reference_s`, and a witness for the prior stationary interval |
| `events[]` | Unique `id`, descriptive `kind`, `start_reference_s`, `end_reference_s`, `z_after_hold_start_reference_s`, `z_after_hold_end_reference_s`, `z_before_m`, `z_after_m`, `surface_before_m`, `surface_after_m`, and `witness` |

Kinds are `stationary`, `terrain`, `vertical`, and `mixed`. They label results;
they do not select a different calculation or establish truth. Both signs of
terrain/vertical/mixed movement remain required by the physical protocol in
`X3_CHARACTERIZATION_PROCEDURE.md`. The synthetic `example()` in
`test_metric_reference.py` gives the complete input shape; its values and witness
text are not measurements or a prepared checkpoint.

The two `z_after_hold_*` fields are not another sensor. They are independent-clock
bounds for the beginning and end of a continuously observed guide interval during
which the same conservative `z_after_m` bound is asserted for the same vehicle
body reference. They exist only so the processor can prove that the physical Z
reference used for the temporal comparison actually spans the analyzed
post-transition window instead of coming from a later plateau reading.

## Computation

The device coordinate is elapsed log time, with the same 24-bit unwrap and CSV
integrity checks as the frozen pressure probe. Host receipt time is checked but
never substituted for it. Synchronization anchors must come from independently
retained observations linking the two clocks. Pairing a reference with an
arbitrary receipt timestamp does not establish a valid anchor or sensor timing.

For a positive affine clock `device = rate × reference + offset`, the first/last
anchor intervals bound a finite polygon of possible rate/offset pairs. Every
anchor intersects that polygon; inconsistent observations reject the input.
Extrema over its vertices preserve rate/offset correlation. Rational arithmetic
avoids a numerical tolerance silently admitting inconsistent anchors, and
floating result endpoints are rounded outward. Nothing is extrapolated beyond
the bracketing observations. Non-affine drift between anchors remains unproven.

Every admissible event must have positive duration, ordered two-second plateaus,
at least 30 seconds of prior calibration, and a post-window covered by the raw
recording. In addition, under **every** admissible affine clock, the declared
continuous vehicle-Z hold must start no later than `event_end + 0.25 s` and remain
valid through at least `event_end + 0.75 s`. Failure of either bound rejects the
input as `UNPROVEN` instead of allowing a late `z_after_m` observation to stand in
for the 1 s reference.

The output retains intervals for the fixed pressure probe's before/after window
starts and for the beginning/end of the declared vehicle-Z hold. It does not
choose timing midpoints or run a pressure calculation on an optimistically
selected alignment. A future consumer must account for the complete timing range.

The same interval subtraction produces signed reference Δz, Δh and Δclearance
for every kind. Shared measurement correlations can make these conservative
envelopes wider than necessary; no statistical independence or confidence level
is assumed. The mixed case retains separate vehicle and terrain movement.

```sh
python3 experiments/crazyflie-ukf-surface-range/test_metric_reference.py
python3 experiments/crazyflie-ukf-surface-range/metric_reference.py reference-input.json --output reference-result.json
```

Sources are read and hashed without alteration. The specification, source and
implementation digests are retained. Output creation is exclusive; incomplete or
inconsistent inputs fail closed and existing results are never overwritten.

## Proof boundary

`COMPUTED_CONDITIONAL` proves only the annotated interval calculation and the
temporal coverage of the supplied post-transition Z annotation. It does **not**
prove that the human/physical annotation is true. Every result retains
`physical_reference_validated:false`, `affine_clock_validated:false`,
`independent_displacement_verdict:UNPROVEN`, and `physical_verdict:null`.

The component neither measures the proposed bounds nor converts them into
acceptance authority. Physical guide accuracy/stillness, affine-clock adequacy,
sensor producer timing and the independent IMU/barometer predictor remain
separate evidentiary questions. An uncertainty interval crossing a predeclared
5 cm or 1 s quantity remains `UNPROVEN`.

The tests use synthetic data to check signed mixed movement, identical arithmetic
across labels, correlated clock bounds, inconsistent/ambiguous timing,
post-transition Z-window coverage, source integrity and exclusive output. No
real-device claim follows from them.

This supplies one reference-processing component. It does not prepare or request
a human checkpoint, change #251 firmware or parameters, alter CI/governance, or
implement another publication path. The integrated #296/#298 mechanism remains
the raw-publication path; its provenance also stays distinct from the owner-
authoritative physical verdict.
