# X3 logging-only independent-input observer

This Lab-only observer narrows one provenance gap in #70. It targets exact Crazyflie firmware `2026.08@54f31e243a0b28b67efef5ba20dbb6d9890a5478` and is compiled only through a dedicated diagnostic path. It changes no estimator/controller equation, ToF/Flow behavior, S3 threshold or persistence, parameter, Runtime behavior, checkpoint profile or motor authority.

## Why a separate observer is needed

The existing `acc.x/y/z` logs expose `sensorData.acc` after the Crazyflie 30 Hz second-order accelerometer LPF. The retained `sensorData.interruptTimestamp` is captured by the BMI088 **gyro** data-ready interrupt, not by an accelerometer producer event. `stabilizer.intToOut` is therefore useful diagnostic evidence relative to gyro DRDY but is not an accelerometer producer timestamp.

The Bosch driver also exposes a 24-bit accelerometer sensor-time counter, but the inspected public semantics do not establish that a separately read counter value is the production timestamp of the XYZ registers. This observer deliberately does not rename such a clock into producer time or alter the sensor bus read to manufacture that relation.

## Recorded snapshots

The applicator adds two log groups to `src/hal/src/sensors_bmi088_bmp3xx.c`.

`x3AccObs` is captured after the current scale/airframe/gravity alignment and **before** `applyAxis3fLpf()`:

| field | type | meaning |
| --- | --- | --- |
| `x/y/z` | float | aligned, gravity-corrected acceleration in the current firmware units, before its 30 Hz software LPF |
| `seq` | uint32 | monotonically incremented firmware snapshot sequence |
| `readBeg` | uint32 | low 32 bits of `usecTimestamp()` immediately before the accelerometer register read |
| `readEnd` | uint32 | low 32 bits of `usecTimestamp()` immediately after that read returns |

The log payload is 24 bytes. `readBeg/readEnd` bound a CPU-side register-read window. They are not accelerometer sample-production timestamps.

`x3BaroObs` is captured after `bmp3_get_sensor_data()` and `sensorsScaleBaro()`:

| field | type | meaning |
| --- | --- | --- |
| `asl/pressure/temp` | float | one scaled barometer snapshot |
| `seq` | uint32 | monotonically incremented firmware snapshot sequence |
| `readBeg/readEnd` | uint32 | low 32 bits of CPU time around `bmp3_get_sensor_data()` |
| `chipId` | uint8 | exact runtime `bmp3_chip_id` (BMP388 or BMP390 identity) |

The log payload is 25 bytes. The CPU read window does not remove BMP3xx conversion, oversampling or IIR response uncertainty.

## Row coherence

Ordinary log variables are copied sequentially by the low-priority log worker and can otherwise mix adjacent sensor-task updates. These groups use `LOG_ADD_BY_FUNCTION`. The pinned logging worker passes the same log-packet timestamp to every function-backed field in one configured log block. The first callback for a new packet timestamp copies one producer-loop snapshot into a latch; all later fields in that same block return that same latch.

**A retained observer row is coherent only when all fields of the corresponding `x3AccObs` or `x3BaroObs` group are requested together in one log block.** Splitting one logical row across multiple log blocks does not inherit the packet-scoped coherence claim and must fail closed in any future capture path that relies on this observer.

Snapshot publication and latch copying are each protected by one short FreeRTOS critical section. Sensor I/O is outside those critical sections. A repeated millisecond packet timestamp may reuse the previous coherent latch, which is detectable through `seq`; it cannot create a mixed row inside one complete observer block. This is a logging-coherence property, not a producer-time claim.

The deterministic observer contract test exercises the applicator's exact transformation, pre-LPF placement, packet-timestamp latch wiring, callback-to-latch field bindings, fail-closed partial-application behavior and 24/25-byte payload budgets.

## Separate diagnostic build oracle

The existing `run_s3_build_oracle.sh` and its `experimental-s3-surface-offset-2026-08` artifact remain unchanged and retain their existing `s3-props-off` checkpoint identity.

`run_x3_prelpf_build_oracle.sh` operates on a **separate pinned firmware checkout**. It first invokes the unchanged canonical S3 oracle in that diagnostic checkout to establish the same UKF/S3 build configuration, then verifies the exact pinned sensor blob, runs the observer contract test, applies only the X3 logging overlay, runs `git diff --check`, verifies the expected declarations and pre-LPF placement, and recompiles CF2. The diagnostic binary must differ from the pre-observer S3 binary in that isolated checkout.

`.github/workflows/x3-prelpf-observer.yml` is a separate pull-request diagnostic workflow. It retains only build logs, source patches, upstream SHA and binary/ELF hashes under the distinct artifact name `x3-prelpf-observer-build-evidence-2026-08`; it deliberately does **not** publish `cf2.bin` or reuse any trusted checkpoint artifact identity.

This diagnostic build proves compilation only. It does not replace the exact #251 physical artifact, enable `x3-independent-props-off`, request a checkpoint, validate live log throughput, or establish a frozen-predictor bound. Any future physical use requires a separately identified instrumented firmware artifact and compatible trusted checkpoint provenance.

## Proof boundary

The low 32-bit microsecond timestamps wrap modulo 2^32; any later duration must be computed with unsigned modular subtraction rather than ordinary signed ordering.

No numeric value for `sensor_time_error_s`, `specific_force_error_g`, `intersample_acceleration_error_m_s2`, `barometer_displacement_error_m` or `delivery_latency_error_s` follows from this observer. Manufacturer typical/RMS values and nominal ODR are not deterministic bounds.

A later capture may use these fields only with their exact stated clock semantics. If the remaining producer/filter/physical-motion uncertainties cannot be pre-registered independently, the X3 independent-displacement result remains `UNPROVEN`. No `TEST_REQUIRED` or motorized action follows from integration.
