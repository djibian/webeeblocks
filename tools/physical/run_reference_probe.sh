#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 radio://<dongle>/<channel>/<rate>/<address>" >&2
  exit 2
fi

URI="$1"
case "$URI" in
  radio://*) ;;
  *)
    echo "Exact Crazyradio radio:// URI required" >&2
    exit 2
    ;;
esac

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/physical-capability-descriptor.json"
ISOLATED_SITE=''
cleanup() {
  if [ -n "$ISOLATED_SITE" ]; then
    rm -rf "$(dirname "$ISOLATED_SITE")"
  fi
}
trap cleanup EXIT

cd "$HERE"
test -s SHA256SUMS
sha256sum -c SHA256SUMS
test -s PROVENANCE.txt
grep -Fxq 'cflib_source=https://github.com/bitcraze/crazyflie-lib-python.git' PROVENANCE.txt
grep -Fxq 'cflib_commit=45fdb784c9d13074c42835f3b5ac1d12133bf873' PROVENANCE.txt

shopt -s nullglob
CFLIB_WHEELS=("$HERE"/wheels/cflib-*.whl)
shopt -u nullglob
if [ "${#CFLIB_WHEELS[@]}" -ne 1 ] || [ ! -f "${CFLIB_WHEELS[0]}" ]; then
  echo "FAIL: exact packaged cflib wheel is missing or ambiguous" >&2
  exit 2
fi

ISOLATED_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/webeeblocks-physical-probe.XXXXXX")"
ISOLATED_SITE="$ISOLATED_ROOT/site"
mkdir -p "$ISOLATED_SITE"

python3 -m pip install --disable-pip-version-check \
  --no-index \
  --find-links "$HERE/wheels" \
  --ignore-installed \
  --target "$ISOLATED_SITE" \
  "${CFLIB_WHEELS[0]}"

PYTHONPATH="$ISOLATED_SITE" PYTHONNOUSERSITE=1 python3 -S - "$ISOLATED_SITE" <<'PY'
import pathlib
import sys
import cflib

site = pathlib.Path(sys.argv[1]).resolve()
module = pathlib.Path(cflib.__file__).resolve()
if site not in module.parents:
    raise SystemExit(f"FAIL: cflib escaped isolated bundle: {module}")
print(f"Using packaged cflib: {module}")
PY

PYTHONPATH="$ISOLATED_SITE" PYTHONNOUSERSITE=1 \
  python3 -S "$HERE/probe_reference_hardware.py" --uri "$URI" --pretty |
  tee "$OUT"

PYTHONPATH="$ISOLATED_SITE" PYTHONNOUSERSITE=1 python3 -S - "$OUT" <<'PY'
import json
import sys
from pathlib import Path

descriptor = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_hardware = {"flow-deck-v2", "multi-ranger-deck", "color-led-deck"}

if descriptor.get("executionAuthority") is not False:
    raise SystemExit("FAIL: executionAuthority must remain false")
identity = descriptor.get("identity") or {}
if identity != {
    "family": "crazyflie",
    "model": "crazyflie-2.1",
    "modelEvidence": "verified",
}:
    raise SystemExit(f"FAIL: exact Crazyflie 2.1 identity not verified: {identity!r}")
hardware = set(descriptor.get("hardware") or [])
missing = expected_hardware - hardware
if missing:
    raise SystemExit(f"FAIL: required reference hardware not healthy/present: {sorted(missing)!r}")

capabilities = descriptor.get("capabilities") or {}
required_actions = {"takeoff", "move", "vertical", "turn", "wait", "set_speed", "set_light", "land"}
missing_actions = required_actions - set(capabilities.get("actions") or [])
if missing_actions:
    raise SystemExit(f"FAIL: required action capability evidence missing: {sorted(missing_actions)!r}")
if set(capabilities.get("rangeDirections") or []) != {"front", "back", "left", "right", "up"}:
    raise SystemExit(f"FAIL: unexpected Multi-ranger directions: {capabilities.get('rangeDirections')!r}")
if set(capabilities.get("moveDirections") or []) != {"forward", "back", "left", "right"}:
    raise SystemExit(f"FAIL: unexpected move directions: {capabilities.get('moveDirections')!r}")
if set(capabilities.get("verticalDirections") or []) != {"up", "down"}:
    raise SystemExit(f"FAIL: unexpected vertical directions: {capabilities.get('verticalDirections')!r}")

print("PASS: exact reference hardware capability descriptor observed with executionAuthority=false")
PY
