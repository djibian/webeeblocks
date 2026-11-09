#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 || $2 != apply && $2 != build ]]; then
  echo "Usage: bash $0 CLEAN_WEBOTS_SOURCE apply|build" >&2
  exit 2
fi

git_exe=${WEBOTS_GIT:-git}
root=$("$git_exe" -C "$(dirname "$0")" rev-parse --show-toplevel)
source=$(cd "$1" && pwd)
revision=c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b
actual=$("$git_exe" -C "$source" rev-parse HEAD)
if [[ $actual != "$revision" ]]; then
  echo "Expected Webots $revision, got $actual." >&2
  exit 1
fi
dirty=$("$git_exe" -C "$source" status --porcelain --untracked-files=no)
if [[ -n $dirty ]]; then
  printf 'Start with a clean Webots checkout. Modified tracked paths:\n%s\n' "$dirty" >&2
  exit 1
fi

"$git_exe" -C "$source" submodule update --init --recursive
while read -r commit path; do
  "$git_exe" -C "$root" show "$commit:$path" | "$git_exe" -C "$source" apply --check -
  "$git_exe" -C "$root" show "$commit:$path" | "$git_exe" -C "$source" apply -
done < "$root/tools/grand_prix/native_engine/patches.lock"
"$git_exe" -C "$source" diff --check

if [[ $2 == build ]]; then
  cd "$source"
  build_flags=()
  if [[ ${MSYSTEM:-} == MINGW64 ]]; then
    export WEBOTS_HOME=$(cygpath -m "$PWD")
    /usr/bin/bash scripts/install/msys64_installer.sh ''
    test -f include/qt/QtCore/QtCore/qglobal.h
    moc=$(pacman -Ql mingw-w64-x86_64-qt6-base | awk '$2 ~ /\/moc\.exe$/ { print $2 }')
    test -x "$moc"
    build_flags+=(MOC="$moc")
  else
    export WEBOTS_HOME=$PWD
  fi
  make -j"${WEBOTS_BUILD_JOBS:-4}" webots_target WEBOTS_HOME="$WEBOTS_HOME" "${build_flags[@]}"
  make -j"${WEBOTS_BUILD_JOBS:-4}" -C src/controller/c release WEBOTS_HOME="$WEBOTS_HOME"
fi
