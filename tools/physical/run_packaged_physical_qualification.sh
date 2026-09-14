#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/.runtime/venv"
LOCK="$ROOT/tools/physical/qualification_runtime_lock.txt"
WHEELHOUSE="$ROOT/support/wheels"
CFLIB="$ROOT/support/cflib-source"

python3 "$ROOT/tools/physical/verify_physical_qualification_package.py" "$ROOT" --manifest-only

python3 - <<'PY'
import platform, sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"Python 3.10 required, got {sys.version.split()[0]}")
if platform.system() != "Linux" or platform.machine() != "x86_64":
    raise SystemExit(f"Linux x86_64 required, got {platform.system()} {platform.machine()}")
PY

rm -rf "$VENV"
python3 -m venv "$VENV"

wheels=()
while IFS='|' read -r spec filename digest; do
  case "$spec" in ''|'#'*) continue ;; esac
  test -f "$WHEELHOUSE/$filename"
  wheels+=("$WHEELHOUSE/$filename")
done < "$LOCK"
test "${#wheels[@]}" -eq 7

"$VENV/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-index \
  --no-deps \
  --no-compile \
  "${wheels[@]}"

chmod u+x "$ROOT/controllers/crazyflie_runtime_v2/crazyflie_runtime_v2"

export PYTHONNOUSERSITE=1
export PYTHONPATH="$ROOT/tools/physical:$CFLIB"
exec "$VENV/bin/python" "$ROOT/tools/physical/launch_physical_qualification.py" "$@"
