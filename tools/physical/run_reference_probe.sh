#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 --verify-environment | radio://<dongle>/<channel>/<rate>/<address>" >&2
  exit 2
fi

MODE="$1"
case "$MODE" in
  --verify-environment) ;;
  radio://*) ;;
  *)
    echo "Exact Crazyradio radio:// URI or --verify-environment required" >&2
    exit 2
    ;;
esac

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/physical-capability-descriptor.json"
ISOLATED_ROOT=''
cleanup() {
  if [ -n "$ISOLATED_ROOT" ]; then
    rm -rf "$ISOLATED_ROOT"
  fi
}
trap cleanup EXIT

cd "$HERE"
test -s SHA256SUMS
sha256sum -c SHA256SUMS
test -s PROVENANCE.txt
grep -Fxq 'cflib_commit=45fdb784c9d13074c42835f3b5ac1d12133bf873' PROVENANCE.txt
grep -Fxq 'cflib_tree=a78cf78d2b4aba51a0fa2b03de0260664b523401' PROVENANCE.txt
grep -Fxq 'cflib_subtree=750e850390753de14019f0e1f55d4fbc44317699' PROVENANCE.txt
grep -Fxq 'runtime=ubuntu-22.04-python-3.10-x86_64' PROVENANCE.txt

python3 - <<'PY'
import platform
import sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"FAIL: Python 3.10 required, got {sys.version}")
if platform.system() != "Linux" or platform.machine() != "x86_64":
    raise SystemExit(f"FAIL: Linux x86_64 required, got {platform.system()} {platform.machine()}")
PY

test -d "$HERE/cflib-source/cflib"
test -d "$HERE/wheels"
test -s "$HERE/reference_probe_lock.txt"

ISOLATED_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/webeeblocks-physical-probe.XXXXXX")"
ISOLATED_SITE="$ISOLATED_ROOT/site"
mkdir -p "$ISOLATED_SITE"

shopt -s nullglob
WHEELS=("$HERE"/wheels/*.whl)
shopt -u nullglob
if [ "${#WHEELS[@]}" -ne 4 ]; then
  echo "FAIL: exact four-wheel runtime closure required" >&2
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
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
import libusb_package
import importlib_resources
import numpy
import usb

if source not in pathlib.Path(cflib.__file__).resolve().parents:
    raise SystemExit(f"FAIL: cflib escaped exact bundled source: {cflib.__file__}")

for module in (libusb_package, importlib_resources, numpy, usb):
    module_path = pathlib.Path(module.__file__).resolve()
    if site not in module_path.parents:
        raise SystemExit(f"FAIL: dependency escaped isolated wheelhouse: {module.__name__} -> {module_path}")

print(f"Using exact bundled cflib: {pathlib.Path(cflib.__file__).resolve()}")
print("PASS: exact offline cflib runtime closure is isolated")
PY

if [ "$MODE" = "--verify-environment" ]; then
  echo "PASS: packaged cflib source and four-wheel closure verified without hardware"
  exit 0
fi

PYTHONPATH="$HERE/cflib-source:$ISOLATED_SITE" PYTHONNOUSERSITE=1 \
  python3 -S "$HERE/probe_reference_hardware.py" --uri "$MODE" --pretty |
  tee "$OUT"

PYTHONPATH="$HERE/cflib-source:$ISOLATED_SITE" PYTHONNOUSERSITE=1 python3 -S - "$OUT" <<'PY'
import json
import sys
from pathlib import Path

descriptor = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_hardware = {"flow-deck-v2", "multi-ranger-deck", "color-led-deck"}
if descriptor.get("executionAuthority") is not False:
    raise SystemExit("FAIL: executionAuthority must remain false")
if descriptor.get("identity") != {
    "family": "crazyflie",
    "model": "crazyflie-2.1",
    "modelEvidence": "verified",
}:
    raise SystemExit(f"FAIL: exact Crazyflie 2.1 identity not verified: {descriptor.get('identity')!r}")
hardware = set(descriptor.get("hardware") or [])
missing = expected_hardware - hardware
if missing:
    raise SystemExit(f"FAIL: required reference hardware not healthy/present: {sorted(missing)!r}")
capabilities = descriptor.get("capabilities") or {}
required_actions = {"takeoff", "move", "vertical", "turn", "wait", "set_speed", "set_light", "land"}
missing_actions = required_actions - set(capabilities.get("actions") or [])
if missing_actions:
    raise SystemExit(f"FAIL: required action evidence missing: {sorted(missing_actions)!r}")
if set(capabilities.get("rangeDirections") or []) != {"front", "back", "left", "right", "up"}:
    raise SystemExit(f"FAIL: unexpected range directions: {capabilities.get('rangeDirections')!r}")
if set(capabilities.get("moveDirections") or []) != {"forward", "back", "left", "right"}:
    raise SystemExit(f"FAIL: unexpected move directions: {capabilities.get('moveDirections')!r}")
if set(capabilities.get("verticalDirections") or []) != {"up", "down"}:
    raise SystemExit(f"FAIL: unexpected vertical directions: {capabilities.get('verticalDirections')!r}")
print("PASS: exact reference hardware capability descriptor observed with executionAuthority=false")
PY
