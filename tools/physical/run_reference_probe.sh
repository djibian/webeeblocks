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

python3 "$HERE/probe_reference_hardware.py" --uri "$URI" --pretty | tee "$OUT"

python3 - "$OUT" <<'PY'
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
