#!/usr/bin/env bash
set -euo pipefail

# Re-run the exact settled C25 harness first so its pinned Webots closure and
# build objects are recreated unchanged before the C26 discriminator.
bash tools/ci/run_firefox_c25_qcore_self_copy.sh

echo C26_BASELINE_C25_REPRODUCED=1

artifact_dir=ci-artifacts/crazyflie-runtime-wwi/firefox-c26-copy-vs-got
mkdir -p "$artifact_dir"

webots="$RUNNER_TEMP/webots"
control_obj="$RUNNER_TEMP/c24-control.o"
broker_obj="$RUNNER_TEMP/c24-broker.o"
self_obj="$RUNNER_TEMP/c25-direct-self.o"
arm_a="$RUNNER_TEMP/c26-arm-a-gc-no-relax"
arm_i="$RUNNER_TEMP/c26-arm-i-direct-self-no-relax"
arm_f="$RUNNER_TEMP/c26-arm-f-qcore-instance-no-relax"
arm_k="$RUNNER_TEMP/c26-arm-k-got-self-no-relax"
staged="$RUNNER_TEMP/c26-control"
got_source="$RUNNER_TEMP/c26-got-self.S"
got_obj="$RUNNER_TEMP/c26-got-self.o"

for path in "$control_obj" "$broker_obj" "$self_obj"; do
  test -f "$path"
done

cat > "$got_source" <<'ASM'
.section .text.webeeblocks_c26_got_self,"ax",@progbits
.globl webeeblocks_c26_got_self
.type webeeblocks_c26_got_self,@function
webeeblocks_c26_got_self:
  movq _ZN16QCoreApplication4selfE@GOTPCREL(%rip), %rax
  movq (%rax), %rax
  ret
.size webeeblocks_c26_got_self, .-webeeblocks_c26_got_self
.section .note.GNU-stack,"",@progbits
ASM

git hash-object "$got_source" | tee "$artifact_dir/got-source-blob.txt"
gcc -fPIC -c "$got_source" -o "$got_obj"
nm -u "$got_obj" | tee "$artifact_dir/got-object-undefined.txt"
objdump -dr "$got_obj" | tee "$artifact_dir/got-object-objdump.txt"
test "$(awk '{print $2}' "$artifact_dir/got-object-undefined.txt" | sed '/^$/d')" = _ZN16QCoreApplication4selfE
grep -Fq '<webeeblocks_c26_got_self>:' "$artifact_dir/got-object-objdump.txt"
grep -Fq '_ZN16QCoreApplication4selfE' "$artifact_dir/got-object-objdump.txt"
grep -Eq 'R_X86_64_(REX_)?GOTPCRELX?.*_ZN16QCoreApplication4selfE|R_X86_64_GOTPCREL.*_ZN16QCoreApplication4selfE' \
  "$artifact_dir/got-object-objdump.txt"

common=(-std=c++17 -g -O0
  -isystem "$webots/include/qt/QtCore"
  -isystem "$webots/include/qt/QtGui"
  -isystem "$webots/include/qt/QtWidgets"
  -L"$webots/lib/webots" -L"$webots/lib/controller"
  -Wl,-rpath-link,"$webots/lib/webots" -Wl,-rpath-link,"$webots/lib/controller")
libs=(-lQt6Widgets -lQt6Gui -lQt6Core -Wl,--no-as-needed -lController -Wl,--as-needed)
link_common=(-Wl,--gc-sections -Wl,--no-relax)

# Rebuild every C26 comparison arm from the exact same C25 objects under one
# no-relax closure. Only the intended root/object differs between arms.
g++ "${common[@]}" "$control_obj" "$broker_obj" \
  "${link_common[@]}" -Wl,-Map,"$artifact_dir/arm-a-link.map" \
  -o "$arm_a" "${libs[@]}"
g++ "${common[@]}" "$control_obj" "$broker_obj" "$got_obj" \
  "${link_common[@]}" -Wl,--undefined=webeeblocks_c26_got_self \
  -Wl,-Map,"$artifact_dir/arm-k-got-self-link.map" \
  -o "$arm_k" "${libs[@]}"
g++ "${common[@]}" "$control_obj" "$broker_obj" "$self_obj" \
  "${link_common[@]}" -Wl,--undefined=webeeblocks_c25_direct_self \
  -Wl,-Map,"$artifact_dir/arm-i-direct-self-link.map" \
  -o "$arm_i" "${libs[@]}"
g++ "${common[@]}" "$control_obj" "$broker_obj" \
  "${link_common[@]}" -Wl,--undefined=_ZN16QCoreApplication8instanceEv \
  -Wl,-Map,"$artifact_dir/arm-f-qcore-instance-link.map" \
  -o "$arm_f" "${libs[@]}"

sha256sum "$got_obj" "$arm_a" "$arm_k" "$arm_i" "$arm_f" | tee "$artifact_dir/sha256.txt"
! cmp -s "$arm_a" "$arm_k"
! cmp -s "$arm_a" "$arm_i"
! cmp -s "$arm_k" "$arm_i"
! cmp -s "$arm_i" "$arm_f"

for arm in a k i f; do
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

for arm in k i f; do
  diff -u "$artifact_dir/arm-a-needed.txt" "$artifact_dir/arm-$arm-needed.txt" \
    > "$artifact_dir/arm-a-vs-$arm-needed.diff" || {
      cat "$artifact_dir/arm-a-vs-$arm-needed.diff"
      exit 1
    }
done

has_qcore_root() { grep -Fq 'QCoreApplication::instance()' "$artifact_dir/arm-$1-nm.txt"; }
has_meta_root() { grep -Fq 'qobject_cast<QApplication*>' "$artifact_dir/arm-$1-nm.txt"; }
has_qcore_copy() { grep -Eq 'R_X86_64_COPY.*QCoreApplication::self' "$artifact_dir/arm-$1-relocations-demangled.txt"; }
no_provider_roots() {
  arm="$1"
  ! grep -Fq 'wb_file_broker_create_qt' "$artifact_dir/arm-$arm-nm.txt" &&
    ! grep -Fq 'webeeblocks::createQtFileDialogProvider()' "$artifact_dir/arm-$arm-nm.txt"
}

# Settled C25 controls must retain their exact structural distinction after the
# common no-relax relink before any C26 runtime classification is accepted.
no_provider_roots a
! has_qcore_root a
! has_meta_root a
! has_qcore_copy a
! grep -Fq 'webeeblocks_c25_direct_self' "$artifact_dir/arm-a-nm.txt"
! grep -Fq 'webeeblocks_c26_got_self' "$artifact_dir/arm-a-nm.txt"

no_provider_roots i
! has_qcore_root i
! has_meta_root i
has_qcore_copy i
grep -Fq 'webeeblocks_c25_direct_self' "$artifact_dir/arm-i-nm.txt"
! grep -Fq 'webeeblocks_c26_got_self' "$artifact_dir/arm-i-nm.txt"
test "$(grep -Ec 'R_X86_64_COPY.*QCoreApplication::self' "$artifact_dir/arm-i-relocations-demangled.txt")" -eq 1

no_provider_roots f
has_qcore_root f
! has_meta_root f
has_qcore_copy f
! grep -Fq 'webeeblocks_c25_direct_self' "$artifact_dir/arm-f-nm.txt"
! grep -Fq 'webeeblocks_c26_got_self' "$artifact_dir/arm-f-nm.txt"

# K references the same Qt data symbol through the GOT and must not interpose it
# via COPY or retain the C25 function/provider/metaobject roots.
no_provider_roots k
! has_qcore_root k
! has_meta_root k
! has_qcore_copy k
! grep -Fq 'webeeblocks_c25_direct_self' "$artifact_dir/arm-k-nm.txt"
grep -Fq 'webeeblocks_c26_got_self' "$artifact_dir/arm-k-nm.txt"
grep -Fq 'QCoreApplication::self' "$artifact_dir/arm-k-relocations-demangled.txt"
grep -Eq 'R_X86_64_(GLOB_DAT|JUMP_SLOT|64).*QCoreApplication::self' \
  "$artifact_dir/arm-k-relocations-demangled.txt"

echo C26_COPY_VS_GOT_CHARACTERIZED=1 | tee "$artifact_dir/root-proof.txt"

session="$RUNNER_TEMP/c26-session.sh"
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
  printf 'WEBEEBLOCKS_C26_PROCESS tag=%s pid=%s argc=1 argv0=%s debug=0 display=%s\n' \
    "$tag" "$pid" "$staged" "${DISPLAY:-}" >> "$log"
  printf 'WEBEEBLOCKS_C26_PROCESS_EXIT tag=%s pid=%s code=%s\n' \
    "$tag" "$pid" "$code" >> "$log"
}
run_one arm-a "$arm_a"
run_one arm-k "$arm_k"
run_one arm-i "$arm_i"
run_one arm-f "$arm_f"
SH
chmod +x "$session"

set +e
env artifact_dir="$artifact_dir" staged="$staged" \
  arm_a="$arm_a" arm_k="$arm_k" arm_i="$arm_i" arm_f="$arm_f" \
  QT_PLUGIN_PATH="$webots/lib/webots/qt/plugins" \
  LD_LIBRARY_PATH="$webots/lib/webots:$webots/lib/controller" \
  LIBGL_ALWAYS_SOFTWARE=true timeout -k 2s 60s xvfb-run -a "$session"
outer=$?
set -e
test "$outer" = 0

check_common() {
  log="$1"; tag="$2"
  cat "$log"
  pid="$(sed -n "s/.*WEBEEBLOCKS_C26_PROCESS tag=$tag pid=\([0-9][0-9]*\).*/\1/p" "$log" | tail -1)"
  exit_pid="$(sed -n "s/.*WEBEEBLOCKS_C26_PROCESS_EXIT tag=$tag pid=\([0-9][0-9]*\) code=.*/\1/p" "$log" | tail -1)"
  test -n "$pid" && test "$pid" = "$exit_pid" &&
    grep -Eq "WEBEEBLOCKS_C26_PROCESS tag=$tag .* argc=1 .* debug=0 display=:[0-9]+" "$log" &&
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
    grep -Eq "WEBEEBLOCKS_C26_PROCESS_EXIT tag=$tag pid=[0-9]+ code=0" "$log" &&
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
    grep -Eq "WEBEEBLOCKS_C26_PROCESS_EXIT tag=$tag pid=[0-9]+ code=139" "$log" &&
    check_no_broker_runtime "$log" &&
    sed -n '/BACKTRACE_BEGIN/,/BACKTRACE_END/p' "$log" |
      grep -Eq 'libQt6(Core|Gui|Widgets)|libQt6XcbQpa|libqxcb|QApplication|QGuiApplication'
}

a_log="$artifact_dir/arm-a.log"
k_log="$artifact_dir/arm-k.log"
i_log="$artifact_dir/arm-i.log"
f_log="$artifact_dir/arm-f.log"

if ! check_success "$a_log" arm-a || ! check_crash "$i_log" arm-i || ! check_crash "$f_log" arm-f; then
  echo DIAGNOSTIC_RESULT=C26_SETTLED_CONTROLS_UNPROVEN | tee "$artifact_dir/result.txt"
  exit 1
fi

if check_success "$k_log" arm-k >&2; then
  echo 'C26_OUTCOME got=success copy=crash instance=crash' | tee "$artifact_dir/outcomes.txt"
  echo DIAGNOSTIC_RESULT=C26_COPY_RELOCATION_REQUIRED_RELATIVE_TO_GOT | tee "$artifact_dir/result.txt"
  exit 0
fi
if check_crash "$k_log" arm-k >&2; then
  echo 'C26_OUTCOME got=crash copy=crash instance=crash' | tee "$artifact_dir/outcomes.txt"
  echo DIAGNOSTIC_RESULT=C26_SELF_BINDING_SURVIVES_WITHOUT_COPY | tee "$artifact_dir/result.txt"
  exit 0
fi

echo 'C26_OUTCOME got=unproven copy=crash instance=crash' | tee "$artifact_dir/outcomes.txt"
echo DIAGNOSTIC_RESULT=C26_GOT_OUTCOME_UNPROVEN | tee "$artifact_dir/result.txt"
exit 1
