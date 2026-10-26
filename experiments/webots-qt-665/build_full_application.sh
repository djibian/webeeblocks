#!/usr/bin/env bash
# Run in the development overlay of the pinned official R2025a image.
# NON-GATE experiment: produces an application, never adopts it in product paths.
set -Eeuo pipefail
source_tree=$(realpath "${1:?pinned expendable upstream checkout}")
evidence=$(realpath "${2:?existing evidence directory}")
experiment=$(cd "$(dirname "$0")" && pwd)
runtime=/usr/local/webots
git config --global --add safe.directory "$source_tree"
test "$(git -C "$source_tree" rev-parse HEAD)" = c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b
python3 "$experiment/qualify_source_patch.py" --webots-tree "$source_tree" > "$evidence/source.json"
g++ --version > "$evidence/compiler.txt"
git -C "$source_tree" submodule status > "$evidence/submodules.txt"
sha256sum "$runtime"/lib/webots/libQt6*.so.6.5.3 "$runtime/bin/webots-bin" > "$evidence/original-runtime.sha256"

# Preserve the official runtime libraries; the full SDK supplies headers/moc only.
cp -a "$runtime/lib/webots/." "$source_tree/lib/webots/"
mkdir -p "$source_tree/bin/qt" "$source_tree/include/qt"
cp -a /opt/Qt/6.5.3/gcc_64/include/. "$source_tree/include/qt/"
cp /opt/Qt/6.5.3/gcc_64/libexec/moc "$source_tree/bin/qt/moc"
export LD_LIBRARY_PATH="$runtime/lib/webots:${LD_LIBRARY_PATH:-}"
export WEBOTS_HOME="$source_tree"
export QT_QPA_PLATFORM_PLUGIN_PATH="$runtime/lib/webots/qt/plugins/platforms"

# Pin the upstream dependency archives, extract only development headers.
cd "$source_tree"
for spec in 'libOIS.1.4.tar.bz2 d1482733dce06f6dcc1c062c5c314185' 'libpico.tar.bz2 13ce4d080f1db578cb2b73206b52e4cb' 'libassimp-5.2.3.tar.bz2 25f08ba04d580e8d81a387856d304f4c'; do
  read -r package digest <<< "$spec"
  curl --fail --location --max-time 180 "https://cyberbotics.com/files/repository/dependencies/linux64/release/$package" -o "$evidence/$package"
  echo "$digest  $evidence/$package" | md5sum --check
  sha256sum "$evidence/$package" >> "$evidence/dependency-archives.sha256"
  tar -xjf "$evidence/$package" --wildcards 'include/*'
done
git apply "$experiment/webots-r2025a-guarded-progress-retirement.patch"
git diff --binary > "$evidence/applied.patch"
sha256sum "$experiment/webots-r2025a-guarded-progress-retirement.patch" > "$evidence/patch.sha256"
find include/qt -type f -print0 | sort -z | xargs -0 sha256sum > "$evidence/qt-headers.sha256"

# Build the real renderer archives and every Webots TU/moc. Keep official ODE.
# Release semantics with debug symbols and no strip for causal GDB experiments.
make -j2 -C src/glad release
make -j2 -C src/wren release
make -j2 -C src/webots release CFLAGS='-fPIC -O2 -g -DNDEBUG -Wall' LD_FLAGS='-rdynamic'
test -x bin/webots-bin
sha256sum bin/webots-bin lib/webots/libQt6*.so.6.5.3 > "$evidence/candidate-runtime.sha256"
readelf -n bin/webots-bin > "$evidence/candidate-notes.txt"
ldd bin/webots-bin > "$evidence/candidate-ldd.txt"
if grep -q 'not found' "$evidence/candidate-ldd.txt"; then exit 1; fi
cp bin/webots-bin "$evidence/webots-bin"
echo QT665_FULL_LINK=PASS

# Exercise the official installation's launcher after replacing only its binary.
# This is diagnostic adoption in this disposable container, NOT product adoption.
cp "$runtime/bin/webots-bin" "$evidence/official-webots-bin"
cp bin/webots-bin "$runtime/bin/webots-bin"
sha256sum "$runtime/bin/webots-bin" > "$evidence/launcher-binary.sha256"
unset WEBOTS_HOME
timeout -k 5s 30s "$runtime/webots" --version > "$evidence/launcher-version.txt" 2>&1
echo QT665_LAUNCHER_VERSION=PASS
