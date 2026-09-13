#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <exact-cflib-source-root> <exact-wheelhouse>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CFLIB_SOURCE="$(cd "$1" && pwd)"
WHEELHOUSE="$(cd "$2" && pwd)"
LOCK="$ROOT/tools/physical/qualification_runtime_lock.txt"
ISOLATED_ROOT=''
cleanup() {
  if [ -n "$ISOLATED_ROOT" ]; then
    rm -rf "$ISOLATED_ROOT"
  fi
}
trap cleanup EXIT

python3 - <<'PY'
import platform
import sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"FAIL: Python 3.10 required, got {sys.version}")
if platform.system() != "Linux" or platform.machine() != "x86_64":
    raise SystemExit(f"FAIL: Linux x86_64 required, got {platform.system()} {platform.machine()}")
PY

test -d "$CFLIB_SOURCE/cflib"
test -s "$LOCK"
test -d "$WHEELHOUSE"

expected="$(mktemp "${TMPDIR:-/tmp}/webeeblocks-qualification-wheel-sha256.XXXXXX")"
trap 'rm -f "$expected"; cleanup' EXIT
count=0
while IFS='|' read -r spec filename digest; do
  case "$spec" in ''|'#'*) continue ;; esac
  test -f "$WHEELHOUSE/$filename"
  printf '%s  %s\n' "$digest" "$WHEELHOUSE/$filename" >> "$expected"
  count=$((count + 1))
done < "$LOCK"
if [ "$count" -ne 7 ]; then
  echo "FAIL: exact seven-wheel physical qualification closure required" >&2
  exit 2
fi
if [ "$(find "$WHEELHOUSE" -maxdepth 1 -type f -name '*.whl' | wc -l)" -ne 7 ]; then
  echo "FAIL: wheelhouse contains files outside the exact seven-wheel closure" >&2
  exit 2
fi
sha256sum -c "$expected"

ISOLATED_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/webeeblocks-physical-qualification.XXXXXX")"
ISOLATED_SITE="$ISOLATED_ROOT/site"
HOSTILE="$ISOLATED_ROOT/hostile"
mkdir -p "$ISOLATED_SITE" "$HOSTILE"

shopt -s nullglob
WHEELS=("$WHEELHOUSE"/*.whl)
shopt -u nullglob
python3 -m pip install --disable-pip-version-check \
  --no-index --no-deps --ignore-installed \
  --target "$ISOLATED_SITE" \
  "${WHEELS[@]}"

for module in cflib usb libusb_package importlib_resources numpy scipy packaging yaml; do
  mkdir -p "$HOSTILE/$module"
  printf '%s\n' 'raise RuntimeError("hostile ambient package must never be imported")' > "$HOSTILE/$module/__init__.py"
done

run_isolated() {
  PYTHONPATH="$CFLIB_SOURCE:$ISOLATED_SITE" \
  PYTHONNOUSERSITE=1 \
  python3 -S "$@"
}

PYTHONPATH="$HOSTILE" run_isolated - "$CFLIB_SOURCE" "$ISOLATED_SITE" "$HOSTILE" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).resolve()
site = pathlib.Path(sys.argv[2]).resolve()
hostile = pathlib.Path(sys.argv[3]).resolve()
if hostile in map(pathlib.Path, sys.path):
    raise SystemExit(f"FAIL: hostile ambient path leaked into isolated sys.path: {sys.path!r}")

import cflib
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils.power_switch import PowerSwitch
import importlib_resources
import libusb_package
import numpy
import packaging
import scipy
import usb
import yaml

if source not in pathlib.Path(cflib.__file__).resolve().parents:
    raise SystemExit(f"FAIL: cflib escaped exact bundled source: {cflib.__file__}")

for module in (importlib_resources, libusb_package, numpy, packaging, scipy, usb, yaml):
    module_path = pathlib.Path(module.__file__).resolve()
    if site not in module_path.parents:
        raise SystemExit(f"FAIL: dependency escaped isolated wheel closure: {module.__name__} -> {module_path}")

for imported in (Crazyflie, LogConfig, SyncCrazyflie, PowerSwitch):
    if source not in pathlib.Path(sys.modules[imported.__module__].__file__).resolve().parents:
        raise SystemExit(f"FAIL: cflib runtime import escaped exact source: {imported.__module__}")

print("PASS: exact cflib execution imports and seven-wheel dependency closure are isolated")
PY

PYTHONPATH="$HOSTILE" run_isolated "$ROOT/tools/physical/launch_physical_qualification.py" --help >/dev/null
PYTHONPATH="$HOSTILE" run_isolated "$ROOT/tools/physical/serve_physical_host.py" --help >/dev/null

echo "PASS: qualification launcher and trusted host import under python3 -S without hardware access"
