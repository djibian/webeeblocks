#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 || $2 != apply && $2 != build ]]; then
  echo "Usage: bash $0 CLEAN_WEBOTS_SOURCE apply|build" >&2
  exit 2
fi

root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
source=$(cd "$1" && pwd)
revision=c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b
actual=$(git -C "$source" rev-parse HEAD)
if [[ $actual != "$revision" ]]; then
  echo "Expected Webots $revision, got $actual." >&2
  exit 1
fi
dirty=$(git -C "$source" status --porcelain --untracked-files=no)
if [[ -n $dirty ]]; then
  printf 'Start with a clean Webots checkout. Modified tracked paths:\n%s\n' "$dirty" >&2
  exit 1
fi

git -C "$source" submodule update --init --recursive
while read -r commit path; do
  git -C "$root" show "$commit:$path" | git -C "$source" apply --check -
  git -C "$root" show "$commit:$path" | git -C "$source" apply -
done < "$root/tools/grand_prix/native_engine/patches.lock"
git -C "$source" diff --check

if [[ $2 == build ]]; then
  cd "$source"
  if [[ $(uname -s) == MINGW* ]]; then
    export WEBOTS_HOME=$(pwd -W)
    bash scripts/install/msys64_installer.sh ''
  else
    export WEBOTS_HOME=$PWD
  fi
  make -j"${WEBOTS_BUILD_JOBS:-4}" webots_target
  make -j"${WEBOTS_BUILD_JOBS:-4}" -C src/controller/c release
fi
