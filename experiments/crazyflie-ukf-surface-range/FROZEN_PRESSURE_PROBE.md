# Frozen descriptive pressure probe

This executes the pressure-only statistic specified by
[#70's architecture review](https://github.com/djibian/webeeblocks/issues/70#issuecomment-5606273253).
The archived-input audit establishes that the retained traces cannot supply its
continuous inputs. No new physical result is derived here. The probe is an
offline calculation component, not the complete IMU/barometer predictor or a
prepared checkpoint.

For every annotated stationary, terrain, vertical and mixed episode, the exact
same function computes `median(B+) - median(B-)`. B− is `[start−0.5, start)`;
B+ is `[end+0.25, end+0.75)`. There is no S3/UKF eligibility branch. Labels do not
change the computation; they do not establish physical truth. The statistic
uses raw firmware `baro.asl`, never UKF Z/VZ or an S3 conditional snapshot.

A centered least-squares line is fitted only to the supplied prior stationary
calibration of at least 30 s. Both the raw contrast and the comparison after
subtracting `slope × observed median-timestamp separation` are retained. This
uses the actual sampled times instead of assuming the sampling grid coincides
with nominal window centers. Event outcomes
cannot change that fit, the windows or any parameter.

Calibration comparisons use the same window width and separation as each event.
Their complete before/after spans do not overlap. Every pair and its signed
residual remain in the output. The residual extrema describe only this finite
calibration: non-overlap does **not** prove independence, and low-rate drift and
sensor autocorrelation remain relevant. Pair count is not an effective
independent sample count. No Gaussian error, standard error, 95/99% confidence
or future uncertainty bound is inferred from these counts/extrema. The effective
count and predictive bound stay null and the scientific result stays UNPROVEN.

## Inputs and execution

The specification is a JSON file with this shape (times and names are illustrative,
not measured data):

```json
{
  "schema": "webeeblocks.x3.pressure-probe-input.v1",
  "barometer": {"path": "barometer.csv", "sha256": "<exact 64-hex digest>"},
  "calibration": {"start_s": 0, "end_s": 30},
  "events": [
    {"id": "terrain-entry", "kind": "terrain", "start_s": 34, "end_s": 35}
  ]
}
```

The CSV columns are `cf_timestamp_ms,host_monotonic_s,baro.asl,baro.pressure,baro.temp`.
Additional columns are not used. Time zero is the first barometer device log
timestamp, with genuine forward 24-bit wraps unwrapped; the host clock is retained
and checked but never substituted for device time. Physical event annotations
must later come from an independently synchronized reference. Startup/readiness
or S3 decisions do not supply those boundaries.

```sh
python3 experiments/crazyflie-ukf-surface-range/test_frozen_pressure_probe.py
python3 experiments/crazyflie-ukf-surface-range/frozen_pressure_probe.py input.json --output pressure-result.json
```

The file entry point verifies the exact input digest and confines the input path
to the specification directory, preserves source bytes, fingerprints the script
and specification and creates a new result file exclusively. Empty/non-finite
inputs, ambiguous timestamps, receipt-clock reversal, gaps over 40 ms, windows
with fewer than 20 rows per 0.5 s or edge coverage worse than 40 ms fail closed.
These fixed checks establish minimal sampled-window coverage, not sensor producer
cadence or independent observations. Episodes must be ordered, with at least 2 s
between calibration/episodes; the physical stillness of these plateaus is not
verified by arithmetic. No missing sample is synthesized.

The synthetic tests establish signed arithmetic, identical paths for all labels,
calibration isolation from changed terrain values, matched non-overlapping pairs,
input integrity and rejection of missing coverage/clock errors. They are local
component tests, not a new CI or physical oracle.

## Remaining scientific boundary

`COMPUTED` establishes only that this descriptive calculation ran. Every result
keeps `independent_displacement_verdict: UNPROVEN` and `physical_verdict: null`.
The end+0.75 s window endpoint is not an end-to-end latency measurement. In
particular, this component neither compares an independent metric Z reference,
integrates IMU signals nor computes/validates terrain Δh.

Before any new checkpoint, the complete preparation still needs the exact
acquisition/runtime, synchronized metric reference and annotations, an executable
independent predictor with its validity/uncertainty limits, and durable raw
publication. Faithful inertial replay requires verified producer timing, bias and
attitude treatment; log receipt times and ToF-derived estimator outputs cannot
silently fill those gaps. Failure of this frozen probe must not trigger a search
for windows tuned to the same terrain outcomes. Preserve the #251 firmware and
parameters, the Flow local-range split and the props-off boundary.
