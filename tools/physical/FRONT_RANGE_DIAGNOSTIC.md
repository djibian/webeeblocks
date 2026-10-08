# Props-off front-range diagnostic after FAIL #566

This is a frozen machine-prepared observation procedure, not a checkpoint
request or permission to run hardware. Use only when a later trusted checkpoint
explicitly binds this procedure and its exact artifact. No flight, parameter
change, firmware installation, reset or retry occurs in this diagnostic.

## Why a raw observation is necessary

Owner-authoritative #566 FAIL on `cbe261729145fe966a9598139634cf673b97e41b`
retains `range.front=32766` at device timestamp 33205, epoch
`8cf54b41c90c5c55093321a4eafa58e6`, followed by positively recorded controlled
recovery landing. Its first execution moved the vehicle after PREPARE; its
subsequent manual retry remains diagnostic evidence and cannot become PASS.
No firmware/sensor physical cause for #554 follows from this result.

`VERIFIED_BY_CODE_INSPECTION`: pinned cflib
`45fdb784c9d13074c42835f3b5ac1d12133bf873` maps every raw value >=8000 to None.
The integrated observer preserves that availability boundary. It must not turn
32766 into a large numeric distance, infinity or proof of clearance.

At the reported official firmware source
`54f31e243a0b28b67efef5ba20dbb6d9890a5478`, `multiranger.c` uses 32767 when
the VL53L1 RangeStatus is excluded by `multiranger.filterMask` (default 1,
RANGE_VALID only). Its `/1000.0f` conversion followed by `range.c::rangeSet`
and uint16 assignment can produce 32766: binary32 arithmetic gives
32.766998291015625 m, then 32766.998046875 mm, truncated to 32766.
`INFERENCE`: #566 is consistent with this unavailable-status path. Actual
RangeStatus, filterMask, target geometry, occlusion and lighting were not
retained, so the initiating physical reason remains unknown. Presence/self-test
alone cannot establish a finite current return.

Primary source anchors:

- [Multi-ranger driver](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/deck/drivers/src/multiranger.c);
- [range storage/log types](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/range.c);
- [pinned cflib availability](https://github.com/bitcraze/crazyflie-lib-python/blob/45fdb784c9d13074c42835f3b5ac1d12133bf873/cflib/utils/multiranger.py).

## Exact observation boundary

The packaged command consumes this artifact's applicable PREPARED flight
restoration record. It verifies source SHA, URI, binary digest, exact metadata
and typed readbacks before hardware. It then opens one bounded one-shot link,
retains its live descriptor and fresh typed firmware/estimator/controller reads,
and requires the unchanged uint16 filterMask=1. No parameter writes or factory
authority/reset calls occur. A changed filter is rejected rather than repaired.

The actual production front log TOC must be uint16/<H. One 100 ms log stream
retains a fixed 10 s window with device timestamps and host receipt times.
The existing 0.7 s observer timeout bounds startup/stream gaps, and modular
24-bit timestamps must strictly advance. Malformed and unavailable raw rows are
written before interpretation. Unavailable is retained as diagnostic data;
it never becomes a numeric student distance. Transport, stale/malformed data,
write, log-stop/delete, close or interruption failures remain INCOMPLETE, with
partial evidence and causal errors, and do not cause reconnection or retry.
Connection/PARAM setup and teardown have no claimed sensor coverage. Late
callbacks cannot change sealed evidence; teardown bypasses normal Commander
close. Neither raw callback receipt nor its timestamp is a sensor-producer time.

OBSERVED means only that this raw capture completed. Its physical_verdict is
null, even when every return is unavailable. It does not qualify the sensor,
prove geometry, authorize a later motorized run or demonstrate continuous
availability. Independent actual geometry evidence is essential for interpreting
the trace; a predeclared geometry JSON alone cannot prove placement.

## Future human-owned procedure

1. Keep all four propellers removed throughout. Use only the later checkpoint's
   verified package and pinned Ubuntu/Python 3.10 runtime, together with its
   separately authorized successful official-flight preparation record. This
   command installs no firmware. Never substitute X3's experimental recipe.
2. Keep the vehicle stationary on a flat support; identify the physical front
   sensor and place a broad opaque flat target in front, centered on its height
   and line of sight. Start with an independently measured 0.50 m separation.
   Record actual target placement, sensor orientation, dimensions, ambient light
   and uncertainty (photo/video and ruler, without using the range reading as
   the measuring reference). Nothing moves during the 10 s window.
3. Save geometry outside the package, for example:
   `{"target_distance_m":0.50,"uncertainty_m":0.01,"method":"ruler plus retained side/front photographs"}`.
   The method must describe an actual witness, not promise one. Use a fresh
   output directory and retain all output, including incomplete observations:

   ```bash
   bash tools/physical/run_packaged_front_range_diagnostic.sh \
     --uri radio://... --preparation-record ../flight-preparation/preparation.json \
     --geometry ../front-geometry.json --output ../front-near --props-removed
   ```

4. At the first command/transport/retention error, stop without retry. If the
   later exact checkpoint prescribes both scenes and the first capture is
   OBSERVED, change only the target to independently measured 1.00 m and run
   its separately named geometry/output once. Do not silently omit unfavorable
   first-scene data. Two planned observations are distinct scene subjects, not
   retries after a failure; neither proves the interval between connections.
5. Retain preparation bytes/digest, geometry and actual independent witness,
   raw CSV, descriptor, partial raw and complete typed readbacks, start/result
   and all causal errors. Do not tune filterMask, deadlines, thresholds or
   sensor values. Inspect whether each scene produced finite returns compatible
   with its measured target; do not infer that an unavailable scene was clear
   or that a normal self-test proves the measurement.

Before any later representative flight request, resolve this availability/setup
boundary and bind a newly reviewed exact procedure. The vehicle must be in its
final takeoff position before reset/PREPARE and must not move afterwards.
Preserve exact AST/teacher/watchdog/current-program, no-retry and controlled-
recovery obligations. #566 stays historical FAIL; its artifact/approval cannot
authorize this changed subject. This document issues no human request or queue.
