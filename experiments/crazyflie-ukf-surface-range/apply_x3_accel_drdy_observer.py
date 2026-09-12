#!/usr/bin/env python3
"""Add a diagnostic-only BMI088 accelerometer-DRDY observer to the X3 overlay.

This overlay is applied only after ``apply_x3_prelpf_timing_observer.py`` on the
exact pinned Crazyflie 2026.08 source. It configures BMI088 accelerometer INT1,
observes its published CF2.1 PC13 path through EXTI13, and records the latest
interrupt sequence/timestamp immediately before and after each accelerometer
register read.

The observer never wakes or retimes the existing sensor task. Its interrupt
timestamps are MCU data-ready observations only: they do not prove BMI088
internal sample/filter producer time or validate a predictor timing bound.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
TARGET = Path("src/hal/src/sensors_bmi088_bmp3xx.c")

STATE_OLD = """static uint32_t x3AccObserverLatchTimestamp = 0xffffffffU;
static uint32_t x3BaroObserverLatchTimestamp = 0xffffffffU;

static void x3LatchAccObserver(uint32_t timestamp)
"""

STATE_NEW = """static uint32_t x3AccObserverLatchTimestamp = 0xffffffffU;
static uint32_t x3BaroObserverLatchTimestamp = 0xffffffffU;

// X3 accelerometer data-ready provenance observer. This is intentionally
// independent from the existing PC14 sensor-task wake path.
typedef struct
{
  uint32_t accSequence;
  uint32_t drdySequenceBefore;
  uint32_t drdyTimestampBeforeUsLow;
  uint32_t drdySequenceAfter;
  uint32_t drdyTimestampAfterUsLow;
} x3AccDrdyObserverSnapshot_t;

static volatile uint32_t x3AccelDrdySequence = 0;
static volatile uint32_t x3AccelDrdyTimestampUsLow = 0;
static x3AccDrdyObserverSnapshot_t x3AccDrdyObserverSnapshot;
static x3AccDrdyObserverSnapshot_t x3AccDrdyObserverLatch;
static uint32_t x3AccDrdyObserverLatchTimestamp = 0xffffffffU;

static void x3LatchAccDrdyObserver(uint32_t timestamp)
{
  if (timestamp != x3AccDrdyObserverLatchTimestamp)
  {
    taskENTER_CRITICAL();
    x3AccDrdyObserverLatch = x3AccDrdyObserverSnapshot;
    taskEXIT_CRITICAL();
    x3AccDrdyObserverLatchTimestamp = timestamp;
  }
}

static uint32_t x3LogAccDrdyAccSequence(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccDrdyObserver(timestamp);
  return x3AccDrdyObserverLatch.accSequence;
}

static uint32_t x3LogAccDrdySequenceBefore(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccDrdyObserver(timestamp);
  return x3AccDrdyObserverLatch.drdySequenceBefore;
}

static uint32_t x3LogAccDrdyTimestampBefore(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccDrdyObserver(timestamp);
  return x3AccDrdyObserverLatch.drdyTimestampBeforeUsLow;
}

static uint32_t x3LogAccDrdySequenceAfter(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccDrdyObserver(timestamp);
  return x3AccDrdyObserverLatch.drdySequenceAfter;
}

static uint32_t x3LogAccDrdyTimestampAfter(uint32_t timestamp, void* data)
{
  (void)data;
  x3LatchAccDrdyObserver(timestamp);
  return x3AccDrdyObserverLatch.drdyTimestampAfterUsLow;
}

static logByFunction_t x3AccDrdyLogAccSequence = {.acquireUInt32 = x3LogAccDrdyAccSequence, .data = NULL};
static logByFunction_t x3AccDrdyLogSequenceBefore = {.acquireUInt32 = x3LogAccDrdySequenceBefore, .data = NULL};
static logByFunction_t x3AccDrdyLogTimestampBefore = {.acquireUInt32 = x3LogAccDrdyTimestampBefore, .data = NULL};
static logByFunction_t x3AccDrdyLogSequenceAfter = {.acquireUInt32 = x3LogAccDrdySequenceAfter, .data = NULL};
static logByFunction_t x3AccDrdyLogTimestampAfter = {.acquireUInt32 = x3LogAccDrdyTimestampAfter, .data = NULL};

static void x3LatchAccObserver(uint32_t timestamp)
"""

READ_OLD = """      /* get data from chosen sensors */
      sensorsGyroGet(&gyroRaw);
      const uint64_t x3AccReadStartUs = usecTimestamp();
      sensorsAccelGet(&accelRaw);
      const uint64_t x3AccReadEndUs = usecTimestamp();

      /* calibrate if necessary */
"""

READ_NEW = """      /* get data from chosen sensors */
      sensorsGyroGet(&gyroRaw);

      uint32_t x3AccDrdySequenceBefore;
      uint32_t x3AccDrdyTimestampBeforeUsLow;
      taskENTER_CRITICAL();
      x3AccDrdySequenceBefore = x3AccelDrdySequence;
      x3AccDrdyTimestampBeforeUsLow = x3AccelDrdyTimestampUsLow;
      taskEXIT_CRITICAL();

      const uint64_t x3AccReadStartUs = usecTimestamp();
      sensorsAccelGet(&accelRaw);
      const uint64_t x3AccReadEndUs = usecTimestamp();

      uint32_t x3AccDrdySequenceAfter;
      uint32_t x3AccDrdyTimestampAfterUsLow;
      taskENTER_CRITICAL();
      x3AccDrdySequenceAfter = x3AccelDrdySequence;
      x3AccDrdyTimestampAfterUsLow = x3AccelDrdyTimestampUsLow;
      taskEXIT_CRITICAL();

      /* calibrate if necessary */
"""

SNAPSHOT_OLD = """      x3AccObserverSnapshot.accPreLpf = sensorData.acc;
      x3AccObserverSnapshot.sequence++;
      x3AccObserverSnapshot.readStartUsLow = (uint32_t)x3AccReadStartUs;
      x3AccObserverSnapshot.readEndUsLow = (uint32_t)x3AccReadEndUs;
      taskEXIT_CRITICAL();
"""

SNAPSHOT_NEW = """      x3AccObserverSnapshot.accPreLpf = sensorData.acc;
      x3AccObserverSnapshot.sequence++;
      x3AccObserverSnapshot.readStartUsLow = (uint32_t)x3AccReadStartUs;
      x3AccObserverSnapshot.readEndUsLow = (uint32_t)x3AccReadEndUs;

      x3AccDrdyObserverSnapshot.accSequence = x3AccObserverSnapshot.sequence;
      x3AccDrdyObserverSnapshot.drdySequenceBefore = x3AccDrdySequenceBefore;
      x3AccDrdyObserverSnapshot.drdyTimestampBeforeUsLow = x3AccDrdyTimestampBeforeUsLow;
      x3AccDrdyObserverSnapshot.drdySequenceAfter = x3AccDrdySequenceAfter;
      x3AccDrdyObserverSnapshot.drdyTimestampAfterUsLow = x3AccDrdyTimestampAfterUsLow;
      taskEXIT_CRITICAL();
"""

ACCEL_CONFIG_OLD = """    bmi088Dev.accel_cfg.odr = BMI088_ACCEL_ODR_1600_HZ;
    rslt |= bmi088_set_accel_meas_conf(&bmi088Dev);

    struct bmi088_sensor_data acc;
"""

ACCEL_CONFIG_NEW = """    bmi088Dev.accel_cfg.odr = BMI088_ACCEL_ODR_1600_HZ;
    rslt |= bmi088_set_accel_meas_conf(&bmi088Dev);

    // Diagnostic-only producer-availability observation: explicitly map accel
    // data-ready to BMI088 INT1. Published CF2.1 Rev.B routes INT1 to MCU PC13.
    struct bmi088_int_cfg x3AccelIntConfig = {0};
    x3AccelIntConfig.accel_int_channel = BMI088_INT_CHANNEL_1;
    x3AccelIntConfig.accel_int_type = BMI088_ACCEL_DATA_RDY_INT;
    x3AccelIntConfig.accel_int_pin_cfg.enable_int_pin = 1;
    x3AccelIntConfig.accel_int_pin_cfg.lvl = 1;
    x3AccelIntConfig.accel_int_pin_cfg.output_mode = 0;
    rslt |= bmi088_set_accel_int_config(&x3AccelIntConfig, &bmi088Dev);

    struct bmi088_sensor_data acc;
"""

INTERRUPT_OLD = """  // Enable the interrupt on PC14
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_14;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN;
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_NOPULL; //GPIO_PuPd_DOWN;
  GPIO_Init(GPIOC, &GPIO_InitStructure);

  SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOC, EXTI_PinSource14);

  EXTI_InitStructure.EXTI_Line = EXTI_Line14;
  EXTI_InitStructure.EXTI_Mode = EXTI_Mode_Interrupt;
  EXTI_InitStructure.EXTI_Trigger = EXTI_Trigger_Rising;
  EXTI_InitStructure.EXTI_LineCmd = ENABLE;
  portDISABLE_INTERRUPTS();
  EXTI_Init(&EXTI_InitStructure);
  EXTI_ClearITPendingBit(EXTI_Line14);
  portENABLE_INTERRUPTS();
"""

INTERRUPT_NEW = """  // Diagnostic-only accelerometer DRDY observer on published CF2.1 INT1/PC13.
  // It does not wake the sensor task; PC14 below remains the operational path.
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_13;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN;
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_NOPULL;
  GPIO_Init(GPIOC, &GPIO_InitStructure);

  SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOC, EXTI_PinSource13);

  EXTI_InitStructure.EXTI_Line = EXTI_Line13;
  EXTI_InitStructure.EXTI_Mode = EXTI_Mode_Interrupt;
  EXTI_InitStructure.EXTI_Trigger = EXTI_Trigger_Rising;
  EXTI_InitStructure.EXTI_LineCmd = ENABLE;
  portDISABLE_INTERRUPTS();
  EXTI_Init(&EXTI_InitStructure);
  EXTI_ClearITPendingBit(EXTI_Line13);
  portENABLE_INTERRUPTS();

  // Existing operational interrupt path on PC14 remains unchanged.
  GPIO_InitStructure.GPIO_Pin = GPIO_Pin_14;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN;
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_NOPULL; //GPIO_PuPd_DOWN;
  GPIO_Init(GPIOC, &GPIO_InitStructure);

  SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOC, EXTI_PinSource14);

  EXTI_InitStructure.EXTI_Line = EXTI_Line14;
  EXTI_InitStructure.EXTI_Mode = EXTI_Mode_Interrupt;
  EXTI_InitStructure.EXTI_Trigger = EXTI_Trigger_Rising;
  EXTI_InitStructure.EXTI_LineCmd = ENABLE;
  portDISABLE_INTERRUPTS();
  EXTI_Init(&EXTI_InitStructure);
  EXTI_ClearITPendingBit(EXTI_Line14);
  portENABLE_INTERRUPTS();
"""

CALLBACK_OLD = """static void applyAxis3fLpf(lpf2pData *data, Axis3f* in)
{
  for (uint8_t i = 0; i < 3; i++) {
    in->axis[i] = lpf2pApply(&data[i], in->axis[i]);
  }
}

void sensorsBmi088Bmp3xxDataAvailableCallback(void)
{
"""

CALLBACK_NEW = """static void applyAxis3fLpf(lpf2pData *data, Axis3f* in)
{
  for (uint8_t i = 0; i < 3; i++) {
    in->axis[i] = lpf2pApply(&data[i], in->axis[i]);
  }
}

void __attribute__((used)) EXTI13_Callback(void)
{
  // Observation only: do not notify/yield or otherwise retime the sensor task.
  x3AccelDrdyTimestampUsLow = (uint32_t)usecTimestamp();
  x3AccelDrdySequence++;
}

void sensorsBmi088Bmp3xxDataAvailableCallback(void)
{
"""

LOG_OLD = """LOG_GROUP_STOP(x3AccObs)

LOG_GROUP_START(x3BaroObs)
"""

LOG_NEW = """LOG_GROUP_STOP(x3AccObs)

LOG_GROUP_START(x3AccDrdy)
LOG_ADD_BY_FUNCTION(LOG_UINT32, accSeq, &x3AccDrdyLogAccSequence)
LOG_ADD_BY_FUNCTION(LOG_UINT32, irqBeg, &x3AccDrdyLogSequenceBefore)
LOG_ADD_BY_FUNCTION(LOG_UINT32, irqUsBeg, &x3AccDrdyLogTimestampBefore)
LOG_ADD_BY_FUNCTION(LOG_UINT32, irqEnd, &x3AccDrdyLogSequenceAfter)
LOG_ADD_BY_FUNCTION(LOG_UINT32, irqUsEnd, &x3AccDrdyLogTimestampAfter)
LOG_GROUP_STOP(x3AccDrdy)

LOG_GROUP_START(x3BaroObs)
"""

MARKERS = (
    ("observer state/functions", STATE_OLD, STATE_NEW, 1),
    ("accelerometer read bracketing", READ_OLD, READ_NEW, 1),
    ("DRDY snapshot publication", SNAPSHOT_OLD, SNAPSHOT_NEW, 1),
    ("BMI088 accelerometer INT1 configuration", ACCEL_CONFIG_OLD, ACCEL_CONFIG_NEW, 1),
    ("PC13 EXTI observer configuration", INTERRUPT_OLD, INTERRUPT_NEW, 1),
    ("PC13 observer ISR", CALLBACK_OLD, CALLBACK_NEW, 1),
    ("DRDY log group", LOG_OLD, LOG_NEW, 1),
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
    raise SystemExit("partial X3 accelerometer-DRDY observer detected; no file written")


def require_exact_context(text: str) -> str:
    if git("rev-parse", "HEAD") != EXPECTED_COMMIT:
        raise SystemExit("wrong upstream commit; no file written")
    if "LOG_GROUP_START(x3AccObs)" not in text:
        raise SystemExit("pre-LPF X3 observer must be applied first; no file written")
    if "BMI088_GYRO_DATA_RDY_INT" not in text:
        raise SystemExit("expected operational gyro DRDY configuration missing; no file written")
    if "EXTI_PinSource14" not in text:
        raise SystemExit("expected operational PC14 path missing; no file written")
    return marker_state(text)


def transform(text: str) -> str:
    state = require_exact_context(text)
    if state == "applied":
        return text
    for _label, old, new, count in MARKERS:
        text = text.replace(old, new, count)
    if require_exact_context(text) != "applied":
        raise SystemExit("X3 accelerometer-DRDY observer failed postcondition; no file written")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify exact 2026.08 post-pre-LPF source and DRDY observer applicability",
    )
    args = parser.parse_args()

    if not TARGET.is_file():
        raise SystemExit(f"missing target: {TARGET}")
    original = TARGET.read_text(encoding="utf-8")
    state = require_exact_context(original)
    transformed = transform(original)
    if args.check:
        print(f"X3 accelerometer-DRDY observer: {state}")
        return
    if transformed == original:
        print("X3 accelerometer-DRDY observer already applied; no file written")
        return
    TARGET.write_text(transformed, encoding="utf-8")
    print(
        "Applied X3 accelerometer-DRDY observer: BMI088 INT1/PC13 evidence only; "
        "sensor-task PC14 behavior unchanged"
    )


if __name__ == "__main__":
    main()
