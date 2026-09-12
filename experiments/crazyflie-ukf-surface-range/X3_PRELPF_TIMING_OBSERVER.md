# X3 logging-only independent-input observer

This Lab-only observer narrows one provenance gap in #70. It targets exact Crazyflie firmware `2026.08@54f31e243a0b28b67efef5ba20dbb6d9890a5478` and is compiled only through a dedicated diagnostic path. It changes no estimator/controller equation, ToF/Flow behavior, S3 threshold or persistence, parameter, Runtime behavior, checkpoint profile or motor authority.

## Why a separate observer is needed

The existing `acc.x/y/z` logs expose `sensorData.acc` after the Crazyflie 30 Hz second-order accelerometer LPF. The pinned firmware configures BMI088 gyro DRDY on its INT3 path, listens on STM32 `PC14` / `EXTI14`, and stores the callback time in `sensorData.interruptTimestamp`. However, the published Crazyflie 2.1 Rev.B schematic routes STM32 `PC14` (`INT_GYR`) to BMI088 package pin 1 / `INT2`; Bosch BMI088 datasheet rev 1.9 defines pin 1 / INT2 as an **accelerometer** interrupt and pin 12 / INT3 as a **gyroscope** interrupt, with Rev.B showing INT3 unconnected. Until the exact production-board wiring/revision is reconciled with that firmware configuration, the electrical source of `sensorData.interruptTimestamp` is **UNPROVEN**. `stabilizer.intToOut` is therefore diagnostic only relative to the firmware interrupt timestamp; it is not a proven gyro- or accelerometer-producer timestamp.

The same Rev.B schematic exposes BMI088 pin 16 / INT1 (`INT_ACC`) on STM32 `PC13`, but the pinned implementation does not configure an accelerometer DRDY interrupt or route `EXTI13` into the sensor callback. That wiring is a possible future investigation, not evidence that an accelerometer producer timestamp already exists. The Bosch driver also exposes a 24-bit accelerometer sensor-time counter, but the inspected public semantics do not establish that a separately read counter value is the production timestamp of the XYZ registers. This observer deliberately does not rename either clock into producer time or alter the sensor bus read to manufacture that relation.

## Recorded snapshots

The applicator adds two log groups to `src/hal/src/sensors_bmi088_bmp3xx.c`.

`x3AccObs` is captured after the current scale/airframe/gravity alignment and **before** `applyAxis3fLpf()`:

| field | type | meaning |
| --- | --- | --- |
| `x/y/z` | float | aligned, gravity-corrected acceleration in the current firmware units, before its 30 Hz software LPF |
| `seq` | uint32 | monotonically incremented firmware snapshot sequence |
| `readBeg` | uint32 | low 32 bits of `usecTimestamp()` immediately before the accelerometer register read; on pinned 2026.08 this counter has the known TIM7 84/85 nominal-rate defect described below |
| `readEnd` | uint32 | low 32 bits of `usecTimestamp()` immediately after that read returns; same clock semantics as `readBeg` |

The log payload is 24 bytes. `readBeg/readEnd` bound a CPU-side register-read window. They are not accelerometer sample-production timestamps and, on the pinned firmware, their raw deltas are not true elapsed microseconds without the clock-scale correction below.

`x3BaroObs` is captured after `bmp3_get_sensor_data()` and `sensorsScaleBaro()`:

| field | type | meaning |
| --- | --- | --- |
| `asl/pressure/temp` | float | one scaled barometer snapshot |
| `seq` | uint32 | monotonically incremented firmware snapshot sequence |
| `readBeg/readEnd` | uint32 | low 32 bits of the same `usecTimestamp()` counter around `bmp3_get_sensor_data()` |
| `chipId` | uint8 | exact runtime `bmp3_chip_id` (BMP388 or BMP390 identity) |

The log payload is 25 bytes. The CPU read window does not remove BMP3xx conversion, oversampling or IIR response uncertainty.

## Pinned `usecTimestamp()` clock-scale erratum

Upstream PR [bitcraze/crazyflie-firmware#1684](https://github.com/bitcraze/crazyflie-firmware/pull/1684) is based exactly on the firmware commit pinned here, `54f31e243a0b28b67efef5ba20dbb6d9890a5478`. That source programs TIM7 with
`TIM_Prescaler = SystemCoreClock / (1000 * 1000) / 2`. On the CF2 timer clock this writes PSC=84, while the STM32 timer divides by PSC+1. The nominal `usecTimestamp()` counter therefore advances at `84/85` of the intended 1 MHz rate. PR #1684 repairs the one line by subtracting one from the programmed prescaler. Its exact current head `bb58cadfa348f903e4e8e6995a5557c42cd5754d` remains upstream/open as of 2026-09-12, but has two upstream approvals; one review independently quantified the old timing behavior and the expected Flow-deck/high-level-command consequences.

For a modular interval formed from this counter on the unchanged pinned firmware, the deterministic prescaler correction alone is therefore:

`nominal_real_interval = raw_usecTimestamp_delta * 85 / 84`

This correction is only the digital divider ratio. It does not establish absolute clock accuracy: STM32 oscillator accuracy/drift remains separate, as do interrupt-source, sensor-producer, filter, bus-read and scheduling uncertainties. In particular, it does not rehabilitate `sensorData.interruptTimestamp` or justify a smaller `sensor_time_error_s`.

The normal wireless log packet timestamp is a different clock path based on the FreeRTOS logging timestamp and is not converted by this rule. A later analysis must never compare these clocks as though they shared an already-proven common real-time scale or producer epoch merely because both are numeric timestamps.

## Row coherence

Ordinary log variables are copied sequentially by the low-priority log worker and can otherwise mix adjacent sensor-task updates. These groups use `LOG_ADD_BY_FUNCTION`. The pinned logging worker passes the same log-packet timestamp to every function-backed field in one configured log block. The first callback for a new packet timestamp copies one producer-loop snapshot into a latch; all later fields in that same block return that same latch.

**A retained observer row is coherent only when all fields of the corresponding `x3AccObs` or `x3BaroObs` group are requested together in one log block.** Splitting one logical row across multiple log blocks does not inherit the packet-scoped coherence claim and must fail closed in any future capture path that relies on this observer.

Snapshot publication and latch copying are each protected by one short FreeRTOS critical section. Sensor I/O is outside those critical sections. A repeated millisecond packet timestamp may reuse the previous coherent latch, which is detectable through `seq`; it cannot create a mixed row inside one complete observer block. This is a logging-coherence property, not a producer-time claim.

The deterministic observer contract test exercises the applicator's exact transformation, pre-LPF placement, packet-timestamp latch wiring, callback-to-latch field bindings, fail-closed partial-application behavior and 24/25-byte payload budgets.

## Separate diagnostic build oracle

The existing `run_s3_build_oracle.sh` and its `experimental-s3-surface-offset-2026-08` artifact remain unchanged and retain their existing `s3-props-off` checkpoint identity.

`run_x3_prelpf_build_oracle.sh` operates on a **separate pinned firmware checkout**. It first invokes the unchanged canonical S3 oracle in that diagnostic checkout to establish the same UKF/S3 build configuration, then verifies the exact pinned sensor blob, runs the observer contract test, applies only the X3 logging overlay, runs `git diff --check`, verifies the expected declarations and pre-LPF placement, and recompiles CF2. The diagnostic binary must differ from the pre-observer S3 binary in that isolated checkout.

The existing canonical `.github/workflows/ci.yml` `Select suites` job runs this bounded X3 diagnostic for relevant observer/S3 changes, using its own pinned Crazyflie checkout. It retains only build logs, source patches, upstream SHA and binary/ELF hashes under the distinct artifact name `x3-prelpf-observer-build-evidence-2026-08`; it deliberately does **not** publish `cf2.bin` or reuse any trusted checkpoint artifact identity. The separate `ci-webots.yml` S3 job and its `experimental-s3-surface-offset-2026-08` checkpoint artifact remain unchanged.

This diagnostic build proves compilation only. It does not replace the exact #251 physical artifact, enable `x3-independent-props-off`, request a checkpoint, validate live log throughput, or establish a frozen-predictor bound. Any future physical use requires a separately identified instrumented firmware artifact and compatible trusted checkpoint provenance.

## Proof boundary

The low 32-bit `usecTimestamp()` counter wraps modulo 2^32; any later duration must first be computed with unsigned modular subtraction rather than ordinary signed ordering. On the pinned 2026.08 firmware, a raw modular delta must then account for the known 84/85 TIM7 rate defect before it is called a nominal elapsed microsecond interval. Oscillator accuracy and all sensor/producer timing uncertainty remain separate and are not removed by that deterministic correction.

No numeric value for `sensor_time_error_s`, `specific_force_error_g`, `intersample_acceleration_error_m_s2`, `barometer_displacement_error_m` or `delivery_latency_error_s` follows from this observer or from the TIM7 prescaler correction. Manufacturer typical/RMS values and nominal ODR are not deterministic bounds.

A later capture may use these fields only with their exact stated clock semantics. If the remaining producer/filter/physical-motion uncertainties cannot be pre-registered independently, the X3 independent-displacement result remains `UNPROVEN`. No `TEST_REQUIRED` or motorized action follows from integration.
