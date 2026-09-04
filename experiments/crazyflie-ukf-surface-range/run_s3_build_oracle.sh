#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UPSTREAM="${1:-$ROOT/.ci-crazyflie-firmware}"
EXPECTED_COMMIT=54f31e243a0b28b67efef5ba20dbb6d9890a5478
EXPECTED_BLOB=57c0e8405c07b63a29538019895ed17d0a379440
APPLICATOR="$ROOT/experiments/crazyflie-ukf-surface-range/apply_surface_offset_s3.py"

test -d "$UPSTREAM/.git"
test "$(git -C "$UPSTREAM" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test "$(git -C "$UPSTREAM" hash-object src/modules/src/estimator/estimator_ukf.c)" = "$EXPECTED_BLOB"
test -z "$(git -C "$UPSTREAM" status --porcelain -- src/modules/src/estimator/estimator_ukf.c)"

(
  cd "$UPSTREAM"
  python3 "$APPLICATOR" --check
  python3 "$APPLICATOR"
  git diff --check
  grep -Fq 'static uint8_t surfaceOffsetS3 = 0;' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'LOG_ADD(LOG_FLOAT, surfOffset, &surfaceOffset)' src/modules/src/estimator/estimator_ukf.c
  grep -Fq 'PARAM_ADD(PARAM_UINT8, surfaceOffsetS3, &surfaceOffsetS3)' src/modules/src/estimator/estimator_ukf.c

  docker run --rm -v "$PWD:/module" bitcraze/builder bash -lc '
    set -euo pipefail
    make cf2_defconfig
    # Flow Deck support selects ESTIMATOR_KALMAN_ENABLE as compiled support.
    # Keep that stock dependency; select UKF as the default estimator instead.
    cat > /tmp/s3-ukf-default.config <<'EOF'
# CONFIG_ESTIMATOR_AUTO_SELECT is not set
CONFIG_ESTIMATOR_UKF_ENABLE=y
CONFIG_ESTIMATOR_UKF=y
EOF
    ./scripts/kconfig/merge_config.sh -O build -m build/.config /tmp/s3-ukf-default.config
    make olddefconfig
    grep -q "^CONFIG_DECK_FLOW=y$" build/.config
    grep -q "^CONFIG_ESTIMATOR_KALMAN_ENABLE=y$" build/.config
    grep -q "^# CONFIG_ESTIMATOR_AUTO_SELECT is not set$" build/.config
    grep -q "^CONFIG_ESTIMATOR_UKF_ENABLE=y$" build/.config
    grep -q "^CONFIG_ESTIMATOR_UKF=y$" build/.config
    ./tools/build/build UNIT_TEST_STYLE=min
  '

  test -s build/cf2.elf
  test -s build/cf2.bin
  find build -type f -name 'estimator_ukf.o' -size +0c -print -quit | grep -q .
)

printf '%s\n' "PASS: exact Crazyflie 2026.08 S3 source applied and UKF-enabled cf2 firmware built."
