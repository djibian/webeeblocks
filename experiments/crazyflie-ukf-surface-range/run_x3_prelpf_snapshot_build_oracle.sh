#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UPSTREAM="${1:-$ROOT/.ci-crazyflie-firmware-x3-prelpf}"
EXPECTED_COMMIT=54f31e243a0b28b67efef5ba20dbb6d9890a5478
EXPECTED_BLOB=b183285c999335ca258b5131b1a835473473c078
TARGET=src/hal/src/sensors_bmi088_bmp3xx.c
APPLICATOR="$ROOT/experiments/crazyflie-ukf-surface-range/apply_x3_prelpf_snapshot_logging.py"

test -d "$UPSTREAM/.git"
test "$(git -C "$UPSTREAM" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test "$(git -C "$UPSTREAM" hash-object "$TARGET")" = "$EXPECTED_BLOB"
test -z "$(git -C "$UPSTREAM" status --porcelain -- "$TARGET")"

(
  cd "$UPSTREAM"
  python3 "$APPLICATOR" --check
  python3 "$APPLICATOR"
  python3 "$APPLICATOR" --check
  git diff --check
  test "$(git diff --name-only)" = "$TARGET"

  grep -Fq 'X3_PRELPF_SNAPSHOT_LOGGING_V1' "$TARGET"
  grep -Fq 'x3AccProducer.accPreLpf = sensorData.acc;' "$TARGET"
  grep -Fq 'x3AccProducer.gyroIrqUs = (uint32_t)sensorData.interruptTimestamp;' "$TARGET"
  grep -Fq 'x3AccProducer.accDoneUs = x3AccReadDoneUs;' "$TARGET"
  grep -Fq 'x3BaroProducer.chipId = bmp3_chip_id;' "$TARGET"
  grep -Fq 'LOG_GROUP_START(x3Acc)' "$TARGET"
  grep -Fq 'LOG_GROUP_START(x3Baro)' "$TARGET"

  python3 - <<'PY'
from pathlib import Path

text = Path("src/hal/src/sensors_bmi088_bmp3xx.c").read_text(encoding="utf-8")

# The diagnostic acceleration snapshot must remain before the existing 30 Hz
# software LPF and after both alignment stages.
start = text.index("sensorsAlignToAirframe(&accScaledIMU, &accScaled);")
gravity = text.index("sensorsAccAlignToGravity(&accScaled, &sensorData.acc);", start)
snapshot = text.index("x3AccProducer.accPreLpf = sensorData.acc;", gravity)
lpf = text.index("applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);", snapshot)
assert start < gravity < snapshot < lpf

# The CPU read-completion observation is taken after the actual accel read and
# before scaling/alignment. It is deliberately not named as producer time.
read = text.index("sensorsAccelGet(&accelRaw);")
done = text.index("const uint32_t x3AccReadDoneUs = usecTimestamp();", read)
scale = text.index("accScaledIMU.x = accelRaw.x", done)
assert read < done < scale
assert "accProducer" not in text

# Barometer CPU completion and chip identity are captured only after the Bosch
# read and Crazyflie scaling path. Internal conversion/IIR time is not claimed.
baro_read = text.index("bmp3_get_sensor_data(sensor_comp, &data, &bmp3xxDev);")
baro_scale = text.index("sensorsScaleBaro(baro388, data.pressure, data.temperature);", baro_read)
baro_done = text.index("const uint32_t x3BaroReadDoneUs = usecTimestamp();", baro_scale)
chip = text.index("x3BaroProducer.chipId = bmp3_chip_id;", baro_done)
assert baro_read < baro_scale < baro_done < chip

# One configured x3Acc block is 3 floats + 3 uint32 = 24 bytes. One x3Baro
# block is 3 floats + 2 uint32 + 1 uint8 = 21 bytes; both stay below CRTP's
# 26-byte log payload ceiling.
assert text.count("LOG_ADD_BY_FUNCTION(LOG_FLOAT, pre") == 3
assert text.count("LOG_ADD_BY_FUNCTION(LOG_UINT32, gyroIrqUs") == 1
assert text.count("LOG_ADD_BY_FUNCTION(LOG_UINT32, accDoneUs") == 1
assert text.count("LOG_ADD_BY_FUNCTION(LOG_UINT32, seq, &x3AccSeqLogger)") == 1
assert text.count("LOG_ADD_BY_FUNCTION(LOG_FLOAT, asl") == 1
assert text.count("LOG_ADD_BY_FUNCTION(LOG_FLOAT, press") == 1
assert text.count("LOG_ADD_BY_FUNCTION(LOG_FLOAT, temp") == 1
assert text.count("LOG_ADD_BY_FUNCTION(LOG_UINT32, readDoneUs") == 1
assert text.count("LOG_ADD_BY_FUNCTION(LOG_UINT32, seq, &x3BaroSeqLogger)") == 1
assert text.count("LOG_ADD_BY_FUNCTION(LOG_UINT8, chipId") == 1

# Producer writes and packet-latch copies are both protected by the same short
# FreeRTOS critical-section mechanism, preventing torn multi-field snapshots.
assert text.count("taskENTER_CRITICAL();") >= 4
assert text.count("taskEXIT_CRITICAL();") >= 4
assert "x3AccLatched = x3AccProducer;" in text
assert "x3BaroLatched = x3BaroProducer;" in text
PY

  docker run --rm -v "$PWD:/module" bitcraze/builder bash -lc '
    set -euo pipefail
    make cf2_defconfig
    cat > /tmp/x3-prelpf-ukf.config <<'EOF'
# CONFIG_ESTIMATOR_AUTO_SELECT is not set
CONFIG_ESTIMATOR_UKF_ENABLE=y
CONFIG_ESTIMATOR_UKF=y
CONFIG_DECK_FLOW=y
CONFIG_DECK_ZRANGER=y
CONFIG_DECK_ZRANGER2=y
# CONFIG_DECK_ACTIVE_MARKER is not set
# CONFIG_DECK_AI is not set
# CONFIG_DECK_BUZZ is not set
# CONFIG_DECK_LEDRING is not set
# CONFIG_DECK_LIGHTHOUSE is not set
# CONFIG_DECK_LOCO is not set
# CONFIG_DECK_MULTIRANGER is not set
# CONFIG_DECK_OA is not set
# CONFIG_DECK_USD is not set
EOF
    ./scripts/kconfig/merge_config.sh -O build -m build/.config /tmp/x3-prelpf-ukf.config
    make olddefconfig
    grep -q "^CONFIG_DECK_FLOW=y$" build/.config
    grep -q "^CONFIG_DECK_ZRANGER=y$" build/.config
    grep -q "^CONFIG_DECK_ZRANGER2=y$" build/.config
    grep -q "^CONFIG_ESTIMATOR_UKF_ENABLE=y$" build/.config
    grep -q "^CONFIG_ESTIMATOR_UKF=y$" build/.config
    ./tools/build/build UNIT_TEST_STYLE=min
  '

  test -s build/cf2.elf
  test -s build/cf2.bin
  find build -type f -name 'sensors_bmi088_bmp3xx.o' -size +0c -print -quit | grep -q .
)

printf '%s\n' "PASS: exact Crazyflie 2026.08 source accepted the Lab-only packet-latched pre-LPF acceleration/barometer diagnostic and built UKF-enabled cf2 firmware."
