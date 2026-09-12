#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UPSTREAM="${1:-$ROOT/.x3-crazyflie-firmware}"
EXPECTED_COMMIT=54f31e243a0b28b67efef5ba20dbb6d9890a5478
EXPECTED_SENSOR_BLOB=b183285c999335ca258b5131b1a835473473c078
S3_ORACLE="$ROOT/experiments/crazyflie-ukf-surface-range/run_s3_build_oracle.sh"
OBSERVER="$ROOT/experiments/crazyflie-ukf-surface-range/apply_x3_prelpf_timing_observer.py"
OBSERVER_TEST="$ROOT/experiments/crazyflie-ukf-surface-range/test_x3_prelpf_timing_observer.py"
DRDY_OBSERVER="$ROOT/experiments/crazyflie-ukf-surface-range/apply_x3_accel_drdy_observer.py"
DRDY_OBSERVER_TEST="$ROOT/experiments/crazyflie-ukf-surface-range/test_x3_accel_drdy_observer.py"

test -d "$UPSTREAM/.git"
test "$(git -C "$UPSTREAM" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test "$(git -C "$UPSTREAM" hash-object src/hal/src/sensors_bmi088_bmp3xx.c)" = "$EXPECTED_SENSOR_BLOB"
test -z "$(git -C "$UPSTREAM" status --porcelain -- src/modules/src/estimator/estimator_ukf.c src/hal/src/sensors_bmi088_bmp3xx.c)"

python3 "$OBSERVER_TEST"
python3 "$DRDY_OBSERVER_TEST"

# Reuse the exact canonical S3 configuration, but only inside this dedicated
# diagnostic checkout. The trusted s3-props-off workflow/artifact path is never
# touched by this script.
bash "$S3_ORACLE" "$UPSTREAM"
CANONICAL_S3_BIN_SHA="$(sha256sum "$UPSTREAM/build/cf2.bin" | awk '{print $1}')"

test "$(git -C "$UPSTREAM" hash-object src/hal/src/sensors_bmi088_bmp3xx.c)" = "$EXPECTED_SENSOR_BLOB"
test -z "$(git -C "$UPSTREAM" diff -- src/hal/src/sensors_bmi088_bmp3xx.c)"

(
  cd "$UPSTREAM"
  python3 "$OBSERVER" --check
  python3 "$OBSERVER"
  python3 "$DRDY_OBSERVER" --check
  python3 "$DRDY_OBSERVER"
  git diff --check

  grep -Fq 'LOG_GROUP_START(x3AccObs)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'LOG_ADD_BY_FUNCTION(LOG_UINT32, readBeg, &x3AccLogReadStart)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'LOG_GROUP_START(x3AccDrdy)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'LOG_ADD_BY_FUNCTION(LOG_UINT32, irqBeg, &x3AccDrdyLogSequenceBefore)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'x3AccelIntConfig.accel_int_channel = BMI088_INT_CHANNEL_1;' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOC, EXTI_PinSource13);' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'LOG_GROUP_START(x3BaroObs)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'LOG_ADD_BY_FUNCTION(LOG_UINT8, chipId, &x3BaroLogChipId)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'x3AccObserverSnapshot.accPreLpf = sensorData.acc;' src/hal/src/sensors_bmi088_bmp3xx.c

  python3 - <<'PY'
from pathlib import Path
import re
text = Path("src/hal/src/sensors_bmi088_bmp3xx.c").read_text()
snapshot = text.index("x3AccObserverSnapshot.accPreLpf = sensorData.acc;")
lpf = text.index("applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);", snapshot)
assert snapshot < lpf

m = re.search(
    r"void __attribute__\(\(used\)\) EXTI13_Callback\(void\)\n\{(.*?)\n\}\n\n"
    r"void sensorsBmi088Bmp3xxDataAvailableCallback",
    text,
    re.S,
)
assert m
body = m.group(1)
assert "x3AccelDrdySequence++;" in body
assert "vTaskNotifyGiveFromISR" not in body
assert "portYIELD" not in body
assert "imuIntTimestamp" not in body
PY

  docker run --rm -v "$PWD:/module" bitcraze/builder bash -lc '
    set -euo pipefail
    cat > /tmp/x3-cf21-drdy.config <<'"'"'EOF'"'"'
# CONFIG_SENSORS_MPU9250_LPS25H is not set
CONFIG_SENSORS_BMI088_BMP3XX=y
EOF
    ./scripts/kconfig/merge_config.sh -O build -m build/.config /tmp/x3-cf21-drdy.config
    make olddefconfig
    grep -q "^# CONFIG_SENSORS_MPU9250_LPS25H is not set$" build/.config
    grep -q "^CONFIG_SENSORS_BMI088_BMP3XX=y$" build/.config
    make -j"$(nproc)"
    arm-none-eabi-nm --defined-only build/cf2.elf | grep -Eq "[[:space:]]x3LogAccX$"
    arm-none-eabi-nm --defined-only build/cf2.elf | grep -Eq "[[:space:]]x3LogBaroChipId$"
    arm-none-eabi-nm --defined-only build/cf2.elf | grep -Eq "[[:space:]]x3LogAccDrdySequenceBefore$"
    arm-none-eabi-nm --defined-only build/cf2.elf | grep -Eq "[[:space:]]EXTI13_Callback$"
  '

  test -s build/cf2.elf
  test -s build/cf2.bin
  find build -type f -name 'sensors_bmi088_bmp3xx.o' -size +0c -print -quit | grep -q .
  test "$(sha256sum build/cf2.bin | awk '{print $1}')" != "$CANONICAL_S3_BIN_SHA"
)

printf '%s\n' "PASS: X3 pre-LPF/read-window plus explicit BMI088 accel-DRDY INT1/PC13 observer compiled in a CF21-only diagnostic checkout; canonical s3-props-off workflow/artifact identity was not reused."
