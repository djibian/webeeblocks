# X3 pre-LPF snapshot logging diagnostic

Status: **Lab-only support artifact** for #70. This is not checkpoint firmware,
not a physical verdict and not flight authority.

## Purpose

The frozen independent vertical predictor needs acceleration evidence whose
software semantics are explicit. The ordinary Crazyflie `acc.x/y/z` path is
scaled/aligned and then passed through a 30 Hz second-order firmware LPF. That
history is useful to flight control but makes an instantaneous-sample timing
claim inappropriate. The pinned BMI088 interrupt timestamp is also the gyro
DRDY ISR time, not an accelerometer producer timestamp.

This overlay therefore adds a narrower diagnostic on exact Crazyflie firmware
`54f31e243a0b28b67efef5ba20dbb6d9890a5478` without changing estimator or
controller equations:

- `x3Acc.preX/preY/preZ`: calibrated, airframe-aligned and gravity-aligned
  acceleration copied immediately **before** the existing 30 Hz software LPF;
- `x3Acc.gyroIrqUs`: low 32 bits of the existing gyro-DRDY ISR `usecTimestamp`;
- `x3Acc.accDoneUs`: MCU `usecTimestamp` immediately after the existing
  accelerometer register read returns;
- `x3Acc.seq`: producer snapshot sequence counter;
- `x3Baro.asl/press/temp`: the existing scaled barometer result;
- `x3Baro.readDoneUs`: MCU time immediately after the Bosch read plus Crazyflie
  scaling completes;
- `x3Baro.seq`: barometer snapshot sequence counter;
- `x3Baro.chipId`: exact linked Bosch `bmp3_chip_id` value (BMP388/BMP390
  identity when read from the instrumented firmware).

The overlay does not modify sensor ODR/bandwidth, the UKF, S3 classifier, Flow,
ToF, Runtime v2, commander behavior, parameters or motor authority.

## Coherence invariant

The Crazyflie logger invokes every `LOG_ADD_BY_FUNCTION` callback in one packet
with the same logger timestamp. Each X3 group uses that timestamp only as a
packet-latch key: the first callback for a new key copies one producer snapshot
under a short FreeRTOS critical section, and later callbacks for that key return
fields from the same latched copy. Producer writes use the same critical-section
mechanism, so a row cannot mix fields from two producer writes.

Configure each group as one log block. The complete `x3Acc` row is 24 bytes and
the complete `x3Baro` row is 21 bytes, both below the 26-byte log payload limit.
The two groups are independently latched; this mechanism does **not** claim that
an acceleration packet and a barometer packet are simultaneous.

A repeated logger timestamp can intentionally reuse the previous latch. That can
make a row older than the packet execution, but it remains internally coherent;
`seq` and the explicit device-clock observations must be retained so analysis can
identify repeated producer snapshots rather than invent freshness.

## Clock semantics

All `*Us` fields are low 32 bits of the Crazyflie `usecTimestamp()` device clock.
They wrap about every 71.6 minutes. Analysis must use unsigned modular arithmetic
and bounded capture windows.

`gyroIrqUs` is a **gyro data-ready interrupt witness**. It is not accelerometer
sample production time. `accDoneUs` is **MCU accelerometer read completion**. It
is not a Bosch ADC/sample timestamp. The BMI088 sensor-time counter is deliberately
not added here because the inspected public semantics do not prove that a
separately read counter value timestamps the XYZ sample, and reading it would add
a bus transaction with its own observer effect.

`x3Baro.readDoneUs` is **MCU barometer read/scale completion**. It does not identify
the effective pressure-conversion time. The already-established BMP3xx ×8/×1
conversion interval and coefficient-3 stateful IIR response remain a separate
scientific uncertainty and must continue to be covered by a conservative
barometer displacement/timing model.

## Deterministic build oracle

`run_x3_prelpf_snapshot_build_oracle.sh` fails closed unless:

1. the upstream checkout is exactly `54f31e243a0b28b67efef5ba20dbb6d9890a5478`;
2. `src/hal/src/sensors_bmi088_bmp3xx.c` is the exact pristine blob
   `b183285c999335ca258b5131b1a835473473c078`;
3. every source anchor appears exactly once;
4. the acceleration snapshot remains after calibration/alignment and before the
   30 Hz software LPF;
5. the barometer snapshot remains after the existing Bosch read + scaling path;
6. both producer writes and packet latches retain critical-section protection;
7. the complete diagnostic source builds as UKF-enabled CF2 firmware.

The oracle is intentionally separate from `run_s3_build_oracle.sh`. The exact
#251/S3 checkpoint artifact is not silently redefined by this diagnostic.

## Boundary before any physical use

A successful build proves only source applicability, internal row-coherence
mechanics and compilation. It does not choose or justify
`sensor_time_error_s`, `specific_force_error_g`,
`intersample_acceleration_error_m_s2`, or `barometer_displacement_error_m`.
It does not prove an accelerometer producer timestamp, instantaneous pressure,
world-Z accuracy, or terrain discrimination.

No checkpoint profile is enabled by this file. No flash, parameter change,
`TEST_REQUIRED` notification or motorized action follows from this diagnostic.
Any later physical capture must separately bind the exact built binary, hardware,
procedure, reference measurement and pre-registered numeric bounds before the
project can ask a human to execute a checkpoint.
