#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UPSTREAM="${1:-$ROOT/.x3-crazyflie-firmware}"
EXPECTED_COMMIT=54f31e243a0b28b67efef5ba20dbb6d9890a5478
EXPECTED_SENSOR_BLOB=b183285c999335ca258b5131b1a835473473c078
S3_ORACLE="$ROOT/experiments/crazyflie-ukf-surface-range/run_s3_build_oracle.sh"
OBSERVER="$ROOT/experiments/crazyflie-ukf-surface-range/apply_x3_prelpf_timing_observer.py"
OBSERVER_TEST="$ROOT/experiments/crazyflie-ukf-surface-range/test_x3_prelpf_timing_observer.py"

test -d "$UPSTREAM/.git"
test "$(git -C "$UPSTREAM" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test "$(git -C "$UPSTREAM" hash-object src/hal/src/sensors_bmi088_bmp3xx.c)" = "$EXPECTED_SENSOR_BLOB"
test -z "$(git -C "$UPSTREAM" status --porcelain -- src/modules/src/estimator/estimator_ukf.c src/hal/src/sensors_bmi088_bmp3xx.c)"

python3 "$OBSERVER_TEST"

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
  git diff --check

  grep -Fq 'LOG_GROUP_START(x3AccObs)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'LOG_ADD_BY_FUNCTION(LOG_UINT32, readBeg, &x3AccLogReadStart)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'LOG_GROUP_START(x3BaroObs)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'LOG_ADD_BY_FUNCTION(LOG_UINT8, chipId, &x3BaroLogChipId)' src/hal/src/sensors_bmi088_bmp3xx.c
  grep -Fq 'x3AccObserverSnapshot.accPreLpf = sensorData.acc;' src/hal/src/sensors_bmi088_bmp3xx.c

  python3 - <<'PY'
from pathlib import Path
text = Path("src/hal/src/sensors_bmi088_bmp3xx.c").read_text()
snapshot = text.index("x3AccObserverSnapshot.accPreLpf = sensorData.acc;")
lpf = text.index("applyAxis3fLpf((lpf2pData*)(&accLpf), &sensorData.acc);", snapshot)
assert snapshot < lpf
PY

  docker run --rm -v "$PWD:/module" bitcraze/builder bash -lc '
    set -euo pipefail
    make -j"$(nproc)"
    arm-none-eabi-nm --defined-only build/cf2.elf | grep -Eq "[[:space:]]x3LogAccX$"
    arm-none-eabi-nm --defined-only build/cf2.elf | grep -Eq "[[:space:]]x3LogBaroChipId$"
  '

  test -s build/cf2.elf
  test -s build/cf2.bin
  find build -type f -name 'sensors_bmi088_bmp3xx.o' -size +0c -print -quit | grep -q .
  test "$(sha256sum build/cf2.bin | awk '{print $1}')" != "$CANONICAL_S3_BIN_SHA"
)

printf '%s\n' "PASS: X3 pre-LPF/read-window observer compiled in a dedicated diagnostic checkout; canonical s3-props-off workflow/artifact identity was not reused."
