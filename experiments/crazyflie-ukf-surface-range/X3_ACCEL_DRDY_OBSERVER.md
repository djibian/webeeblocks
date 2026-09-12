# X3 BMI088 accelerometer data-ready provenance observer

This diagnostic-only X3 overlay narrows one timing/provenance question from #70.
It does **not** change the estimator/controller/Flow/S3 equations, does not enable
a physical checkpoint, and does not turn an MCU interrupt timestamp into sensor
producer time.

## Exact source and purpose

The overlay targets Crazyflie firmware
`2026.08@54f31e243a0b28b67efef5ba20dbb6d9890a5478` after
`apply_x3_prelpf_timing_observer.py` has been applied.

The pinned operational BMI088 path configures gyro data-ready on BMI088 INT3 but
waits on STM32 PC14/EXTI14. Published Crazyflie 2.1 Rev.B hardware documentation
instead labels PC14/`INT_GYR` on BMI088 pin 1 (INT2, an accelerometer interrupt
pin) and leaves the BMI088 gyro INT3 pin unconnected. Consequently the electrical
source of the operational `sensorData.interruptTimestamp` remains `UNPROVEN`.

This overlay therefore creates a **separate observation path** whose source is
explicit in both firmware configuration and the published schematic:

- configure BMI088 accelerometer data-ready on **INT1**;
- observe the published INT1 → STM32 **PC13 / EXTI13** route;
- increment only a diagnostic sequence and timestamp in the EXTI13 ISR;
- do **not** notify, wake, yield to, or otherwise retime the existing sensor task;
- retain the operational PC14 path unchanged.

The isolated diagnostic build is deliberately CF21/BMI088-only. It disables the
legacy `CONFIG_SENSORS_MPU9250_LPS25H` implementation because that implementation
owns a strong `EXTI13_Callback` for Crazyflie 2.0. This avoids silently replacing
or multiplexing a legacy production interrupt path merely to obtain diagnostic
evidence. The canonical S3 build/artifact remains unchanged.

## Observed fields

The existing `x3AccObs` group still contains the aligned/gravity-corrected
pre-30-Hz-LPF acceleration, firmware sequence, and CPU register-read window.

The new `x3AccDrdy` group contains five `uint32_t` fields (20-byte payload):

- `accSeq`: the matching `x3AccObs.seq`;
- `irqBeg`: latest accelerometer-DRDY interrupt sequence observed immediately
  before the accelerometer register read;
- `irqUsBeg`: low 32 bits of its MCU `usecTimestamp()`;
- `irqEnd`: interrupt sequence observed immediately after that register read;
- `irqUsEnd`: low 32 bits of its MCU timestamp.

Each group is packet-latched through `LOG_ADD_BY_FUNCTION`; `accSeq` is the
cross-group join key. A row with `irqBeg != irqEnd` is timing-ambiguous because a
new accelerometer DRDY arrived during the CPU read and must not be promoted into
a producer-timing calibration point. Equality means only that no observed PC13
DRDY edge arrived during that CPU read. It does **not** prove the BMI088 internal
filter/sample production instant, interrupt latency, or a deterministic
`sensor_time_error_s`.

The extra EXTI13 ISR itself adds CPU load and can perturb timing. Any later
physical use must retain that instrumentation effect in its uncertainty model.

## Deterministic build oracle

`run_x3_prelpf_build_oracle.sh`:

1. verifies the exact pinned upstream commit/source;
2. runs the existing pre-LPF observer contract tests and the new DRDY tests;
3. builds the unchanged canonical S3 artifact first and records its binary hash;
4. applies the pre-LPF observer, then this DRDY overlay;
5. switches only the isolated diagnostic build to CF21/BMI088-only sensor
   support (`CONFIG_SENSORS_BMI088_BMP3XX=y`,
   `CONFIG_SENSORS_MPU9250_LPS25H=n`);
6. rebuilds and checks the PC13 observer/log symbols and configuration;
7. requires the diagnostic binary hash to differ from the canonical S3 binary.

CI retains source patches, the final diagnostic `.config`, hashes and build log.
The flashable binary is not a checkpoint artifact.

## Boundary

A future physical observation in which `irqBeg/irqEnd` advance coherently would
establish that the **instrumented unit** produced observable PC13 edges after the
firmware explicitly mapped BMI088 accelerometer DRDY to INT1. It would not
rehabilitate the operational PC14 timestamp, prove board net continuity outside
that observed path, remove BMI088 internal filter/group-delay uncertainty, or
validate any frozen-predictor bound.

No `TEST_REQUIRED`, flash, reset, parameter write, commander action, motorized
test, threshold tuning, or world-altitude capability claim follows from this
support slice alone.
