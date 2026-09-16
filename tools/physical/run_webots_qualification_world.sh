#!/usr/bin/env bash
set -euo pipefail

REAL_WEBOTS="${WEBEEBLOCKS_REAL_WEBOTS:-}"
PERSPECTIVE_SOURCE="${WEBEEBLOCKS_QUALIFICATION_PERSPECTIVE:-}"

if [[ -z "$REAL_WEBOTS" || ! -x "$REAL_WEBOTS" ]]; then
  echo "FAIL: exact real Webots executable is unavailable to qualification wrapper" >&2
  exit 1
fi
if [[ -z "$PERSPECTIVE_SOURCE" || ! -f "$PERSPECTIVE_SOURCE" ]]; then
  echo "FAIL: manifest-backed qualification perspective is unavailable" >&2
  exit 1
fi
if [[ "$#" -lt 1 ]]; then
  echo "FAIL: qualification Webots wrapper requires an exact world path" >&2
  exit 1
fi

WORLD="${!#}"
WORLD_NAME="$(basename "$WORLD")"
case "$WORLD_NAME" in
  .webeeblocks-physical-*.wbt) ;;
  *)
    echo "FAIL: qualification Webots wrapper refused non-ephemeral world: $WORLD_NAME" >&2
    exit 1
    ;;
esac

WORLD_DIR="$(cd "$(dirname "$WORLD")" && pwd)"
WORLD_BASE="${WORLD_NAME%.wbt}"
PERSPECTIVE="$WORLD_DIR/.${WORLD_BASE}.wbproj"

if [[ -e "$PERSPECTIVE" ]]; then
  echo "FAIL: qualification perspective path already exists: $PERSPECTIVE" >&2
  exit 1
fi
cp -- "$PERSPECTIVE_SOURCE" "$PERSPECTIVE"
if ! cmp -s -- "$PERSPECTIVE_SOURCE" "$PERSPECTIVE"; then
  rm -f -- "$PERSPECTIVE"
  echo "FAIL: qualification perspective copy changed" >&2
  exit 1
fi
if ! grep -Fxq 'Webots Project File version R2025a' "$PERSPECTIVE" || \
   [[ "$(grep -Fxc 'robotWindow: Crazyflie WebeeBlocks' "$PERSPECTIVE")" -ne 1 ]]; then
  rm -f -- "$PERSPECTIVE"
  echo "FAIL: qualification perspective lost exact R2025a Robot Window binding" >&2
  exit 1
fi

CHILD_PID=""
cleanup() {
  rm -f -- "$PERSPECTIVE"
}
forward_signal() {
  local signal="$1"
  if [[ -n "$CHILD_PID" ]]; then
    kill "-$signal" "$CHILD_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'forward_signal TERM' TERM
trap 'forward_signal INT' INT
trap 'forward_signal HUP' HUP

"$REAL_WEBOTS" "$@" &
CHILD_PID="$!"
set +e
wait "$CHILD_PID"
STATUS="$?"
set -e
CHILD_PID=""
exit "$STATUS"
