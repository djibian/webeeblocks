# X3 logging-only independent-input observer

This Lab-only observer narrows one provenance gap in #70. It targets exact
Crazyflie firmware `2026.08@54f31e243a0b28b67efef5ba20dbb6d9890a5478`
on top of the existing S3/discriminator/timing-observer source path. It changes no
estimator/controller equation, ToF/Flow behavior, S3 threshold or persistence,
parameter, Runtime behavior, checkpoint profile or motor authority.

## Why a separate observer is needed

The existing `acc.x/y/z` logs expose `sensorData.acc` after the Crazyflie 30 Hz
second-order accelerometer LPF. The retained `sensorData.interruptTimestamp` is
captured by the BMI088 **gyro** data-ready interrupt, not by an accelerometer
producer event. `stabilizer.intToOut` is therefore useful diagnostic evidence
relative to gyro DRDY but is not an accelerometer producer timestamp.

The Bosch driver also exposes a 24-bit accelerometer sensor-time counter, but the
inspected public semantics do not establish that a separately read counter value
is the production timestamp of the XYZ registers. This observer deliberately
does not rename any such clock into producer time or alter the sensor bus read to
manufacture that relation.

## Recorded snapshots

The applicator adds two log groups to
`src/hal/src/sensors_bmi088_bmp3xx.c`.

`x3AccObs` is captured after the current scale/airframe/gravity alignment and
**before** `applyAxis3fLpf()`:

| field | type | meaning |
| --- | --- | --- |
| `x/y/z` | float | aligned, gravity-corrected acceleration in the current firmware units, before its 30 Hz software LPF |
| `seq` | uint32 | monotonically incremented firmware snapshot sequence |
| `readBeg` | uint32 | low 32 bits of `usecTimestamp()` immediately before `bmi088_get_accel_data()` |
| `readEnd` | uint32 | low 32 bits of `usecTimestamp()` immediately after that read returns |

The log payload is 24 bytes. `readBeg/readEnd` bound a CPU-side register-read
window. They are not accelerometer sample-production timestamps.

`x3BaroObs` is captured after `bmp3_get_sensor_data()` and
`sensorsScaleBaro()`:

| field | type | meaning |
| --- | --- | --- |
| `asl/pressure/temp` | float | one scaled barometer snapshot |
| `seq` | uint32 | monotonically incremented firmware snapshot sequence |
| `readBeg/readEnd` | uint32 | low 32 bits of CPU time around `bmp3_get_sensor_data()` |
| `chipId` | uint8 | exact runtime `bmp3_chip_id` (BMP388 or BMP390 identity) |

The log payload is 25 bytes. The CPU read window does not remove BMP3xx
conversion, oversampling or IIR response uncertainty.

## Row coherence

Ordinary log variables are copied sequentially by the low-priority log worker
and can otherwise mix adjacent sensor-task updates. These groups use
`LOG_ADD_BY_FUNCTION`. The pinned logging worker passes the same log-packet
timestamp to every function-backed field in one configured log block. The first
callback for a new packet timestamp copies one producer-loop snapshot into a
latch; all later fields in that same block return that same latch.

**A retained observer row is coherent only when all fields of the corresponding
`x3AccObs` or `x3BaroObs` group are requested together in one log block.** Splitting
one logical row across multiple log blocks does not inherit the packet-scoped
coherence claim and must fail closed in any future capture path that relies on
this observer.

Snapshot publication and latch copying are each protected by one short FreeRTOS
critical section. The critical sections copy only the small snapshot structures;
sensor I/O is outside them. A repeated millisecond packet timestamp may reuse the
previous coherent latch, which is detectable through `seq`; it cannot create a
mixed row inside one complete observer block. This is a logging-coherence
property, not a producer-time claim.

The deterministic observer contract test exercises the applicator's exact
transformation, pre-LPF placement, packet-timestamp latch wiring, all callback-to-
latch field bindings, fail-closed partial-application behavior and 24/25-byte
payload budgets.

## Build-oracle isolation

`run_s3_build_oracle.sh` preserves the existing checkpoint artifact workspace as
the authority boundary. It first performs the canonical S3/discriminator/timing
build in the original pinned Crazyflie checkout exactly as before. It records the
resulting canonical `cf2.bin` and `cf2.elf` hashes and verifies that the pinned
`sensors_bmi088_bmp3xx.c` source is still byte-identical and unmodified.

Only **after** that canonical build completes, the oracle copies the built
Crazyflie workspace to a temporary diagnostic directory. The X3 observer
contract test and applicator run only in that copied directory; the diagnostic
copy is rebuilt there and the linked ELF must contain the observer callbacks.
The diagnostic binary must differ from the canonical binary, while final
postconditions require the original canonical `cf2.bin`, `cf2.elf` and sensor
source hashes to remain unchanged. The temporary copy is then removed.

This isolation is deliberate because `.github/workflows/ci-webots.yml` packages
only the original checkout as `experimental-s3-surface-offset-2026-08`, and the
enabled `s3-props-off` human-checkpoint profile is bound to that existing artifact
identity. The observer diagnostic must never become that checkpoint firmware as a
side effect of this compile proof.

The isolated diagnostic rebuild is therefore only a CI compilation oracle. It is
not uploaded under the existing checkpoint artifact identity, does not replace
the exact #251 physical artifact, enable `x3-independent-props-off`, request a
checkpoint, validate live log throughput, or establish any frozen-predictor
bound. Any future physical use requires a separately identified instrumented
firmware artifact and compatible trusted checkpoint provenance.

## Proof boundary

The low 32-bit microsecond timestamps wrap modulo 2^32; any later duration must be
computed with unsigned modular subtraction rather than ordinary signed ordering.

No numeric value for `sensor_time_error_s`, `specific_force_error_g`,
`intersample_acceleration_error_m_s2`, `barometer_displacement_error_m` or
`delivery_latency_error_s` follows from this observer. In particular, manufacturer
typical/RMS values and nominal ODR are not deterministic bounds.

A later capture may use these fields only with their exact stated clock semantics.
If the remaining producer/filter/physical-motion uncertainties cannot be
pre-registered independently, the X3 independent-displacement result remains
`UNPROVEN`. No `TEST_REQUIRED` or motorized action follows from integration.
