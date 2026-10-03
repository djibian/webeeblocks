#!/usr/bin/env bash
set -euo pipefail

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
EXPECTED_FIRMWARE_SHA256="67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738"
EXPECTED_CFLIB_COMMIT="45fdb784c9d13074c42835f3b5ac1d12133bf873"
EXPECTED_CFLIB_TREE="a78cf78d2b4aba51a0fa2b03de0260664b523401"
EXPECTED_CFLIB_SUBTREE="750e850390753de14019f0e1f55d4fbc44317699"
EXPECTED_UPSTREAM_FIRMWARE_COMMIT="54f31e243a0b28b67efef5ba20dbb6d9890a5478"
EXPECTED_TEST_PROFILE="x3-independent-props-off"

usage() {
  cat <<'EOF'
Usage:
  ./prepare_x3_independent_capture.sh --verify-environment
  ./prepare_x3_independent_capture.sh \
    --uri radio://0/80/2M/E7E7E7E7E7 \
    --output /path/to/new-preparation-directory \
    --props-removed

This is a distinct pre-acquisition effect phase. With --props-removed it:
  1. verifies the exact signed-by-manifest X3 bundle and runtime;
  2. flashes only the exact bundled #251 cf2.bin to cf2/stm32/fw;
  3. writes only the four predeclared X3 configuration parameters when needed;
  4. requests ukf.resetEstimation uint8_t=1, requires a fresh observation of
     the firmware-owned auto-clear to 0 within 0.25 s, then preserves the
     historical explicit client 0 release after the 0.25 s client delay;
  5. waits the fixed 5 s post-reset settling interval and verifies broad,
     predeclared estimator-health bounds;
  6. writes preparation.json.

It never arms, invokes a commander, runs motors, tunes parameters or starts a
scientific capture. Keep the Crazyflie stationary during post-reset settling.
Do not power-cycle the Crazyflie between PREPARED and the read-only acquisition
that consumes preparation.json.
EOF
}

verify_bundle() {
  python3 -B "$HERE/verify_x3_characterization_bundle.py" "$HERE"
}

verify_static_inputs() {
  test -f "$HERE/cf2.bin"
  test -f "$HERE/PROVENANCE.txt"
  test -f "$HERE/x3_runtime_lock.txt"
  test -f "$HERE/prepare_x3_independent_capture.py"
  test -f "$HERE/x3_no_commander_link.py"
  test -d "$HERE/cflib-source/cflib"
  test -d "$HERE/wheels"

  test "$(sha256sum "$HERE/cf2.bin" | awk '{print $1}')" = "$EXPECTED_FIRMWARE_SHA256"
  grep -Fxq "test_profile=$EXPECTED_TEST_PROFILE" "$HERE/PROVENANCE.txt"
  grep -Fxq "firmware_bin_sha256=$EXPECTED_FIRMWARE_SHA256" "$HERE/PROVENANCE.txt"
  grep -Fxq "upstream_firmware_commit=$EXPECTED_UPSTREAM_FIRMWARE_COMMIT" "$HERE/PROVENANCE.txt"
  grep -Fxq "cflib_commit=$EXPECTED_CFLIB_COMMIT" "$HERE/PROVENANCE.txt"
  grep -Fxq "cflib_tree=$EXPECTED_CFLIB_TREE" "$HERE/PROVENANCE.txt"
  grep -Fxq "cflib_subtree=$EXPECTED_CFLIB_SUBTREE" "$HERE/PROVENANCE.txt"

  test "$(uname -s)" = "Linux"
  test "$(uname -m)" = "x86_64"
  python3 - <<'PY'
import sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"Python 3.10 required, found {sys.version.split()[0]}")
PY
}

make_runtime() {
  ISOLATED_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/webeeblocks-x3-prep.XXXXXXXX")"
  ISOLATED_SITE="$ISOLATED_ROOT/site"
  mkdir -p "$ISOLATED_SITE"

  mapfile -t LOCK_ROWS < <(grep -Ev '^[[:space:]]*(#|$)' "$HERE/x3_runtime_lock.txt")
  test "${#LOCK_ROWS[@]}" -eq 5

  local specs=()
  local spec filename digest
  for row in "${LOCK_ROWS[@]}"; do
    IFS='|' read -r spec filename digest <<<"$row"
    test -n "$spec"
    test -n "$filename"
    [[ "$digest" =~ ^[0-9a-f]{64}$ ]]
    test -f "$HERE/wheels/$filename"
    test "$(sha256sum "$HERE/wheels/$filename" | awk '{print $1}')" = "$digest"
    specs+=("$HERE/wheels/$filename")
  done

  python3 -m pip install \
    --disable-pip-version-check \
    --no-index \
    --no-deps \
    --target "$ISOLATED_SITE" \
    "${specs[@]}" >/dev/null

  export PYTHONPATH="$HERE/cflib-source:$ISOLATED_SITE"
  export PYTHONNOUSERSITE=1
  export PYTHONDONTWRITEBYTECODE=1

  python3 -B -S - <<'PY'
from pathlib import Path

import cflib
import packaging
import usb
from cflib.bootloader import Bootloader, Target
from cflib.crazyflie import Crazyflie

if not Path(cflib.__file__).resolve().as_posix().endswith("/cflib-source/cflib/__init__.py"):
    raise SystemExit("cflib did not load from exact bundled source")
for module in (packaging, usb):
    if "/site/" not in Path(module.__file__).resolve().as_posix():
        raise SystemExit(f"{module.__name__} did not load from isolated locked wheels")
# Importing these symbols is the hardware-free proof that the exact physical
# preparation import closure is complete. No object is constructed here.
assert Bootloader and Target and Crazyflie
PY
}

cleanup() {
  if [[ -n "${ISOLATED_ROOT:-}" && -d "$ISOLATED_ROOT" ]]; then
    rm -rf -- "$ISOLATED_ROOT"
  fi
}
trap cleanup EXIT

MODE="prepare"
URI=""
OUTPUT=""
PROPS_REMOVED=0

while (($#)); do
  case "$1" in
    --verify-environment)
      MODE="verify"
      shift
      ;;
    --uri)
      URI="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    --props-removed)
      PROPS_REMOVED=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

verify_bundle
verify_static_inputs
make_runtime
python3 -B -S "$HERE/x3_no_commander_link.py"
python3 -B -S "$HERE/prepare_x3_independent_capture.py" --self-test

if [[ "$MODE" == "verify" ]]; then
  verify_bundle
  echo "PASS: exact X3 preparation environment verified; no hardware effect performed"
  exit 0
fi

if [[ -z "$URI" || -z "$OUTPUT" || "$PROPS_REMOVED" -ne 1 ]]; then
  usage >&2
  exit 2
fi
if [[ -e "$OUTPUT" ]]; then
  echo "Preparation output already exists: $OUTPUT" >&2
  exit 2
fi

python3 -B -S "$HERE/prepare_x3_independent_capture.py" \
  --uri "$URI" \
  --firmware-bin "$HERE/cf2.bin" \
  --provenance "$HERE/PROVENANCE.txt" \
  --output "$OUTPUT" \
  --props-removed

verify_bundle
echo "PREPARED: use $OUTPUT/preparation.json as the read-only acquisition gate"
