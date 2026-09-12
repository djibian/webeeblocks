#!/usr/bin/env bash
set -euo pipefail

CALLER_PWD="$(pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
EXPECTED_FIRMWARE_SHA256="67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738"
EXPECTED_CFLIB_COMMIT="45fdb784c9d13074c42835f3b5ac1d12133bf873"
EXPECTED_CFLIB_TREE="a78cf78d2b4aba51a0fa2b03de0260664b523401"
EXPECTED_CFLIB_SUBTREE="750e850390753de14019f0e1f55d4fbc44317699"

usage() {
  cat >&2 <<'EOF'
Usage:
  run_x3_independent_capture.sh --verify-environment
  run_x3_independent_capture.sh \
    --uri radio://<dongle>/<channel>/<rate>/<address> \
    --checkpoint-url https://github.com/djibian/webeeblocks/issues/<N> \
    --request-sha <40-char-sha> \
    --seconds <30..300> \
    --output <new-directory> \
    --props-removed \
    --installed-bin-confirmed

This runner only records props-off X3 evidence through the bundled collector.
It never flashes firmware, changes estimator parameters, publishes evidence, or
performs a motorized action. The operator must explicitly confirm that the props
are removed and that the exact bundled cf2.bin has already been installed.
EOF
  exit 2
}

VERIFY_ONLY=0
URI=""
CHECKPOINT_URL=""
REQUEST_SHA=""
DURATION_SECONDS=""
OUTPUT=""
PROPS_REMOVED=0
INSTALLED_BIN_CONFIRMED=0

if [ "$#" -eq 1 ] && [ "$1" = "--verify-environment" ]; then
  VERIFY_ONLY=1
else
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --uri)
        [ "$#" -ge 2 ] || usage
        URI="$2"
        shift 2
        ;;
      --checkpoint-url)
        [ "$#" -ge 2 ] || usage
        CHECKPOINT_URL="$2"
        shift 2
        ;;
      --request-sha)
        [ "$#" -ge 2 ] || usage
        REQUEST_SHA="$2"
        shift 2
        ;;
      --seconds)
        [ "$#" -ge 2 ] || usage
        DURATION_SECONDS="$2"
        shift 2
        ;;
      --output)
        [ "$#" -ge 2 ] || usage
        OUTPUT="$2"
        shift 2
        ;;
      --props-removed)
        PROPS_REMOVED=1
        shift
        ;;
      --installed-bin-confirmed)
        INSTALLED_BIN_CONFIRMED=1
        shift
        ;;
      *) usage ;;
    esac
  done
  [ -n "$URI" ] && [ -n "$CHECKPOINT_URL" ] && [ -n "$REQUEST_SHA" ] && \
    [ -n "$DURATION_SECONDS" ] && [ -n "$OUTPUT" ] || usage
  [ "$PROPS_REMOVED" -eq 1 ] && [ "$INSTALLED_BIN_CONFIRMED" -eq 1 ] || usage
  case "$OUTPUT" in
    /*) ;;
    *) OUTPUT="$CALLER_PWD/$OUTPUT" ;;
  esac
fi

cd "$HERE"
test -s SHA256SUMS
sha256sum -c SHA256SUMS

test -s PROVENANCE.txt
grep -Fxq "cflib_commit=$EXPECTED_CFLIB_COMMIT" PROVENANCE.txt
grep -Fxq "cflib_tree=$EXPECTED_CFLIB_TREE" PROVENANCE.txt
grep -Fxq "cflib_subtree=$EXPECTED_CFLIB_SUBTREE" PROVENANCE.txt
grep -Fxq 'runtime=ubuntu-22.04-python-3.10-x86_64' PROVENANCE.txt
grep -Fxq "firmware_bin_sha256=$EXPECTED_FIRMWARE_SHA256" PROVENANCE.txt
mapfile -t TARGET_LINES < <(sed -n 's/^repository_target_sha=//p' PROVENANCE.txt)
if [ "${#TARGET_LINES[@]}" -ne 1 ] || ! [[ "${TARGET_LINES[0]}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "FAIL: exactly one valid repository_target_sha is required" >&2
  exit 2
fi
BUNDLE_TARGET_SHA="${TARGET_LINES[0]}"

test -s "$HERE/cf2.bin"
test "$(sha256sum "$HERE/cf2.bin" | awk '{print $1}')" = "$EXPECTED_FIRMWARE_SHA256"
test -s "$HERE/capture_independent_inputs.py"
test -d "$HERE/cflib-source/cflib"
test -d "$HERE/wheels"

python3 - <<'PY'
import platform
import sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"FAIL: Python 3.10 required, got {sys.version}")
if platform.system() != "Linux" or platform.machine() != "x86_64":
    raise SystemExit(
        f"FAIL: Linux x86_64 required, got {platform.system()} {platform.machine()}"
    )
PY

ISOLATED_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/webeeblocks-x3-capture.XXXXXX")"
cleanup() {
  rm -rf "$ISOLATED_ROOT"
}
trap cleanup EXIT
ISOLATED_SITE="$ISOLATED_ROOT/site"
mkdir -p "$ISOLATED_SITE"

shopt -s nullglob
WHEELS=("$HERE"/wheels/*.whl)
shopt -u nullglob
if [ "${#WHEELS[@]}" -ne 4 ]; then
  echo "FAIL: exact four-wheel cflib runtime closure required" >&2
  exit 2
fi

python3 -m pip install --disable-pip-version-check \
  --no-index --no-deps --ignore-installed \
  --target "$ISOLATED_SITE" \
  "${WHEELS[@]}"

PYTHONPATH="$HERE/cflib-source:$ISOLATED_SITE" PYTHONNOUSERSITE=1 \
python3 -S - "$HERE/cflib-source" "$ISOLATED_SITE" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).resolve()
site = pathlib.Path(sys.argv[2]).resolve()

import cflib
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
import libusb_package
import importlib_resources
import numpy
import usb

if source not in pathlib.Path(cflib.__file__).resolve().parents:
    raise SystemExit(f"FAIL: cflib escaped exact bundled source: {cflib.__file__}")
for module in (libusb_package, importlib_resources, numpy, usb):
    module_path = pathlib.Path(module.__file__).resolve()
    if site not in module_path.parents:
        raise SystemExit(
            f"FAIL: dependency escaped isolated wheelhouse: {module.__name__} -> {module_path}"
        )
print("PASS: exact offline X3 cflib runtime closure is isolated")
PY

PYTHONPATH="$HERE/cflib-source:$ISOLATED_SITE" PYTHONNOUSERSITE=1 \
  python3 -S "$HERE/capture_independent_inputs.py" --describe >/dev/null

if [ "$VERIFY_ONLY" -eq 1 ]; then
  echo "PASS: X3 capture bundle verified without hardware"
  exit 0
fi

case "$DURATION_SECONDS" in
  ''|*[!0-9]*) usage ;;
esac
if [ "$DURATION_SECONDS" -lt 30 ] || [ "$DURATION_SECONDS" -gt 300 ]; then
  usage
fi
if ! [[ "$REQUEST_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  usage
fi
if [ "$REQUEST_SHA" != "$BUNDLE_TARGET_SHA" ]; then
  echo "FAIL: request SHA does not match bundled repository target" >&2
  exit 2
fi
if ! [[ "$CHECKPOINT_URL" =~ ^https://github.com/djibian/webeeblocks/issues/[1-9][0-9]*$ ]]; then
  usage
fi
if ! [[ "$URI" =~ ^radio://[0-9]+/[0-9]+/(250K|1M|2M)(/[0-9A-Fa-f]+)?$ ]]; then
  usage
fi

PYTHONPATH="$HERE/cflib-source:$ISOLATED_SITE" PYTHONNOUSERSITE=1 \
python3 -S "$HERE/capture_independent_inputs.py" \
  --uri "$URI" \
  --checkpoint-url "$CHECKPOINT_URL" \
  --request-sha "$REQUEST_SHA" \
  --firmware-bin "$HERE/cf2.bin" \
  --output "$OUTPUT" \
  --seconds "$DURATION_SECONDS" \
  --props-removed \
  --installed-bin-confirmed
