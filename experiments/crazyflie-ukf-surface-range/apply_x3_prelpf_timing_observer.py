#!/usr/bin/env python3
"""Add logging-only X3 pre-LPF sensor read-window observability.

This applicator targets exact Crazyflie firmware 2026.08 source. It changes no
estimator/controller/Flow/S3 equation or parameter. It records:
- aligned/gravity-corrected acceleration immediately before the firmware 30 Hz
  LPF, with CPU read-start/read-end timestamps for the underlying accel register
  read;
- scaled barometer values with CPU read-start/read-end timestamps and the exact
  BMP388/BMP390 chip id.

The CPU timestamps are read-window observations, not sensor producer timestamps.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
TARGET = Path("src/hal/src/sensors_bmi088_bmp3xx.c")

STATE_OLD = """static bool isInit = false;
static sensorData_t sensorData;
static volatile uint64_t imuIntTimestamp;

static Axis3i16 gyroRaw;
"""

STATE_NEW = """static bool isInit = false;
static sensorData_t sensorData;
static volatile uint64_t imuIntTimestamp;

// X3 independent-input observer: logging-only snapshots. CPU timestamps are
// read-window observations and MUST NOT be interpreted as sensor producer time.
typedef struct
{
  Axis3f accPreLpf;
  uint32_t sequence;
  uint32_t readStartUsLow;
  uint32_t readEndUsLow;
} x3AccObserverSnapshot_t;

typedef struct
{
  baro_t baro;
  uint32_t sequence;
  uint32_t readStartUsLow;
  uint32_t readEndUsLow;
  uint8_t chipId;
} x3BaroObserverSnapshot_t;

static x3AccObserverSnapshot_t x3AccObserverSnapshot;
static x3BaroObserverSnapshot_t x3BaroObserverSnapshot;
static x3AccObserverSnapshot_t x3AccObserverLatch;
static x3BaroObserverSnapshot_t x3BaroObserverLatch;
static uint32_t x3AccObserverLatchTimestamp = 0xffffffffU;
static uint32_t x3BaroObserverLatchTimestamp = 0xffffffffU;

static void x3LatchAccObserver(uint32_t timestamp)
{
  if (timestamp != x3AccObserverLatchTimestamp)
  {
    taskENTER_CRITICAL();
    x3AccObserverLatch = x3AccObserverSnapshot;
    taskEXIT_CRITICAL();
    x3AccObserverLatchTimestamp = timestamp;
  }
}

static void x3LatchBaroObserver(uint32_t timestamp)
{
  if (timestamp != x3BaroObserverLatchTimestamp)
  {
    taskENTER_CRITICAL();
    x3BaroObserverLatch = x3BaroObserverSnapshot;
    taskEXIT_CRITICAL();
    x3BaroObserverLatchTimestamp = timestamp;
  }
}

static float x3LogAccX(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccObserver(timestamp);
  return x3AccObserverLatch.accPreLpf.x;
}

static float x3LogAccY(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccObserver(timestamp);
  return x3AccObserverLatch.accPreLpf.y;
}

static float x3LogAccZ(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccObserver(timestamp);
  return x3AccObserverLatch.accPreLpf.z;
}

static uint32_t x3LogAccSequence(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccObserver(timestamp);
  return x3AccObserverLatch.sequence;
}

static uint32_t x3LogAccReadStart(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccObserver(timestamp);
  return x3AccObserverLatch.readStartUsLow;
}

static uint32_t x3LogAccReadEnd(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccObserver(timestamp);
  return x3AccObserverLatch.readEndUsLow;
}

static float x3LogBaroAsl(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroObserver(timestamp);
  return x3BaroObserverLatch.baro.asl;
}

static float x3LogBaroPressure(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroObserver(timestamp);
  return x3BaroObserverLatch.baro.pressure;
}

static float x3LogBaroTemp(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroObserver(timestamp);
  return x3BaroObserverLatch.baro.temperature;
}

static uint32_t x3LogBaroSequence(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroObserver(timestamp);
  return x3BaroObserverLatch.sequence;
}

static uint32_t x3LogBaroReadStart(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroObserver(timestamp);
  return x3BaroObserverLatch.readStartUsLow;
}

static uint32_t x3LogBaroReadEnd(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroObserver(timestamp);
  return x3BaroObserverLatch.readEndUsLow;
}

static uint8_t x3LogBaroChipId(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchBaroObserver(timestamp);
  return x3BaroObserverLatch.chipId;
}

static logByFunction_t x3AccLogX = {.aquireFloat = x3LogAccX, .data = NULL};
static logByFunction_t x3AccLogY = {.aquireFloat = x3LogAccY, .data = NULL};
static logByFunction_t x3AccLogZ = {.aquireFloat = x3LogAccZ, .data = NULL};
static logByFunction_t x3AccLogSequence = {.acquireUInt32 = x3LogAccSequence, .data = NULL};
static logByFunction_t x3AccLogReadStart = {.acquireUInt32 = x3LogAccReadStart, .data = NULL};
static logByFunction_t x3AccLogReadEnd = {.acquireUInt32 = x3LogAccReadEnd, .data = NULL};

static logByFunction_t x3BaroLogAsl = {.aquireFloat = x3LogBaroAsl, .data = NULL};
static logByFunction_t x3BaroLogPressure = {.aquireFloat = x3LogBaroPressure, .data = NULL};
static logByFunction_t x3BaroLogTemp = {.aquireFloat = x3LogBaroTemp, .data = NULL};
static logByFunction_t x3BaroLogSequence = {.acquireUInt32 = x3LogBaroSequence, .data = NULL};
static logByFunction_t x3BaroLogReadStart = {.acquireUInt32 = x3LogBaroReadStart, .data = NULL};
static logByFunction_t x3BaroLogReadEnd = {.acquireUInt32 = x3LogBaroReadEnd, .data = NULL};
static logByFunction_t x3BaroLogChipId = {.acquireUInt8 = x3LogBaroChipId, .data = NULL};

static Axis3i16 gyroRaw;
"""

READ_OLD = """      /* get data from chosen sensors */
      sensorsGyroGet(&gyroRaw);
      sensorsAccelGet(&accelRaw);

      /* calibrate if necessary */
"""

READ_NEW = """      /* get data from chosen sensors */
      sensorsGyroGet(&gyroRaw);
      const uint64_t x3AccReadStartUs = usecTimestamp();
      sensorsAccelGet(&accelRaw);
      const uint64_t x3AccReadEndUs = usecTimestamp();

      /* calibrate if necessary */
"""

ACC_OLD = """      sensorsAlignToAirframe(&accScaledIMU, &accScaled);
      sensorsAccAlignToGravity(&accScaled, &sensorData.acc);
      applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);
"""

ACC_NEW = """      sensorsAlignToAirframe(&accScaledIMU, &accScaled);
      sensorsAccAlignToGravity(&accScaled, &sensorData.acc);

      // Retain the predictor-facing acceleration before the firmware LPF. This
      // preserves current scaling/alignment while avoiding post-LPF history.
      taskENTER_CRITICAL();
      x3AccObserverSnapshot.accPreLpf = sensorData.acc;
      x3AccObserverSnapshot.sequence++;
      x3AccObserverSnapshot.readStartUsLow = (uint32_t)x3AccReadStartUs;
      x3AccObserverSnapshot.readEndUsLow = (uint32_t)x3AccReadEndUs;
      taskEXIT_CRITICAL();

      applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);
"""

BARO_OLD = """        baro_t* baro388 = &sensorData.baro;
        /* Temperature and Pressure data are read and stored in the bmp3_data instance */
        bmp3_get_sensor_data(sensor_comp, &data, &bmp3xxDev);
        sensorsScaleBaro(baro388, data.pressure, data.temperature);

        measurement.type = MeasurementTypeBarometer;
"""

BARO_NEW = """        baro_t* baro388 = &sensorData.baro;
        /* Temperature and Pressure data are read and stored in the bmp3_data instance */
        const uint64_t x3BaroReadStartUs = usecTimestamp();
        bmp3_get_sensor_data(sensor_comp, &data, &bmp3xxDev);
        const uint64_t x3BaroReadEndUs = usecTimestamp();
        sensorsScaleBaro(baro388, data.pressure, data.temperature);

        // CPU read/update timing is observable, but BMP3xx conversion/IIR
        // effective time remains a separate physical-model uncertainty.
        taskENTER_CRITICAL();
        x3BaroObserverSnapshot.baro = *baro388;
        x3BaroObserverSnapshot.sequence++;
        x3BaroObserverSnapshot.readStartUsLow = (uint32_t)x3BaroReadStartUs;
        x3BaroObserverSnapshot.readEndUsLow = (uint32_t)x3BaroReadEndUs;
        x3BaroObserverSnapshot.chipId = bmp3_chip_id;
        taskEXIT_CRITICAL();

        measurement.type = MeasurementTypeBarometer;
"""

LOG_OLD = """#ifdef GYRO_ADD_RAW_AND_VARIANCE_LOG_VALUES
LOG_GROUP_START(gyro)
"""

LOG_NEW = """// X3 logging-only independent-input observer. Each group fits one 26-byte
// log payload. Function-backed values share the log packet timestamp and latch
// one firmware snapshot so a row cannot mix adjacent producer-loop snapshots.
LOG_GROUP_START(x3AccObs)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, x, &x3AccLogX)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, y, &x3AccLogY)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, z, &x3AccLogZ)
LOG_ADD_BY_FUNCTION(LOG_UINT32, seq, &x3AccLogSequence)
LOG_ADD_BY_FUNCTION(LOG_UINT32, readBeg, &x3AccLogReadStart)
LOG_ADD_BY_FUNCTION(LOG_UINT32, readEnd, &x3AccLogReadEnd)
LOG_GROUP_STOP(x3AccObs)

LOG_GROUP_START(x3BaroObs)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, asl, &x3BaroLogAsl)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, pressure, &x3BaroLogPressure)
LOG_ADD_BY_FUNCTION(LOG_FLOAT, temp, &x3BaroLogTemp)
LOG_ADD_BY_FUNCTION(LOG_UINT32, seq, &x3BaroLogSequence)
LOG_ADD_BY_FUNCTION(LOG_UINT32, readBeg, &x3BaroLogReadStart)
LOG_ADD_BY_FUNCTION(LOG_UINT32, readEnd, &x3BaroLogReadEnd)
LOG_ADD_BY_FUNCTION(LOG_UINT8, chipId, &x3BaroLogChipId)
LOG_GROUP_STOP(x3BaroObs)

#ifdef GYRO_ADD_RAW_AND_VARIANCE_LOG_VALUES
LOG_GROUP_START(gyro)
"""

MARKERS = (
    ("observer state/functions", STATE_OLD, STATE_NEW, 1),
    ("accelerometer CPU read window", READ_OLD, READ_NEW, 1),
    ("pre-LPF acceleration snapshot", ACC_OLD, ACC_NEW, 1),
    ("barometer CPU read window", BARO_OLD, BARO_NEW, 1),
    ("observer log groups", LOG_OLD, LOG_NEW, 1),
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


def marker_state(text: str) -> str:
    states: list[str] = []
    for label, old, new, count in MARKERS:
        old_count = text.count(old)
        new_count = text.count(new)
        if old_count == count and new_count == 0:
            states.append("old")
        elif old_count == 0 and new_count == count:
            states.append("new")
        else:
            raise SystemExit(
                f"{label}: expected old={count}/new=0 or old=0/new={count}, "
                f"found old={old_count}, new={new_count}; no file written"
            )
    if all(state == "old" for state in states):
        return "applicable"
    if all(state == "new" for state in states):
        return "applied"
    raise SystemExit("partial X3 independent-input observer detected; no file written")


def require_exact_context(text: str) -> str:
    if git("rev-parse", "HEAD") != EXPECTED_COMMIT:
        raise SystemExit("wrong upstream commit; no file written")
    if "BMI088_GYRO_DATA_RDY_INT" not in text:
        raise SystemExit("expected gyro data-ready source path missing; no file written")
    if "applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);" not in text:
        raise SystemExit("expected accelerometer LPF path missing; no file written")
    if "bmp3_chip_id" not in text:
        raise SystemExit("expected BMP3xx chip identity missing; no file written")
    return marker_state(text)


def transform(text: str) -> str:
    state = require_exact_context(text)
    if state == "applied":
        return text
    for _label, old, new, count in MARKERS:
        text = text.replace(old, new, count)
    if require_exact_context(text) != "applied":
        raise SystemExit("X3 independent-input observer failed postcondition; no file written")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify exact 2026.08 sensor source and observer applicability",
    )
    args = parser.parse_args()

    if not TARGET.is_file():
        raise SystemExit(f"missing target: {TARGET}")
    original = TARGET.read_text(encoding="utf-8")
    state = require_exact_context(original)
    transformed = transform(original)
    if args.check:
        print(f"X3 independent-input observer: {state}")
        return
    if transformed == original:
        print("X3 independent-input observer already applied; no file written")
        return
    TARGET.write_text(transformed, encoding="utf-8")
    print(
        "Applied X3 independent-input observer: coherent pre-LPF acceleration "
        "and barometer CPU read windows only"
    )


if __name__ == "__main__":
    main()
