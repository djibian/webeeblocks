#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UPSTREAM="${1:-$ROOT/.ci-crazyflie-firmware}"
EXPECTED_COMMIT=54f31e243a0b28b67efef5ba20dbb6d9890a5478
EXPECTED_BLOB=57c0e8405c07b63a29538019895ed17d0a379440
EXPECTED_SENSOR_BLOB=b183285c999335ca258b5131b1a835473473c078
APPLICATOR="$ROOT/experiments/crazyflie-ukf-surface-range/apply_surface_offset_s3.py"
DISCRIMINATOR="$ROOT/experiments/crazyflie-ukf-surface-range/apply_surface_offset_s3_veto_discriminator.py"
TIMING_OBSERVER="$ROOT/experiments/crazyflie-ukf-surface-range/apply_surface_offset_s3_timing_observer.py"
INPUT_OBSERVER="$ROOT/experiments/crazyflie-ukf-surface-range/apply_x3_prelpf_timing_observer.py"
INPUT_OBSERVER_TEST="$ROOT/experiments/crazyflie-ukf-surface-range/test_x3_prelpf_timing_observer.py"

test -d "$UPSTREAM/.git"
test "$(git -C "$UPSTREAM" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test "$(git -C "$UPSTREAM" hash-object src/modules/src/estimator/estimator_ukf.c)" = "$EXPECTED_BLOB"
test "$(git -C "$UPSTREAM" hash-object src/hal/src/sensors_bmi088_bmp3xx.c)" = "$EXPECTED_SENSOR_BLOB"
test -z "$(git -C "$UPSTREAM" status --porcelain -- src/modules/src/estimator/estimator_ukf.c src/hal/src/sensors_bmi088_bmp3xx.c)"

(
  cd "$UPSTREAM"
  python3 "$APPLICATOR" --check
  python3 "$APPLICATOR"
  python3 "$DISCRIMINATOR" --check
  python3 "$DISCRIMINATOR"
  python3 "$TIMING_OBSERVER" --check
  python3 "$TIMING_OBSERVER"
  git diff --check
  grep -Fq 'static uint8_t surfaceOffsetS3 = 0;' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'LOG_ADD(LOG_FLOAT, surfOffset, &surfaceOffset)' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'PARAM_ADD(PARAM_UINT8, surfaceOffsetS3, &surfaceOffsetS3)' src/modules/src/estimator/estimator_ukf.c
  grep -Fq '#define S3_CLEARANCE_WINDOW 5U' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'sameSignPersistent' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'LOG_ADD(LOG_FLOAT, surfBefore, &surfaceBaselineClearance)' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'LOG_ADD(LOG_FLOAT, surfAfter, &surfaceAfterClearance)' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'S3_REASON_VZ_VETO = 6' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'S3_REASON_BARO_VETO = 7' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'S3_REASON_BOTH_VETO = 8' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'const bool vzVerticalVeto = fabsf(stateNav[5]) >= S3_VZ_VERTICAL_VETO_MPS;' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'const bool baroVerticalVeto = fabsf(surfaceBaroDelta) >= S3_BARO_VERTICAL_VETO_M;' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'const bool verticalVeto = vzVerticalVeto || baroVerticalVeto;' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'surfaceTofAgeMs = nowMs - T2M(m.data.tof.timestamp);' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'surfaceLatestBaroSequence = surfaceQueueSequence;' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'surfaceBaroLagAtSuspect = surfaceBaroLagEvents;' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'surfaceVzAtDecision = stateNav[5];' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'surfaceBaroSeen = 0;' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'LOG_ADD(LOG_UINT32, tofAge, &surfaceTofAgeMs)' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'LOG_ADD(LOG_UINT32, baroLag0, &surfaceBaroLagAtSuspect)' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'LOG_ADD(LOG_FLOAT, vzDec, &surfaceVzAtDecision)' src/modules/src/estimator/estimator_ukf.c

  docker run --rm -v "$PWD:/module" bitcraze/builder bash -lc '
    set -euo pipefail
    make cf2_defconfig
    # The stock cf2 defconfig enables most deck drivers by default. S3 only needs
    # the real Flow Deck driver/ToF path plus UKF; disable unrelated default deck
    # drivers so the experimental firmware fits the CF2 CCMRAM budget without
    # removing Flow support or weakening the artifact oracle.
    cat > /tmp/s3-ukf-default.config <<'EOF'
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
    ./scripts/kconfig/merge_config.sh -O build -m build/.config /tmp/s3-ukf-default.config
    make olddefconfig
    grep -q "^CONFIG_DECK_FLOW=y$" build/.config
    grep -q "^CONFIG_DECK_ZRANGER=y$" build/.config
    grep -q "^CONFIG_DECK_ZRANGER2=y$" build/.config
    grep -q "^CONFIG_ESTIMATOR_KALMAN_ENABLE=y$" build/.config
    grep -q "^# CONFIG_ESTIMATOR_AUTO_SELECT is not set$" build/.config
    grep -q "^CONFIG_ESTIMATOR_UKF_ENABLE=y$" build/.config
    grep -q "^CONFIG_ESTIMATOR_UKF=y$" build/.config
    ./tools/build/build UNIT_TEST_STYLE=min

    symbol_count="$(arm-none-eabi-nm -S --defined-only build/cf2.elf | grep -Ec "[[:space:]]bmp3_chip_id$")"
    test "$symbol_count" -eq 1
    symbol="$(arm-none-eabi-nm -S --defined-only build/cf2.elf | grep -E "[[:space:]]bmp3_chip_id$")"
    read -r address size type name <<<"$symbol"
    test "$name" = "bmp3_chip_id"
    test "$size" = "00000001"
    case "$type" in
      B|b|D|d) ;;
      *) echo "unexpected bmp3_chip_id symbol type: $type" >&2; exit 1 ;;
    esac
    printf "X3_BMP3_CHIP_ID_SYMBOL address=0x%s size=0x%s type=%s name=%s\n" \
      "$address" "$size" "$type" "$name"
  '

  test -s build/cf2.elf
  test -s build/cf2.bin
  find build -type f -name 'estimator_ukf.o' -size +0c -print -quit | grep -q .
)

# The existing checkpoint artifact is produced from UPSTREAM after the canonical
# build above. Prove the X3 observer in a separate copied workspace only; never
# alter the source/build tree that ci-webots later packages as
# experimental-s3-surface-offset-2026-08.
CANONICAL_BIN_SHA="$(sha256sum "$UPSTREAM/build/cf2.bin" | awk '{print $1}')"
CANONICAL_ELF_SHA="$(sha256sum "$UPSTREAM/build/cf2.elf" | awk '{print $1}')"
test "$(git -C "$UPSTREAM" hash-object src/hal/src/sensors_bmi088_bmp3xx.c)" = "$EXPECTED_SENSOR_BLOB"
test -z "$(git -C "$UPSTREAM" diff -- src/hal/src/sensors_bmi088_bmp3xx.c)"

python3 "$INPUT_OBSERVER_TEST"
DIAGNOSTIC_UPSTREAM="$(mktemp -d)"
trap 'rm -rf "$DIAGNOSTIC_UPSTREAM"' EXIT
cp -a "$UPSTREAM/." "$DIAGNOSTIC_UPSTREAM/"

(
  cd "$DIAGNOSTIC_UPSTREAM"
  test "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT"
  python3 "$INPUT_OBSERVER" --check
  python3 "$INPUT_OBSERVER"
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
    ./tools/build/build UNIT_TEST_STYLE=min
    arm-none-eabi-nm --defined-only build/cf2.elf | grep -Eq "[[:space:]]x3LogAccX$"
    arm-none-eabi-nm --defined-only build/cf2.elf | grep -Eq "[[:space:]]x3LogBaroChipId$"
  '

  test -s build/cf2.elf
  test -s build/cf2.bin
  find build -type f -name 'sensors_bmi088_bmp3xx.o' -size +0c -print -quit | grep -q .
  test "$(sha256sum build/cf2.bin | awk '{print $1}')" != "$CANONICAL_BIN_SHA"
)

# Fail closed if the diagnostic build touched the canonical checkpoint workspace.
test "$(sha256sum "$UPSTREAM/build/cf2.bin" | awk '{print $1}')" = "$CANONICAL_BIN_SHA"
test "$(sha256sum "$UPSTREAM/build/cf2.elf" | awk '{print $1}')" = "$CANONICAL_ELF_SHA"
test "$(git -C "$UPSTREAM" hash-object src/hal/src/sensors_bmi088_bmp3xx.c)" = "$EXPECTED_SENSOR_BLOB"
test -z "$(git -C "$UPSTREAM" diff -- src/hal/src/sensors_bmi088_bmp3xx.c)"

printf '%s\n' "PASS: canonical S3 checkpoint workspace/artifact remained unchanged; X3 pre-LPF/read-window observer compiled only in an isolated diagnostic copy."
