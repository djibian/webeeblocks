#!/usr/bin/env python3
"""Add Lab-only coherent pre-LPF acceleration and barometer log snapshots.

This diagnostic overlay targets one exact Crazyflie firmware source revision. It
changes observability only: estimator/controller equations, sensor configuration,
Flow/ToF behavior and motor authority are untouched.

The acceleration snapshot is taken after the existing scale + airframe/gravity
alignment and immediately before the 30 Hz software LPF. Timing names preserve
what is actually observed: gyroIrqUs is the low 32 bits of the gyro-DRDY ISR
clock, while accDoneUs is MCU time immediately after the accelerometer register
read. Neither is called an accelerometer producer timestamp.

The barometer snapshot retains the already-scaled value, MCU read/scale completion
time and Bosch chip id. It does not collapse BMP3xx conversion/IIR dynamics into
that CPU timestamp.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
EXPECTED_BLOB = "b183285c999335ca258b5131b1a835473473c078"
TARGET = Path("src/hal/src/sensors_bmi088_bmp3xx.c")
MARKER = "X3_PRELPF_SNAPSHOT_LOGGING_V1"

STATE_OLD = """static sensorData_t sensorData;
static volatile uint64_t imuIntTimestamp;

static Axis3i16 gyroRaw;
"""

STATE_NEW = """static sensorData_t sensorData;
static volatile uint64_t imuIntTimestamp;

// X3_PRELPF_SNAPSHOT_LOGGING_V1: Lab-only producer/readout provenance.
typedef struct
{
  Axis3f accPreLpf;
  uint32_t gyroIrqUs;
  uint32_t accDoneUs;
  uint32_t sequence;
} x3AccSnapshot_t;

typedef struct
{
  baro_t baro;
  uint32_t readDoneUs;
  uint32_t sequence;
  uint8_t chipId;
} x3BaroSnapshot_t;

static x3AccSnapshot_t x3AccProducer;
static x3AccSnapshot_t x3AccLatched;
static uint32_t x3AccLatchedPacketMs;
static bool x3AccLatchValid;

static x3BaroSnapshot_t x3BaroProducer;
static x3BaroSnapshot_t x3BaroLatched;
static uint32_t x3BaroLatchedPacketMs;
static bool x3BaroLatchValid;

static void x3LatchAccForPacket(uint32_t packetTimestampMs)
{
  if (!x3AccLatchValid || x3AccLatchedPacketMs != packetTimestampMs)
  {
    taskENTER_CRITICAL();
    x3AccLatched = x3AccProducer;
    taskEXIT_CRITICAL();
    x3AccLatchedPacketMs = packetTimestampMs;
    x3AccLatchValid = true;
  }
}

static void x3LatchBaroForPacket(uint32_t packetTimestampMs)
{
  if (!x3BaroLatchValid || x3BaroLatchedPacketMs != packetTimestampMs)
  {
    taskENTER_CRITICAL();
    x3BaroLatched = x3BaroProducer;
    taskEXIT_CRITICAL();
    x3BaroLatchedPacketMs = packetTimestampMs;
    x3BaroLatchValid = true;
  }
}

static float x3LogAccX(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccForPacket(timestamp);
  return x3AccLatched.accPreLpf.x;
}

static float x3LogAccY(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccForPacket(timestamp);
  return x3AccLatched.accPreLpf.y;
}

static float x3LogAccZ(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccForPacket(timestamp);
  return x3AccLatched.accPreLpf.z;
}

static uint32_t x3LogGyroIrqUs(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccForPacket(timestamp);
  return x3AccLatched.gyroIrqUs;
}

static uint32_t x3LogAccDoneUs(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccForPacket(timestamp);
  return x3AccLatched.accDoneUs;
}

static uint32_t x3LogAccSequence(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccForPacket(timestamp);
  return x3AccLatched.sequence;
}

static float x3LogBaroAsl(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroForPacket(timestamp);
  return x3BaroLatched.baro.asl;
}

static float x3LogBaroPressure(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroForPacket(timestamp);
  return x3BaroLatched.baro.pressure;
}

static float x3LogBaroTemperature(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroForPacket(timestamp);
  return x3BaroLatched.baro.temperature;
}

static uint32_t x3LogBaroDoneUs(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroForPacket(timestamp);
  return x3BaroLatched.readDoneUs;
}

static uint32_t x3LogBaroSequence(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroForPacket(timestamp);
  return x3BaroLatched.sequence;
}

static uint8_t x3LogBaroChipId(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroForPacket(timestamp);
  return x3BaroLatched.chipId;
}

static logByFunction_t x3AccXLogger = { .aquireFloat = x3LogAccX, .data = NULL };
static logByFunction_t x3AccYLogger = { .aquireFloat = x3LogAccY, .data = NULL };
static logByFunction_t x3AccZLogger = { .aquireFloat = x3LogAccZ, .data = NULL };
static logByFunction_t x3GyroIrqLogger = { .acquireUInt32 = x3LogGyroIrqUs, .data = NULL };
static logByFunction_t x3AccDoneLogger = { .acquireUInt32 = x3LogAccDoneUs, .data = NULL };
static logByFunction_t x3AccSeqLogger = { .acquireUInt32 = x3LogAccSequence, .data = NULL };
static logByFunction_t x3BaroAslLogger = { .aquireFloat = x3LogBaroAsl, .data = NULL };
static logByFunction_t x3BaroPressureLogger = { .aquireFloat = x3LogBaroPressure, .data = NULL };
static logByFunction_t x3BaroTemperatureLogger = { .aquireFloat = x3LogBaroTemperature, .data = NULL };
static logByFunction_t x3BaroDoneLogger = { .acquireUInt32 = x3LogBaroDoneUs, .data = NULL };
static logByFunction_t x3BaroSeqLogger = { .acquireUInt32 = x3LogBaroSequence, .data = NULL };
static logByFunction_t x3BaroChipLogger = { .acquireUInt8 = x3LogBaroChipId, .data = NULL };

static Axis3i16 gyroRaw;
"""

READ_OLD = """      sensorsGyroGet(&gyroRaw);
      sensorsAccelGet(&accelRaw);

      /* calibrate if necessary */
"""
READ_NEW = """      sensorsGyroGet(&gyroRaw);
      sensorsAccelGet(&accelRaw);
      const uint32_t x3AccReadDoneUs = usecTimestamp();

      /* calibrate if necessary */
"""

ACC_OLD = """      sensorsAlignToAirframe(&accScaledIMU, &accScaled);
      sensorsAccAlignToGravity(&accScaled, &sensorData.acc);
      applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);
"""
ACC_NEW = """      sensorsAlignToAirframe(&accScaledIMU, &accScaled);
      sensorsAccAlignToGravity(&accScaled, &sensorData.acc);

      // Preserve calibrated/aligned specific force before the 30 Hz software LPF.
      taskENTER_CRITICAL();
      x3AccProducer.accPreLpf = sensorData.acc;
      x3AccProducer.gyroIrqUs = (uint32_t)sensorData.interruptTimestamp;
      x3AccProducer.accDoneUs = x3AccReadDoneUs;
      x3AccProducer.sequence++;
      taskEXIT_CRITICAL();

      applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);
"""

BARO_OLD = """        bmp3_get_sensor_data(sensor_comp, &data, &bmp3xxDev);
        sensorsScaleBaro(baro388, data.pressure, data.temperature);

        measurement.type = MeasurementTypeBarometer;
"""
BARO_NEW = """        bmp3_get_sensor_data(sensor_comp, &data, &bmp3xxDev);
        sensorsScaleBaro(baro388, data.pressure, data.temperature);
        const uint32_t x3BaroReadDoneUs = usecTimestamp();

        taskENTER_CRITICAL();
        x3BaroProducer.baro = sensorData.baro;
        x3BaroProducer.readDoneUs = x3BaroReadDoneUs;
        x3BaroProducer.sequence++;
        x3BaroProducer.chipId = bmp3_chip_id;
        taskEXIT_CRITICAL();

        measurement.type = MeasurementTypeBarometer;
"""

LOG_OLD = """LOG_GROUP_STOP(gyro)
#endif

PARAM_GROUP_START(imu_sensors)
"""
LOG_NEW = """LOG_GROUP_STOP(gyro)
#endif

// X3 Lab diagnostic blocks. Configure each group as one log block to retain
// packet-scoped latch coherence. Payloads are 24 bytes (acc) and 21 bytes (baro).
LOG_GROUP_START(x3Acc)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, preX, &x3AccXLogger)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, preY, &x3AccYLogger)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, preZ, &x3AccZLogger)
LOG_ADD_BY_FUNCTION(LOG_UINT32, gyroIrqUs, &x3GyroIrqLogger)
LOG_ADD_BY_FUNCTION(LOG_UINT32, accDoneUs, &x3AccDoneLogger)
LOG_ADD_BY_FUNCTION(LOG_UINT32, seq, &x3AccSeqLogger)
LOG_GROUP_STOP(x3Acc)

LOG_GROUP_START(x3Baro)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, asl, &x3BaroAslLogger)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, press, &x3BaroPressureLogger)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, temp, &x3BaroTemperatureLogger)
LOG_ADD_BY_FUNCTION(LOG_UINT32, readDoneUs, &x3BaroDoneLogger)
LOG_ADD_BY_FUNCTION(LOG_UINT32, seq, &x3BaroSeqLogger)
LOG_ADD_BY_FUNCTION(LOG_UINT8, chipId, &x3BaroChipLogger)
LOG_GROUP_STOP(x3Baro)

PARAM_GROUP_START(imu_sensors)
"""

REPLACEMENTS = (
    ("snapshot state and log functions", STATE_OLD, STATE_NEW),
    ("accelerometer CPU read completion", READ_OLD, READ_NEW),
    ("pre-LPF acceleration snapshot", ACC_OLD, ACC_NEW),
    ("barometer read/update snapshot", BARO_OLD, BARO_NEW),
    ("function-backed log groups", LOG_OLD, LOG_NEW),
)

REQUIRED_APPLIED = (
    MARKER,
    "x3AccProducer.accPreLpf = sensorData.acc;",
    "x3AccProducer.gyroIrqUs = (uint32_t)sensorData.interruptTimestamp;",
    "x3AccProducer.accDoneUs = x3AccReadDoneUs;",
    "x3BaroProducer.chipId = bmp3_chip_id;",
    "LOG_GROUP_START(x3Acc)",
    "LOG_GROUP_START(x3Baro)",
    "LOG_ADD_BY_FUNCTION(LOG_UINT32, gyroIrqUs, &x3GyroIrqLogger)",
    "LOG_ADD_BY_FUNCTION(LOG_UINT8, chipId, &x3BaroChipLogger)",
)


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def state(text: str) -> str:
    if MARKER in text:
        missing = [item for item in REQUIRED_APPLIED if text.count(item) != 1]
        if missing:
            raise SystemExit(
                "partial/corrupt X3 pre-LPF diagnostic application: "
                + ", ".join(missing)
                + "; no file written"
            )
        for label, old, _new in REPLACEMENTS:
            if text.count(old):
                raise SystemExit(f"{label}: old anchor survived applied state; no file written")
        return "applied"

    blob = git("hash-object", str(TARGET))
    if blob != EXPECTED_BLOB:
        raise SystemExit(
            f"unexpected pristine target blob {blob}; expected {EXPECTED_BLOB}; no file written"
        )
    for label, old, new in REPLACEMENTS:
        if text.count(old) != 1 or text.count(new) != 0:
            raise SystemExit(f"{label}: exact anchor mismatch; no file written")
    return "applicable"


def require_context(text: str) -> str:
    if git("rev-parse", "HEAD") != EXPECTED_COMMIT:
        raise SystemExit("wrong upstream commit; no file written")
    return state(text)


def transform(text: str) -> str:
    current = require_context(text)
    if current == "applied":
        return text
    transformed = text
    for _label, old, new in REPLACEMENTS:
        transformed = transformed.replace(old, new, 1)
    if state(transformed) != "applied":
        raise SystemExit("X3 pre-LPF diagnostic postcondition failed; no file written")
    return transformed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if not TARGET.is_file():
        raise SystemExit(f"missing target: {TARGET}")
    original = TARGET.read_text(encoding="utf-8")
    current = require_context(original)
    transformed = transform(original)

    if args.check:
        print(f"X3 pre-LPF snapshot logging: {current}")
        return
    if transformed == original:
        print("X3 pre-LPF snapshot logging already applied; no file written")
        return

    TARGET.write_text(transformed, encoding="utf-8")
    print(
        "Applied X3 pre-LPF snapshot logging: coherent packet-latched acceleration "
        "and barometer diagnostics only"
    )


if __name__ == "__main__":
    main()
