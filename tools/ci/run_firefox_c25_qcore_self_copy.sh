#!/usr/bin/env bash
set -euo pipefail

artifact_dir=ci-artifacts/crazyflie-runtime-wwi/firefox-c25-qcore-self-copy
mkdir -p "$artifact_dir"

recipe="$RUNNER_TEMP/linux_runtime_dependencies-R2025a.sh"
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

frozen_sha=fa78eb7dc8fd423abfd7e656a3bbf8c3e7e26c1c
frozen="$RUNNER_TEMP/c24-frozen-broker"
mkdir -p "$frozen"
for file in file_broker.cpp file_broker.hpp file_broker_c.h; do
  curl --fail --location --retry 3 --output "$frozen/$file" \
    "https://raw.githubusercontent.com/djibian/webeeblocks/$frozen_sha/controllers/crazyflie_runtime_v2/$file"
done
test "$(git hash-object "$frozen/file_broker.cpp")" = 241e6e6aaec32ceaeaa2693fad337a774757b895
test "$(git hash-object "$frozen/file_broker.hpp")" = 9e50d286344f680cb0cc254f4d68f4434a9e409a
test "$(git hash-object "$frozen/file_broker_c.h")" = d51074ba660b131f3c9df67d0ceef404c204f079
git hash-object "$frozen"/file_broker.* | tee "$artifact_dir/frozen-source-blobs.txt"

source="$RUNNER_TEMP/c24-control.cpp"
self_source="$RUNNER_TEMP/c25-direct-self.S"
control_obj="$RUNNER_TEMP/c24-control.o"
broker_obj="$RUNNER_TEMP/c24-broker.o"
self_obj="$RUNNER_TEMP/c25-direct-self.o"
arm_a="$RUNNER_TEMP/c25-arm-a-gc"
arm_i="$RUNNER_TEMP/c25-arm-i-direct-self"
arm_f="$RUNNER_TEMP/c25-arm-f-qcore-instance"
arm_b="$RUNNER_TEMP/c25-arm-b-internal-factory"
staged="$RUNNER_TEMP/c24-control"

cat > "$source" <<'CPP'
#include <QtWidgets/QApplication>
#include <csignal>
#include <cstring>
#include <execinfo.h>
#include <unistd.h>
static void marker(const char *m) { ::write(STDERR_FILENO, m, std::strlen(m)); }
static void fatal_handler(int s) {
  if (s == SIGSEGV) marker("WEBEEBLOCKS_QT_CONTROL_FATAL signal=SIGSEGV\n");
  else if (s == SIGABRT) marker("WEBEEBLOCKS_QT_CONTROL_FATAL signal=SIGABRT\n");
  else if (s == SIGBUS) marker("WEBEEBLOCKS_QT_CONTROL_FATAL signal=SIGBUS\n");
  else if (s == SIGILL) marker("WEBEEBLOCKS_QT_CONTROL_FATAL signal=SIGILL\n");
  else if (s == SIGFPE) marker("WEBEEBLOCKS_QT_CONTROL_FATAL signal=SIGFPE\n");
  else marker("WEBEEBLOCKS_QT_CONTROL_FATAL signal=UNKNOWN\n");
  void *frames[64];
  int count = ::backtrace(frames, 64);
  marker("WEBEEBLOCKS_QT_CONTROL_BACKTRACE_BEGIN\n");
  ::backtrace_symbols_fd(frames, count, STDERR_FILENO);
  marker("WEBEEBLOCKS_QT_CONTROL_BACKTRACE_END\n");
  _exit(128 + s);
}
int main(int argc, char **argv) {
  void *warmup[1]; (void)::backtrace(warmup, 1);
  struct sigaction action {};
  action.sa_handler = fatal_handler; sigemptyset(&action.sa_mask);
  action.sa_flags = SA_RESETHAND;
  for (int s : {SIGSEGV, SIGABRT, SIGBUS, SIGILL, SIGFPE})
    if (sigaction(s, &action, nullptr) != 0) return 120;
  marker("WEBEEBLOCKS_QT_CONTROL BEFORE_QAPPLICATION\n");
  QApplication app(argc, argv);
  marker("WEBEEBLOCKS_QT_CONTROL QAPPLICATION_OK\n");
  return 0;
}
CPP

cat > "$self_source" <<'ASM'
.section .text.webeeblocks_c25_direct_self,"ax",@progbits
.globl webeeblocks_c25_direct_self
.type webeeblocks_c25_direct_self,@function
webeeblocks_c25_direct_self:
  movq _ZN16QCoreApplication4selfE(%rip), %rax
  ret
.size webeeblocks_c25_direct_self, .-webeeblocks_c25_direct_self
.section .note.GNU-stack,"",@progbits
ASM

git hash-object "$source" "$self_source" | tee "$artifact_dir/local-source-blobs.txt"

common=(-std=c++17 -g -O0
  -isystem "$webots/include/qt/QtCore"
  -isystem "$webots/include/qt/QtGui"
  -isystem "$webots/include/qt/QtWidgets"
  -L"$webots/lib/webots" -L"$webots/lib/controller"
  -Wl,-rpath-link,"$webots/lib/webots" -Wl,-rpath-link,"$webots/lib/controller")
libs=(-lQt6Widgets -lQt6Gui -lQt6Core -Wl,--no-as-needed -lController -Wl,--as-needed)

g++ "${common[@]}" -ffunction-sections -fdata-sections -c "$source" -o "$control_obj"
g++ "${common[@]}" -ffunction-sections -fdata-sections -I"$frozen" \
  -c "$frozen/file_broker.cpp" -o "$broker_obj"
gcc -c "$self_source" -o "$self_obj"

nm -u "$self_obj" | tee "$artifact_dir/direct-self-undefined.txt"
objdump -dr "$self_obj" | tee "$artifact_dir/direct-self-objdump.txt"
test "$(awk '{print $2}' "$artifact_dir/direct-self-undefined.txt" | sed '/^$/d')" = _ZN16QCoreApplication4selfE
grep -Fq '<webeeblocks_c25_direct_self>:' "$artifact_dir/direct-self-objdump.txt"
grep -Fq '_ZN16QCoreApplication4selfE' "$artifact_dir/direct-self-objdump.txt"

g++ "${common[@]}" "$control_obj" "$broker_obj" \
  -Wl,--gc-sections -Wl,-Map,"$artifact_dir/arm-a-link.map" \
  -o "$arm_a" "${libs[@]}"
g++ "${common[@]}" "$control_obj" "$broker_obj" "$self_obj" \
  -Wl,--gc-sections -Wl,--undefined=webeeblocks_c25_direct_self \
  -Wl,-Map,"$artifact_dir/arm-i-direct-self-link.map" \
  -o "$arm_i" "${libs[@]}"
g++ "${common[@]}" "$control_obj" "$broker_obj" \
  -Wl,--gc-sections -Wl,--undefined=_ZN16QCoreApplication8instanceEv \
  -Wl,-Map,"$artifact_dir/arm-f-qcore-instance-link.map" \
  -o "$arm_f" "${libs[@]}"
g++ "${common[@]}" "$control_obj" "$broker_obj" \
  -Wl,--gc-sections -Wl,--undefined=_ZN11webeeblocks26createQtFileDialogProviderEv \
  -Wl,-Map,"$artifact_dir/arm-b-internal-factory-link.map" \
  -o "$arm_b" "${libs[@]}"

sha256sum "$control_obj" "$broker_obj" "$self_obj" "$arm_a" "$arm_i" "$arm_f" "$arm_b" \
  | tee "$artifact_dir/sha256.txt"
! cmp -s "$arm_a" "$arm_i"
! cmp -s "$arm_a" "$arm_f"
! cmp -s "$arm_i" "$arm_f"
! cmp -s "$arm_f" "$arm_b"

for arm in a i f b; do
  binary_var="arm_$arm"
  binary="${!binary_var}"
  nm -C "$binary" > "$artifact_dir/arm-$arm-nm.txt"
  readelf -rW --demangle "$binary" > "$artifact_dir/arm-$arm-relocations-demangled.txt"
  readelf -d "$binary" > "$artifact_dir/arm-$arm-readelf.txt"
  sed -n 's/.*Shared library: \[\(.*\)\].*/\1/p' \
    "$artifact_dir/arm-$arm-readelf.txt" > "$artifact_dir/arm-$arm-needed.txt"
  LD_LIBRARY_PATH="$webots/lib/webots:$webots/lib/controller" \
    ldd "$binary" > "$artifact_dir/arm-$arm-ldd.txt"
  grep -F "libController.so => $webots/lib/controller/libController.so" \
    "$artifact_dir/arm-$arm-ldd.txt"
  qt="$(grep 'libQt6\(Core\|Gui\|Widgets\)' "$artifact_dir/arm-$arm-ldd.txt")"
  test "$(printf '%s\n' "$qt" | wc -l)" -eq 3
  ! printf '%s\n' "$qt" | grep -vF "$webots/lib/webots/"
done

has_qcore_root() {
  grep -Fq 'QCoreApplication::instance()' "$artifact_dir/arm-$1-nm.txt"
}
has_meta_root() {
  grep -Fq 'qobject_cast<QApplication*>' "$artifact_dir/arm-$1-nm.txt"
}
has_qcore_copy() {
  grep -Eq 'R_X86_64_COPY.*QCoreApplication::self' "$artifact_dir/arm-$1-relocations-demangled.txt"
}
has_meta_copy() {
  grep -Eq 'R_X86_64_COPY.*QApplication::staticMetaObject' "$artifact_dir/arm-$1-relocations-demangled.txt"
}
no_provider_roots() {
  arm="$1"
  ! grep -Fq 'wb_file_broker_create_qt' "$artifact_dir/arm-$arm-nm.txt" &&
    ! grep -Fq 'webeeblocks::createQtFileDialogProvider()' "$artifact_dir/arm-$arm-nm.txt"
}

# A: settled ordinary-GC success control.
no_provider_roots a
! has_qcore_root a
! has_meta_root a
! has_qcore_copy a
! has_meta_copy a
! grep -Fq 'webeeblocks_c25_direct_self' "$artifact_dir/arm-a-nm.txt"

# I: direct data-binding arm. No retained Qt helper/provider code is allowed.
no_provider_roots i
! has_qcore_root i
! has_meta_root i
has_qcore_copy i
! has_meta_copy i
grep -Fq 'webeeblocks_c25_direct_self' "$artifact_dir/arm-i-nm.txt"
test "$(grep -Ec 'R_X86_64_COPY.*QCoreApplication::self' "$artifact_dir/arm-i-relocations-demangled.txt")" -eq 1

# F: settled C24 QCoreApplication::instance/self-COPY positive arm.
no_provider_roots f
has_qcore_root f
! has_meta_root f
has_qcore_copy f
! has_meta_copy f
! grep -Fq 'webeeblocks_c25_direct_self' "$artifact_dir/arm-f-nm.txt"

# B: settled C23 internal-factory positive crash control; outer C wrapper absent.
! grep -Fq 'wb_file_broker_create_qt' "$artifact_dir/arm-b-nm.txt"
! grep -Fq 'wb_file_broker_handle_message' "$artifact_dir/arm-b-nm.txt"
grep -Fq 'webeeblocks::createQtFileDialogProvider()' "$artifact_dir/arm-b-nm.txt"
has_qcore_root b
has_meta_root b
has_qcore_copy b
has_meta_copy b

# Direct-self must not alter the linked shared-library closure.
diff -u "$artifact_dir/arm-a-needed.txt" "$artifact_dir/arm-i-needed.txt" \
  | tee "$artifact_dir/arm-a-vs-i-needed.diff"
diff -u "$artifact_dir/arm-a-needed.txt" "$artifact_dir/arm-f-needed.txt" \
  | tee "$artifact_dir/arm-a-vs-f-needed.diff"
echo C25_DIRECT_SELF_CHARACTERIZED=1 | tee "$artifact_dir/root-proof.txt"

session="$RUNNER_TEMP/c25-session.sh"
cat > "$session" <<'SH'
#!/usr/bin/env bash
set +e
run_one() {
  tag="$1"; binary="$2"; log="$artifact_dir/$tag.log"
  cp "$binary" "$staged"
  env -u QT_DEBUG_PLUGINS "$staged" > "$log" 2>&1 &
  pid=$!
  wait "$pid"
  code=$?
  printf 'WEBEEBLOCKS_C25_PROCESS tag=%s pid=%s argc=1 argv0=%s debug=0 display=%s\n' \
    "$tag" "$pid" "$staged" "${DISPLAY:-}" >> "$log"
  printf 'WEBEEBLOCKS_C25_PROCESS_EXIT tag=%s pid=%s code=%s\n' \
    "$tag" "$pid" "$code" >> "$log"
}
run_one arm-a "$arm_a"
run_one arm-i "$arm_i"
run_one arm-f "$arm_f"
run_one arm-b "$arm_b"
SH
chmod +x "$session"

set +e
env artifact_dir="$artifact_dir" staged="$staged" \
  arm_a="$arm_a" arm_i="$arm_i" arm_f="$arm_f" arm_b="$arm_b" \
  QT_PLUGIN_PATH="$webots/lib/webots/qt/plugins" \
  LD_LIBRARY_PATH="$webots/lib/webots:$webots/lib/controller" \
  LIBGL_ALWAYS_SOFTWARE=true timeout -k 2s 60s xvfb-run -a "$session"
outer=$?
set -e
test "$outer" = 0

check_common() {
  log="$1"; tag="$2"
  cat "$log"
  pid="$(sed -n "s/.*WEBEEBLOCKS_C25_PROCESS tag=$tag pid=\([0-9][0-9]*\).*/\1/p" "$log" | tail -1)"
  exit_pid="$(sed -n "s/.*WEBEEBLOCKS_C25_PROCESS_EXIT tag=$tag pid=\([0-9][0-9]*\) code=.*/\1/p" "$log" | tail -1)"
  test -n "$pid" && test "$pid" = "$exit_pid" &&
    grep -Eq "WEBEEBLOCKS_C25_PROCESS tag=$tag .* argc=1 .* debug=0 display=:[0-9]+" "$log" &&
    grep -Fq 'WEBEEBLOCKS_QT_CONTROL BEFORE_QAPPLICATION' "$log"
}

check_no_broker_runtime() {
  log="$1"
  ! grep -Fq 'WEBEEBLOCKS_FILE_BROKER_V1 QT_APP_INITIALIZED' "$log" &&
    ! grep -Fq 'WEBEEBLOCKS_FILE_BROKER_V1 QFILEDIALOG_CONSTRUCTED' "$log"
}

check_success() {
  log="$1"; tag="$2"
  check_common "$log" "$tag" &&
    grep -Fq 'WEBEEBLOCKS_QT_CONTROL QAPPLICATION_OK' "$log" &&
    grep -Eq "WEBEEBLOCKS_C25_PROCESS_EXIT tag=$tag pid=[0-9]+ code=0" "$log" &&
    ! grep -Fq 'WEBEEBLOCKS_QT_CONTROL_FATAL signal=' "$log" &&
    check_no_broker_runtime "$log"
}

check_crash() {
  log="$1"; tag="$2"
  check_common "$log" "$tag" &&
    ! grep -Fq 'WEBEEBLOCKS_QT_CONTROL QAPPLICATION_OK' "$log" &&
    grep -Fq 'WEBEEBLOCKS_QT_CONTROL_FATAL signal=SIGSEGV' "$log" &&
    grep -Fq 'WEBEEBLOCKS_QT_CONTROL_BACKTRACE_BEGIN' "$log" &&
    grep -Fq 'WEBEEBLOCKS_QT_CONTROL_BACKTRACE_END' "$log" &&
    grep -Eq "WEBEEBLOCKS_C25_PROCESS_EXIT tag=$tag pid=[0-9]+ code=139" "$log" &&
    check_no_broker_runtime "$log" &&
    sed -n '/BACKTRACE_BEGIN/,/BACKTRACE_END/p' "$log" |
      grep -Eq 'libQt6(Core|Gui|Widgets)|libQt6XcbQpa|libqxcb|QApplication|QGuiApplication'
}

a_log="$artifact_dir/arm-a.log"
i_log="$artifact_dir/arm-i.log"
f_log="$artifact_dir/arm-f.log"
b_log="$artifact_dir/arm-b.log"

if ! check_success "$a_log" arm-a || ! check_crash "$f_log" arm-f || ! check_crash "$b_log" arm-b; then
  echo DIAGNOSTIC_RESULT=C25_C24_C23_CONTROLS_UNPROVEN | tee "$artifact_dir/result.txt"
  exit 1
fi

if check_crash "$i_log" arm-i >&2; then
  echo 'C25_DIRECT_SELF_OUTCOME direct_self=crash instance=crash internal_factory=crash' \
    | tee "$artifact_dir/outcomes.txt"
  echo DIAGNOSTIC_RESULT=C25_QCORE_SELF_COPY_RELOCATION_SUFFICIENT | tee "$artifact_dir/result.txt"
  exit 0
fi
if check_success "$i_log" arm-i >&2; then
  echo 'C25_DIRECT_SELF_OUTCOME direct_self=success instance=crash internal_factory=crash' \
    | tee "$artifact_dir/outcomes.txt"
  echo DIAGNOSTIC_RESULT=C25_INSTANCE_CODE_OR_LAYOUT_REQUIRED | tee "$artifact_dir/result.txt"
  exit 0
fi

echo 'C25_DIRECT_SELF_OUTCOME direct_self=unproven instance=crash internal_factory=crash' \
  | tee "$artifact_dir/outcomes.txt"
echo DIAGNOSTIC_RESULT=C25_DIRECT_SELF_OUTCOME_UNPROVEN | tee "$artifact_dir/result.txt"
exit 1
