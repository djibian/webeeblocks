#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
# Existing exact five-wheel/firmware/runtime and no-Commander evidence, no device.
bash "$HERE/run_x3_independent_capture.sh" --verify-environment
ISOLATED_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/webeeblocks-x3-interval.XXXXXXXX")"
trap 'rm -rf "$ISOLATED_ROOT"' EXIT
wheels=()
while IFS='|' read -r spec filename digest; do
  case "$spec" in ''|'#'*) continue ;; esac
  test "$(sha256sum "$HERE/wheels/$filename" | awk '{print $1}')" = "$digest"
  wheels+=("$HERE/wheels/$filename")
done < "$HERE/x3_runtime_lock.txt"
test "${#wheels[@]}" -eq 5
python3 -B -m pip install --disable-pip-version-check --no-index --no-deps \
  --ignore-installed --no-compile --target "$ISOLATED_ROOT/site" "${wheels[@]}" >/dev/null
export PYTHONPATH="$HERE/cflib-source:$ISOLATED_ROOT/site"
python3 -B -S "$HERE/diagnose_x3_interval.py" --help >/dev/null
python3 -B "$HERE/verify_x3_characterization_bundle.py" "$HERE"
if [ "$#" -eq 1 ] && [ "$1" = '--verify-environment' ]; then
  echo 'PASS: exact offline interval diagnostic imports without hardware'
  exit 0
fi
python3 -B -S "$HERE/diagnose_x3_interval.py" "$@"
