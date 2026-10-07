# X3 checkpoint #561: bounded evidence and the next prerequisite

The [owner-authoritative FAIL](https://github.com/djibian/webeeblocks/issues/561#issuecomment-6041899860)
applies to exact target `4ca2d1e3b3556e98136c12b9d3522d8707144f03`,
profile `x3-independent-props-off`, requested by
[#70 comment 6021601354](https://github.com/djibian/webeeblocks/issues/70#issuecomment-6021601354).
The retained raw evidence is published in [#562](https://github.com/djibian/webeeblocks/pull/562)
under [checkpoint-561-4ca2d1e3b355](../experiments/crazyflie-ukf-surface-range/evidence/checkpoint-561-4ca2d1e3b355/).
Raw publication and its machine review do not change that human verdict.

## Established observations

`VERIFIED_BY_RETAINED_EVIDENCE`: the preparation record reached `PREPARED`,
with the exact bundled firmware digest, frozen four parameter values, fresh
`ukf.resetEstimation` request, observed firmware auto-clear, historical explicit
client release, fixed 5 s settle and a `HEALTHY` observation. The preparation
record copied into the stationary capture is byte-identical to the original.
Its Z observations were approximately -0.000300 to -0.000025 m while the device
was prepared at rest; those values are not a promise of later estimator health.

The stationary capture preserves 7,508 rows in each of pose, detector and
barometer, and 15,016 IMU rows. Device timestamps increase strictly; maximum
gaps are 20 ms for the three slower streams and 10 ms for IMU. Pose host-receipt
span is 150.035851647 s, while device timestamp span is 150.14 s; these are
different clocks, not interchangeable sensor producer timestamps.

| Stationary observation | Retained range |
| --- | --- |
| `stateEstimate.z` | 0.5901439189910889 to 0.6071823835372925 m |
| `stateEstimate.vz` | -0.041351187974214554 to +0.04144752025604248 m/s |
| Downward range | 588 to 614 mm |
| `surfState`, `surfReason`, `surfOffset` | 0 throughout |
| `flowLocal` | 1 throughout |

The capture result records no invalid rows. The operator independently reported
the stationary choreography/reference hold as conforming. This remains one
partial characterization capture, not a complete calibration/confirmation set.

`OWNER_REPORTED`, preserved in the failure record: before cycle 1 terrain
acquisition, the mandatory read-only health gate rejected
`stateEstimate.z=-2.814063310623169` outside the unchanged `[-1.0, 5.0]` bounds.
The terrain scientific collector never started; its reference file contains
only a header. No second preparation, retry or motorized action occurred.

## What the evidence cannot identify

No sensor trace in this evidence set spans the interval from the end of the
stationary capture to the failed pre-terrain gate. The initiating cause, exact
onset, intervening handling/surface geometry and estimator trajectory in that
interval remain `UNPROVEN`. The records do not establish that reconnect,
placement on the floor, a terrain transition or any individual sensor caused
the divergence. Nor does a transport-complete stationary capture establish
health during the following unobserved interval.

#550's missing fresh reset is therefore not an adequate explanation for #561:
the reset and a bounded stationary capture were established this time. The
pre-acquisition guard correctly refused continuation in a divergent state.
There is no evidence here to weaken that guard, widen its limits, tune the
firmware/classifier, or insert repeated resets between scientific trials.

## Decision consequence

#561 is resolved FAIL and no longer occupies the human-test slot. Its artifact,
request and approval cannot be reused for another attempt. X3 remains Lab-only;
terrain/true-vertical/mixed characterization and untouched confirmation are
still missing.

Before requesting another identical characterization, review the existing
preparation/acquisition lifecycle and establish a bounded diagnostic path that
can retain the previously unobserved stationary-to-next-capture interval. If
new physical observations are indispensable, their exact procedure/artifact
must be prepared and independently reviewed through the existing checkpoint
mechanism. Preserve the frozen firmware/configuration, original records,
all-trial retention, props-off/no-Commander boundary and unchanged health
guards. Do not infer a root cause or authorize a blind retry from this analysis.

This finding concerns X3 estimator characterization. It neither diagnoses the
separate motorized #554 failure nor supplies physical qualification for #157
or the final #72 activity.
