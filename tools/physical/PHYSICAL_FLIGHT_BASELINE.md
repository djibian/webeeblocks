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
session factory rejects absent/malformed/wrong firmware metadata, a modified or
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
