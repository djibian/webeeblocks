#!/usr/bin/env bash
set -euo pipefail

root="$(pwd)"
evidence="$root/ci-artifacts/crazyflie-runtime-wwi/firefox-qt-provider-continuity"
mkdir -p "$evidence"
exec > >(tee "$evidence/preparation.log") 2>&1
trap 'code=$?; if [ "$code" -ne 0 ] && [ ! -f "$evidence/result.json" ]; then printf "{\"result\":\"UNPROVEN\",\"reason\":\"preparation or continuity harness incomplete\",\"exit_code\":%s}\n" "$code" > "$evidence/result.json"; fi' EXIT

python3 -m py_compile tools/ci/firefox_qt_provider/qualify.py tools/ci/firefox_qt_provider/continuity.py
python3 tools/ci/firefox_qt_provider/test_qualification.py
python3 tools/ci/firefox_qt_provider/test_continuity.py

recipe="$RUNNER_TEMP/q87-linux-runtime-dependencies.sh"
curl --fail --location --retry 3 --output "$recipe" \
  https://raw.githubusercontent.com/cyberbotics/webots/R2025a/scripts/install/linux_runtime_dependencies.sh
test "$(git hash-object "$recipe")" = 4593476be2c985580a0e1738671f4b5bae81f669
sudo env CI=true bash "$recipe"
archive="$RUNNER_TEMP/webots-R2025a-x86-64.tar.bz2"
curl --fail --location --retry 3 --output "$archive" \
  https://github.com/cyberbotics/webots/releases/download/R2025a/webots-R2025a-x86-64.tar.bz2
echo "c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38  $archive" | sha256sum --check
tar -xjf "$archive" -C "$RUNNER_TEMP"
webots="$RUNNER_TEMP/webots"
project="$RUNNER_TEMP/q87-provider-project"
controller="$project/controllers/qt_provider_probe"
mkdir -p "$controller" "$project/worlds" "$project/files"
printf 'Q87 project-file sentinel: no Open or Save operation\n' > "$project/files/untouched.wbb"

frozen=fa78eb7dc8fd423abfd7e656a3bbf8c3e7e26c1c
for file in file_broker.cpp file_broker.hpp file_broker_c.h runtime.ini; do
  curl --fail --location --retry 3 --output "$controller/$file" \
    "https://raw.githubusercontent.com/djibian/webeeblocks/$frozen/controllers/crazyflie_runtime_v2/$file"
done
test "$(git hash-object "$controller/file_broker.cpp")" = 241e6e6aaec32ceaeaa2693fad337a774757b895
test "$(git hash-object "$controller/file_broker.hpp")" = 9e50d286344f680cb0cc254f4d68f4434a9e409a
test "$(git hash-object "$controller/file_broker_c.h")" = d51074ba660b131f3c9df67d0ceef404c204f079
test "$(git hash-object "$controller/runtime.ini")" = 27cbdb180b6f1aa4ed6a871bd9cb3ed147b29b6a
git hash-object "$controller"/file_broker.* "$controller/runtime.ini" > "$evidence/frozen-blobs.txt"
cp tools/ci/firefox_qt_provider/probe.cpp tools/ci/firefox_qt_provider/dialog_qualification.hpp "$controller/"
python3 tools/ci/firefox_qt_provider/qualify.py prepare "$project" "$evidence"

flags=(-std=c++17 -fPIC -g -O0 -I"$controller" -I"$webots/include/controller/c"
  -isystem "$webots/include/qt" -isystem "$webots/include/qt/QtCore"
  -isystem "$webots/include/qt/QtGui" -isystem "$webots/include/qt/QtWidgets")
g++ "${flags[@]}" -c "$controller/probe.cpp" -o "$controller/probe.o"
g++ "${flags[@]}" -c "$controller/file_broker.cpp" -o "$controller/file_broker.o"
g++ -fPIC -pie "$controller/probe.o" "$controller/file_broker.o" \
  -L"$webots/lib/webots" -L"$webots/lib/controller" \
  -Wl,-rpath-link,"$webots/lib/webots" -Wl,-rpath-link,"$webots/lib/controller" \
  -Wl,-Map,"$evidence/link.map" -lQt6Widgets -lQt6Gui -lQt6Core -lController \
  -o "$controller/qt_provider_probe"
readelf -rW --demangle "$controller/qt_provider_probe" > "$evidence/relocations.txt"
readelf -d "$controller/qt_provider_probe" > "$evidence/dynamic.txt"
nm -C "$controller/qt_provider_probe" > "$evidence/symbols.txt"
LD_LIBRARY_PATH="$webots/lib/webots:$webots/lib/controller" ldd "$controller/qt_provider_probe" > "$evidence/ldd.txt"
sha256sum "$controller/qt_provider_probe" "$controller/file_broker.cpp" "$controller/probe.cpp" \
  "$controller/dialog_qualification.hpp" "$controller/runtime.ini" "$webots/lib/controller/libController.so" \
  "$webots/lib/webots/libQt6Core.so.6" "$webots/lib/webots/libQt6Gui.so.6" \
  "$webots/lib/webots/libQt6Widgets.so.6" > "$evidence/build.sha256"
g++ --version > "$evidence/compiler.txt"
python3 tools/ci/firefox_qt_provider/qualify.py inspect "$project" "$evidence" "$webots"

# One bounded measurement re-evaluation of the already observed real provider.
# The controller cannot request Webots shutdown until the external harness has
# durably read the complete controller-owned continuity journal.
env WEBOTS_HOME="$webots" QT_PLUGIN_PATH="$webots/lib/webots/qt/plugins" \
  LIBGL_ALWAYS_SOFTWARE=true Q87_EVIDENCE="$evidence" Q87_FILES="$project/files" \
  timeout -k 5s 60s xvfb-run -a \
  python3 tools/ci/firefox_qt_provider/continuity.py "$project" "$evidence" "$webots"
