# X3 acquisition lifecycle after checkpoint #561

Historical source subject: `main@cbe261729145fe966a9598139634cf673b97e41b`.
This bounded source review supplements the retained #561 evidence and does not
identify its initiating physical cause. #561 remains owner-authoritative FAIL;
no retry, scientific acceptance or physical execution is authorized here.

## Established lifecycle

`VERIFIED_BY_CODE_INSPECTION` of the exact source subject:

| Phase | Connection and observation boundary | Retained evidence |
| --- | --- | --- |
| Preparation | `configure_live()` opens one Crazyflie object, configures the frozen values, performs the single fresh reset, waits 5 s, collects the 2 s health window, then closes the object through `close_link_without_commander()` | `PREPARED` records reset and aggregate health evidence |
| Runner admission | `run_x3_independent_capture.sh` verifies the exact preparation record without hardware | A successful capture receives a copy of the verified preparation record |
| Live health gate | `verify_live_health()` opens another object, collects 2 s of pose observations and evaluates the unchanged bounds, then closes that object | Success prints aggregates; failure prints the exception. Raw health rows, device timestamps and receipt times are not written to files |
| Scientific capture | `record()` opens a third object, reads the four frozen parameters, starts the four log streams and records until its bounded deadline or failure | Raw CSVs and capture start/readiness/result files, including incomplete captures |
| Between captures | Logs stop and the capture object closes; the next runner invocation performs its own environment preparation, health connection and capture connection | No continuous sensor trace covers the operator interval, disconnected interval or the next connection setup |

The four logged scientific streams remain barometer, IMU, pose and S3 detector.
Their timestamps are firmware log/device and host receipt coordinates, not
per-sensor producer timestamps. The no-Commander close helper deliberately
closes the transport/incoming handler and makes the Crazyflie object one-shot.
Neither read-only health verification nor scientific capture resets the estimator
or writes its configuration. These facts establish acquisition boundaries;
they do not establish firmware state during a disconnected interval.

There is also a bounded evidence-retention gap: the shell runner uses `set -e`
and copies `preparation-record.json` only after the collector returns success.
A collector that creates incomplete raw output and exits nonzero therefore
retains its raw/result files but skips that preparation copy. This is separate
from #561's initiating failure: its completed stationary capture does retain a
byte-identical preparation copy, and its terrain collector never started.

The retention gap above is now repaired by integrated #565 at
`main@c63f91e693bbcb8e0d8515c81cf021130192f006`: every created capture directory
receives the verified preparation record and digest, including incomplete
captures, while collector failure stays nonzero and existing evidence cannot be
overwritten. The historical lifecycle review remains applicable to #561; the
other observation gaps and its unknown initiating cause remain unresolved.

Integrated #567 at `main@881a4d96a9374c16827788a496bee488ef2a488c` then
closes the bounded raw admission-health retention gap for future acquisitions.
The runner retains an exclusive sibling `<capture-output>.health` with exact
preparation bytes/digest, URI and frozen guard metadata, decoded raw values
(including missing/non-finite values), device timestamps and host receipt times,
followed by the health/error result. The rows are sealed before the unchanged
bounds are evaluated; evidence-write failure cannot admit scientific collection.
Failed, interrupted and incomplete health windows are retained without creating
a scientific capture. This repairs one observed window only: it neither
reconstructs #561 nor covers handling, disconnected time or connection setup
before that window.

Integrated #569 at `main@8797e5fa17e852c300b2a0b9734966c47990bba7`
adds the bounded interval diagnostic described in
[the diagnostic procedure](../experiments/crazyflie-ukf-surface-range/X3_INTERVAL_DIAGNOSTIC.md).
It records connected handling or a separate fixed-geometry reconnection contrast,
with per-epoch raw streams and explicit uncovered intervals. Its independently
reviewed startup/cleanup repair also closes the shared opening helper once on
interruption before ownership reaches the caller, retaining independent cleanup
uncertainty. These are machine preparation and lifecycle repairs, not new physical
observations: #561's missing trajectory and initiating cause remain unknown.
An actual independent geometry/time witness and a fresh trusted exact-artifact
request remain necessary; this document issues neither.

## Consequence for diagnosis

`INFERENCE`: a single passing preparation or stationary trace cannot establish
health through the lifecycle above. Another identical characterization could
again reject at the next gate without observing when divergence began. More
frequent aggregate gates alone would not reconstruct the missing trajectory.
Neither reconnect nor handling is proven to cause #561 by this source review.

The diagnostic requirements derived from this historical lifecycle are now
implemented by #569, subject to the physical-evidence boundary above:

1. the existing four raw streams continuously through a bounded stationary-to-
   next-position interval, with explicit phase markers and an independent record
   of vehicle/surface geometry; this tests handling while the connection stays
   live and must not be claimed to reproduce disconnected operation;
2. a separate, explicitly marked connection-lifecycle observation with the
   vehicle/surface held unchanged, raw last-before/first-after observations and
   connection/log start/stop events. The disconnected interval must remain an
   explicit coverage gap, never interpolated into proof;
3. the actual raw health window and its failure result through the integrated
   #567 sidecar, written before applying the unchanged bounds. Preserve that
   repair and the #565 exact preparation identity on successful and incomplete
   acquisitions alike rather than reimplementing either retention boundary.

Those contrasts are diagnostic evidence, not replacement characterization
trials. Their outcome must not select favorable scientific captures or introduce
resets between trials. Freeze the concrete sequence, durations, observations,
output schema and stop conditions before requesting physical information;
validate execution and failure retention without hardware first. Existing
stream deadlines and health bounds remain fail-closed. New raw observations can
narrow a cause only within their actual measured coverage.

Keep the exact #251 firmware, four parameter values, all original records,
props-off/no-Commander boundary and existing independent-reference contract.
Do not change estimator thresholds, Runtime, controller behavior or scientific
acceptance. Any later physical diagnostic needs an independently reviewed exact
artifact/procedure and the trusted checkpoint mechanism after reconstructing
the global human-test set. This source review creates no checkpoint request.

Source anchors: `tools/physical/prepare_x3_independent_capture.py`
(`configure_live`, `verify_live_health`, `collect_live_health`),
`tools/physical/run_x3_independent_capture.sh`,
`tools/physical/x3_no_commander_link.py`, and
`experiments/crazyflie-ukf-surface-range/capture_independent_inputs.py`
(`record`, `Recorder`).
