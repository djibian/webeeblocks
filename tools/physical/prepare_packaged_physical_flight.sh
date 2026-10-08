#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/.runtime/flight-preparation-venv"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
python3 "$ROOT/tools/physical/verify_physical_qualification_package.py" "$ROOT" --manifest-only
python3 - <<'PY'
import platform, sys
if sys.version_info[:2] != (3, 10) or platform.system() != "Linux" or platform.machine() != "x86_64":
    raise SystemExit("Python 3.10 / Linux x86_64 required for physical preparation")
PY
rm -rf "$VENV"
python3 -m venv "$VENV"
wheels=()
while IFS='|' read -r spec filename digest; do
  case "$spec" in ''|'#'*) continue ;; esac
  test -f "$ROOT/support/wheels/$filename"
  wheels+=("$ROOT/support/wheels/$filename")
done < "$ROOT/tools/physical/qualification_runtime_lock.txt"
test "${#wheels[@]}" -eq 7
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-index --no-deps --no-compile "${wheels[@]}"
export PYTHONPATH="$ROOT/tools/physical:$ROOT/support/cflib-source"
"$VENV/bin/python" -B "$ROOT/tools/physical/prepare_physical_flight.py" "$@"
