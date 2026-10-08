#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/.runtime/venv"
LOCK="$ROOT/tools/physical/qualification_runtime_lock.txt"
WHEELHOUSE="$ROOT/support/wheels"
CFLIB="$ROOT/support/cflib-source"
QUALIFICATION_WORLD_SOURCE="$ROOT/tools/physical/qualification_world.wbt"
QUALIFICATION_PERSPECTIVE_ENTRY="$ROOT/tools/physical/qualification_perspective.py"
PREPARATION_RECORD=""
PREPARATION_URI=""
RUN_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --preparation-record)
      test "$#" -ge 2
      test -z "$PREPARATION_RECORD"
      PREPARATION_RECORD="$2"; shift 2 ;;
    --uri)
      test "$#" -ge 2
      test -z "$PREPARATION_URI"
      PREPARATION_URI="$2"; RUN_ARGS+=("$1" "$2"); shift 2 ;;
    --uri=*)
      test -z "$PREPARATION_URI"
      PREPARATION_URI="${1#--uri=}"; RUN_ARGS+=("$1"); shift ;;
    *) RUN_ARGS+=("$1"); shift ;;
  esac
done
if [ -z "$PREPARATION_RECORD" ] || [ -z "$PREPARATION_URI" ]; then
  echo "FAIL: --uri and an exact --preparation-record are required before physical qualification" >&2
  exit 2
fi

# Verification and later imports must be observational with respect to the
# manifest-covered source tree.
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

python3 "$ROOT/tools/physical/verify_physical_qualification_package.py" "$ROOT" --manifest-only
python3 "$ROOT/tools/physical/verify_qualification_world.py" "$QUALIFICATION_WORLD_SOURCE"

python3 - <<'PY'
import platform, sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"Python 3.10 required, got {sys.version.split()[0]}")
if platform.system() != "Linux" or platform.machine() != "x86_64":
    raise SystemExit(f"Linux x86_64 required, got {platform.system()} {platform.machine()}")
PY

if [[ -n "${WEBOTS:-}" ]]; then
  WEBOTS_BIN="$WEBOTS"
elif [[ -n "${WEBOTS_HOME:-}" ]]; then
  WEBOTS_BIN="$WEBOTS_HOME/webots"
else
  WEBOTS_BIN="$(command -v webots || true)"
fi
if [[ -z "$WEBOTS_BIN" || ! -x "$WEBOTS_BIN" ]]; then
  echo "FAIL: exact Webots R2025a executable not found; set WEBOTS or WEBOTS_HOME" >&2
  exit 1
fi
webots_version="$($WEBOTS_BIN --version 2>&1 || true)"
if [[ "$webots_version" != *R2025a* ]]; then
  echo "FAIL: Webots R2025a required; observed: $webots_version" >&2
  exit 1
fi

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

export PYTHONPATH="$ROOT/tools/physical:$CFLIB"
QUALIFICATION_LOG="$(mktemp "$ROOT/physical-qualification-XXXXXXXX.log")"
echo "Diagnostic conservé : $QUALIFICATION_LOG"
cat "$ROOT/SOURCE_SHA" > "$QUALIFICATION_LOG"
"$VENV/bin/python" -B "$ROOT/tools/physical/prepare_physical_flight.py" \
  --verify-record "$PREPARATION_RECORD" --uri "$PREPARATION_URI" 2>&1 | tee -a "$QUALIFICATION_LOG"

chmod u+x "$ROOT/controllers/crazyflie_runtime_v2/crazyflie_runtime_v2"

# Fail closed before opening Crazyradio or Webots unless the exact final
# ephemeral-world/perspective lifecycle is proven against the real
# launch_physical_qualification.py preparation seam.
"$VENV/bin/python" "$QUALIFICATION_PERSPECTIVE_ENTRY" --self-test

# The supported Ubuntu Webots package does not guarantee the optional project
# PROTO tree used by the simulation world. Physical qualification needs only a
# local Robot Window host, so materialize the manifest-covered self-contained
# shell inside the package's worlds/ directory to keep normal controller/project
# discovery while introducing no network or system-project dependency.
QUALIFICATION_WORLD="$(mktemp "$ROOT/worlds/.webeeblocks-qualification-source-XXXXXXXX.wbt")"
trap 'rm -f "$QUALIFICATION_WORLD"' EXIT
cp "$QUALIFICATION_WORLD_SOURCE" "$QUALIFICATION_WORLD"

"$VENV/bin/python" "$QUALIFICATION_PERSPECTIVE_ENTRY" "${RUN_ARGS[@]}" \
  --webots "$WEBOTS_BIN" \
  --world "$QUALIFICATION_WORLD" 2>&1 | tee -a "$QUALIFICATION_LOG"
