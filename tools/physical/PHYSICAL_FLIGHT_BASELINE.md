# Representative physical-flight admission baseline

This is a software admission boundary, not real-flight qualification, a flash
procedure or teacher authorization. X3's experimental #251 firmware/configuration
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

## Remaining preparation prerequisite

The gate alone does not provide reproducible restoration after X3. Before a new
representative checkpoint, deterministic preparation must include the exact
offline binary/provenance, an explicit props-off one-shot installation procedure,
the local digest and actual installation result, effective parameter readbacks,
and retained success/failure records. Wrong/missing binary, failed flash/readback,
existing output and interrupted preparation must fail closed without retry or
motor/arming commands. Post-reset checks must still reject stored overrides.
No ad hoc parameter tuning or inherited X3 configuration can replace that proof.

The physical qualification package currently does not supply that installation
step. Passing this metadata gate does not supply it either. Existing #566 remains
bound to its old exact target/artifact; this new software candidate cannot inherit
its acceptance or authorization. Any later changed physical procedure/artifact
must use independent review and the trusted checkpoint contract. No request,
retry, PASS or NOT_NEEDED is created by this document.
