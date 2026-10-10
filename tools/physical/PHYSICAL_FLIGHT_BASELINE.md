# Representative physical-flight admission baseline

This is a preparation/admission boundary, not real-flight qualification or
teacher authorization. X3's experimental #251 firmware/configuration
is a separate props-off subject and must not inherit flight admission.

## Pinned candidate

| Item | Value |
| --- | --- |
| Official release | Bitcraze `2026.08`, brushed Crazyflie 2.x `cf2` target |
| Source commit | `54f31e243a0b28b67efef5ba20dbb6d9890a5478` |
| Release binary | `cf2-2026.08.bin` |
| Binary SHA-256 | `9b745fe76da30e071ba8e04e6a8535d1dbd747d7ce6ca72d2d3ccf8c18978298` |
| Reported revision0 / revision1 | `0x54f31e24` / `0x3a0b` |
| Reported modified flag | `false` |
| Reported protocol | `12` |
| Effective `stabilizer.estimator` | `2`, extended Kalman |
| Effective `stabilizer.controller` | `1`, PID |

Source justification is bounded to the existing flat-floor #157 qualification:
the official release uses the same unmodified upstream source already inspected
by this project. Its Flow Deck V2 driver requires Kalman; its default controller
is PID. This selects an explicit conventional candidate instead of carrying X3's
experimental UKF/S3 configuration into representative flight. It does not prove
world altitude across furniture, tuning correctness or real-device reliability.

Primary sources at that exact commit:

- [official release and assets](https://github.com/bitcraze/crazyflie-firmware/releases/tag/2026.08);
- [firmware revision encoding](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/tools/make/versionTemplate.py);
- [Flow Deck estimator requirement](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/deck/drivers/src/flowdeck_v1v2.c);
- [effective estimator/controller parameters](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/stabilizer.c);
- [default PID controller](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/controller/controller.c).

The exact release asset was downloaded and independently hashed during source
preparation. No device was flashed or connected by that verification.

## Enforced scope

The read-only descriptor reports the observed firmware metadata and effective
estimator/controller parameters. It keeps `executionAuthority:false`; general
hardware capability observations do not themselves imply this flight baseline.
After the existing trusted STM+deck reset and new live connection, the powered-
session factory requires the exact reported release protocol `12` and rejects
absent/malformed/wrong firmware metadata, a modified or
unknown flag, or any estimator/controller outside the pinned pair before exact
preflight, supervisor postconditions or authority minting. It never repairs a
configuration by writing parameters. Teacher, watchdog, SafeLink, current-program,
acknowledgement, completion and recovery obligations remain independent.

Firmware revision parameters represent only a reported 48-bit source prefix and
modified flag. They are not cryptographic remote binary attestation. Configuration
values come from the parameter download of the newly established connection;
they are not a continuous integrity monitor or independently acknowledged writes.

## Packaged props-off preparation

The package includes the exact unmodified official binary, license and source
links; its manifest and provenance bind the binary digest. When a later exact
checkpoint explicitly requests this preparation:

1. Keep all four propellers removed. Verify the exact package and use its pinned
   Python 3.10/Linux x86-64 offline runtime; do not substitute X3's binary.
2. With the explicit URI, run once from the package root:
   `bash tools/physical/prepare_packaged_physical_flight.sh --uri radio://... --output ../flight-preparation --props-removed`.
   The output must be a new directory outside the manifest-covered package.
3. The helper verifies the local binary before hardware, installs that one binary
   through the existing warm STM32 bootloader path, opens a new bounded connection
   and requires exact Crazyflie 2.1 identity/protocol. It requests fresh typed
   firmware/configuration readbacks; it never writes estimator/controller
   parameters, stores parameters, arms, sends Commander or starts Webots.
4. Continue only after `preparation.json` says `PREPARED`. Retain start/result,
   available raw/typed readbacks and the causal error chain on failure/interruption.
   Stop at that failure, with no automatic retry. Unknown installation outcome
   is not proof that flashing failed or did not occur.
5. Only according to the independently requested human procedure, restore the
   propellers after complete preparation and zone checks, then use:
   `bash tools/physical/run_packaged_physical_qualification.sh --uri radio://... --preparation-record ../flight-preparation/preparation.json`.
   The runner verifies source SHA, URI, firmware identity/digest, typed readbacks
   and non-authority status without hardware, retains the verified record in its
   diagnostic log, then starts the existing host. The host still checks live
   firmware/configuration after its STM+deck reset before any flight authority
   or teacher decision. Stored overrides therefore fail closed too.

Wrong/missing binary, failed flash/readback, existing output and interruption
fail closed. No ad hoc tuning or inherited X3 configuration can replace proof.
The local installation result plus reported metadata are still not remote
binary attestation or a guarantee of subsequent estimator/vehicle health.

Existing #566 remains
bound to its old exact target/artifact; this new software candidate cannot inherit
its acceptance or authorization. Any later changed physical procedure/artifact
must use independent review and the trusted checkpoint contract. No request,
retry, PASS or NOT_NEEDED is created by this document.

## Range availability before takeoff

The dynamic trusted host now checks every syntactically demanded Multi-ranger
direction in the exact validated AST before emitting command 9. This read-only
check runs after the post-reset teacher decision, under the existing takeoff
effect exclusion. It requests the typed `uint16_t` filter readback and requires
the unchanged official `multiranger.filterMask=1`, opens each required range log,
and obtains one post-request, later-timestamp, same-epoch finite observation.
The PARAM reads use the existing never-reused absent-id receive fence and shared
Color LED epoch lock. The pinned cflib updater is excluded during each direct
READ; cached values, generic update callbacks and old target replies preceding
the fence cannot satisfy the exact five-byte typed response. An outstanding
updater request, malformed response, timeout or uncertain callback cleanup
poisons PARAM freshness for the epoch and vetoes takeoff. No X3 preparation,
configuration, reset or no-Commander teardown helper is used by admission.

The range observer retains the first qualifying post-request sample even when
several callbacks arrive before the waiting thread runs. Admission rejects a
reused firmware LOG block id and requires an exact same-epoch delete response
(success or already absent), with the unchanged 0.7 s observation deadline.
It keeps callbacks until that proof, attempts stop/delete once, and vetoes on
missing, rejected or malformed deletion evidence. A deletion reply proves the
stream absent; merely returning from cflib's asynchronous stop/delete is not
proof. It closes each observer once and rechecks the filter and current program
before
the existing fresh supervisor/SafeLink/acknowledgement gates. An unavailable first
sample, wrong binding, transport error or uncertain closure vetoes takeoff;
there is no wait-for-a-good-value loop. Programs without range demand require no
Multi-ranger observation. Both branches and nested expressions are included
conservatively; the check evaluates no expression and selects no student branch.

Successful ground observations appear in `HOST_RANGE_READINESS` with the exact
AST digest, epoch, direction, raw millimetres and LOG timestamp. This diagnostic
is non-authority. Ground values never become interpreter input: the existing
in-flight `readRange` still requests its own fresh log observation and rejects
all values >=8000, with terminal controlled recovery when independently eligible.
The admission check proves neither clearance nor future availability.

### Scientific boundary and shortest remaining qualification path

The original #572 archive has 200/200 finite stationary observations against
declared 0.50/1.00 m targets. Its procedural FAIL, absent geometry witnesses and
full transcripts remain unchanged; repeating those two stationary windows would
not isolate the effect of flight. #566 retains one unavailable in-flight front
value, but no target geometry or actual VL53L1 status. The failure therefore
cannot be attributed specifically to motors, vibration, power, geometry or a
permanent hardware defect.

At the pinned [Multi-ranger driver](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/deck/drivers/src/multiranger.c),
there is no supervisor/flight-state gate disabling ranging. Rejected sensor
statuses collapse to 32767; the float metres/millimetres round trip can produce
32766. The [ST API status mapping](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/lib/vl53l1/core/src/vl53l1_api.c)
distinguishes signal, sigma, bounds, hardware and other failures, but the public
`range.front` does not retain them. The driver's ignored I2C return statuses and
unbounded ready wait are additional source limitations, not established causes
of #566. The [LOG timestamp](https://github.com/bitcraze/crazyflie-firmware/blob/54f31e243a0b28b67efef5ba20dbb6d9890a5478/src/modules/src/log.c)
dates publication of stored values, not sensor production. Consequently advancing
LOG timestamps alone cannot rule out a stalled producer replaying a finite value.
Neither the readiness gate nor current flight completion proves that stronger
property. The [Bitcraze datasheet](https://www.bitcraze.io/documentation/hardware/multi_ranger_deck/multi_ranger_deck-datasheet.pdf)
specifies up to 4 m depending on surface/light; >=8000 is a decoding availability
boundary, not a validated 8 m sensing envelope. An empty ray is not certified
free space. No default/filter/timeout adjustment is justified by these records.

After exact-candidate CI and independent review, the smallest informative
**proposed**, separately owner-authorized physical acceptance is one representative
run over uniform, textured floor with the unchanged historical AST, a broad
fixed opaque front target at an independently measured finite distance (for
example 1.00 m), and sufficient target height/width to remain visible at takeoff
position and at the program's first 0.50 m-high range observation. Keep the target
out of the vehicle/recovery volume, retain its measured geometry and a continuous
external witness of vehicle/target, and use the exact prepared firmware/artifact.
The new ground admission result and the in-flight result then compare motor-off
and motorized observations in the same scene instead of comparing unrelated
scenes. The target/observer never changes the student AST or selects its branch.
An unavailable result ends that one run, with retained raw causal failure and
eligible controlled recovery; a success establishes only this witnessed domain
and exact run, not general reliability or every sensor/mission. Repeatability and
later #72 use require separately justified acceptance evidence.

No code/replay can supply the missing physical returns under real thrust, actual
target visibility or tracking/recovery errors. A further acquisition/flight is
therefore blocked pending an explicit owner decision and the exact trusted
checkpoint procedure. This proposal creates no CHECKPOINT_REQUEST, flight,
hardware manipulation, flash, PASS or retrospective qualification of #572.
