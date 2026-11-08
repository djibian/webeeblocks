#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 || ! $2 =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: bash $0 CLEAN_WEBOTS_SOURCE JOBS" >&2
  exit 2
fi

here=$(cd "$(dirname "$0")" && pwd)
source=$(cd "$1" && pwd)
patch="$here/webots-r2025a.patch"
revision=c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b
if [[ $(git -C "$source" rev-parse HEAD) != "$revision" ]] ||
   ! git -C "$source" diff --quiet HEAD -- ||
   ! git -C "$source" diff --cached --quiet HEAD --; then
  echo "A clean Webots R2025a checkout at $revision is required." >&2
  exit 1
fi

git -C "$source" submodule update --init --recursive
git -C "$source" apply --check "$patch"
git -C "$source" apply "$patch"

cd "$source"
if [[ $(uname -s) == MINGW* ]]; then
  export WEBOTS_HOME=$(pwd -W)
else
  export WEBOTS_HOME=$PWD
fi
make -j"$2" webots_target
make -j"$2" -C src/controller/c release
