#!/usr/bin/env bash
set -euo pipefail

artifact_dir=ci-artifacts/firefox-c14-standalone-qt-control
mkdir -p "$artifact_dir"

c10_sha=fa78eb7dc8fd423abfd7e656a3bbf8c3e7e26c1c
c10_file_broker_blob=241e6e6aaec32ceaeaa2693fad337a774757b895
c10_makefile_blob=ef44dd5caf4ed3c0e77875cec26da511071649f5
c10_runtime_ini_blob=27cbdb180b6f1aa4ed6a871bd9cb3ed147b29b6a
historical="$RUNNER_TEMP/webeeblocks-c10-c14"

git init -q "$historical"
git -C "$historical" remote add origin https://github.com/djibian/webeeblocks.git
git -C "$historical" fetch --depth=1 origin "$c10_sha"
git -C "$historical" checkout -q --detach FETCH_HEAD
test "$(git -C "$historical" rev-parse HEAD)" = "$c10_sha"
test "$(git -C "$historical" hash-object controllers/crazyflie_runtime_v2/file_broker.cpp)" = "$c10_file_broker_blob"
test "$(git -C "$historical" hash-object controllers/crazyflie_runtime_v2/Makefile)" = "$c10_makefile_blob"
test "$(git -C "$historical" hash-object controllers/crazyflie_runtime_v2/runtime.ini)" = "$c10_runtime_ini_blob"

python3 - "$historical/controllers/crazyflie_runtime_v2/file_broker.cpp" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

include_old = """#ifdef WEBEEBLOCKS_QT_CRASH_DIAGNOSTIC
#include <csignal>
#include <unistd.h>
#endif"""
include_new = """#ifdef WEBEEBLOCKS_QT_CRASH_DIAGNOSTIC
#include <csignal>
#include <execinfo.h>
#include <unistd.h>
#endif"""
if source.count(include_old) != 1:
    raise SystemExit("frozen C10 diagnostic include seam changed")
source = source.replace(include_old, include_new, 1)

anchor = 'constexpr const char *kPrefix = "WEBEEBLOCKS_FILE_BROKER_V1";\n'
instrumentation = r'''
#ifdef WEBEEBLOCKS_QT_CRASH_DIAGNOSTIC
void write_diagnostic_marker(const char *message) {
  ::write(STDERR_FILENO, message, std::strlen(message));
}

void fatal_signal_handler(int signal_number) {
  switch (signal_number) {
    case SIGSEGV:
      write_diagnostic_marker("WEBEEBLOCKS_C14_C10_FATAL signal=SIGSEGV\n");
      break;
    case SIGABRT:
      write_diagnostic_marker("WEBEEBLOCKS_C14_C10_FATAL signal=SIGABRT\n");
      break;
    case SIGBUS:
      write_diagnostic_marker("WEBEEBLOCKS_C14_C10_FATAL signal=SIGBUS\n");
      break;
    case SIGILL:
      write_diagnostic_marker("WEBEEBLOCKS_C14_C10_FATAL signal=SIGILL\n");
      break;
    case SIGFPE:
      write_diagnostic_marker("WEBEEBLOCKS_C14_C10_FATAL signal=SIGFPE\n");
      break;
    default:
      write_diagnostic_marker("WEBEEBLOCKS_C14_C10_FATAL signal=UNKNOWN\n");
      break;
  }

  void *frames[64];
  const int count = ::backtrace(frames, 64);
  write_diagnostic_marker("WEBEEBLOCKS_C14_C10_BACKTRACE_BEGIN\n");
  ::backtrace_symbols_fd(frames, count, STDERR_FILENO);
  write_diagnostic_marker("WEBEEBLOCKS_C14_C10_BACKTRACE_END\n");
  _exit(128 + signal_number);
}

bool install_fatal_handlers() {
  void *warmup[1];
  (void)::backtrace(warmup, 1);

  struct sigaction action {};
  action.sa_handler = fatal_signal_handler;
  sigemptyset(&action.sa_mask);
  action.sa_flags = SA_RESETHAND;

  const int fatal_signals[] = {SIGSEGV, SIGABRT, SIGBUS, SIGILL, SIGFPE};
  for (const int signal_number : fatal_signals) {
    if (sigaction(signal_number, &action, nullptr) != 0)
      return false;
  }
  return true;
}
#endif
'''
if source.count(anchor) != 1:
    raise SystemExit("frozen C10 namespace seam changed")
source = source.replace(anchor, anchor + instrumentation, 1)

stop = "    ::raise(SIGSTOP);"
replacement = """    if (!install_fatal_handlers())
      throw std::runtime_error("diagnostic signal handler installation failed");
    std::fprintf(stderr, "WEBEEBLOCKS_C14_C10_HANDLERS_ACTIVE\\n");
    std::fflush(stderr);"""
if source.count(stop) != 1:
    raise SystemExit("frozen C10 SIGSTOP seam changed")
source = source.replace(stop, replacement, 1)

path.write_text(source, encoding="utf-8")
PY

git -C "$historical" diff -- controllers/crazyflie_runtime_v2/file_broker.cpp |
  tee "$artifact_dir/c10-instrumentation.patch"
test -s "$artifact_dir/c10-instrumentation.patch"

recipe="$RUNNER_TEMP/linux_runtime_dependencies-R2025a.sh"
recipe_url=https://raw.githubusercontent.com/cyberbotics/webots/R2025a/scripts/install/linux_runtime_dependencies.sh
recipe_blob=4593476be2c985580a0e1738671f4b5bae81f669
curl --fail --location --retry 3 --output "$recipe" "$recipe_url"
test "$(git hash-object "$recipe")" = "$recipe_blob"
sudo env CI=true bash "$recipe"

archive="$RUNNER_TEMP/webots-R2025a-x86-64.tar.bz2"
archive_url=https://github.com/cyberbotics/webots/releases/download/R2025a/webots-R2025a-x86-64.tar.bz2
archive_sha=c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38
curl --fail --location --retry 3 --output "$archive" "$archive_url"
echo "$archive_sha  $archive" | sha256sum --check
tar -xjf "$archive" -C "$RUNNER_TEMP"
diagnostic_webots="$RUNNER_TEMP/webots"
test -x "$diagnostic_webots/webots"

WEBOTS_HOME="$diagnostic_webots" make -C "$historical/controllers/crazyflie_runtime_v2" clean
WEBOTS_HOME="$diagnostic_webots" make -C "$historical/controllers/crazyflie_runtime_v2" \
  WEBEEBLOCKS_NATIVE_FILE_BROKER=1 \
  WEBEEBLOCKS_QT_CRASH_DIAGNOSTIC=1 \
  VERBOSE=1 2>&1 | tee "$artifact_dir/c10-build.log"

controller="$historical/controllers/crazyflie_runtime_v2/crazyflie_runtime_v2"
test -x "$controller"
real_controller="$controller.real"
mv "$controller" "$real_controller"
cat > "$controller" <<'SH'
#!/usr/bin/env bash
set +e
real="$0.real"
"$real" "$@" &
pid=$!
printf 'WEBEEBLOCKS_C14_C10_PROCESS pid=%s\n' "$pid" >&2
wait "$pid"
code=$?
printf 'WEBEEBLOCKS_C14_C10_PROCESS_EXIT pid=%s code=%s\n' "$pid" "$code" >&2
exit "$code"
SH
chmod +x "$controller"

standalone_cpp="$RUNNER_TEMP/c14-standalone-qt.cpp"
standalone="$RUNNER_TEMP/c14-standalone-qt"
cat > "$standalone_cpp" <<'CPP'
#include <QtWidgets/QApplication>
#include <QtWidgets/QFileDialog>

#include <csignal>
#include <cstring>
#include <execinfo.h>
#include <unistd.h>

namespace {

void mark(const char *message) {
  ::write(STDERR_FILENO, message, std::strlen(message));
}

void fatal_signal_handler(int signal_number) {
  switch (signal_number) {
    case SIGSEGV:
      mark("WEBEEBLOCKS_C14_STANDALONE_FATAL signal=SIGSEGV\n");
      break;
    case SIGABRT:
      mark("WEBEEBLOCKS_C14_STANDALONE_FATAL signal=SIGABRT\n");
      break;
    case SIGBUS:
      mark("WEBEEBLOCKS_C14_STANDALONE_FATAL signal=SIGBUS\n");
      break;
    case SIGILL:
      mark("WEBEEBLOCKS_C14_STANDALONE_FATAL signal=SIGILL\n");
      break;
    case SIGFPE:
      mark("WEBEEBLOCKS_C14_STANDALONE_FATAL signal=SIGFPE\n");
      break;
    default:
      mark("WEBEEBLOCKS_C14_STANDALONE_FATAL signal=UNKNOWN\n");
      break;
  }

  void *frames[64];
  const int count = ::backtrace(frames, 64);
  mark("WEBEEBLOCKS_C14_STANDALONE_BACKTRACE_BEGIN\n");
  ::backtrace_symbols_fd(frames, count, STDERR_FILENO);
  mark("WEBEEBLOCKS_C14_STANDALONE_BACKTRACE_END\n");
  _exit(128 + signal_number);
}

bool install_fatal_handlers() {
  void *warmup[1];
  (void)::backtrace(warmup, 1);

  struct sigaction action {};
  action.sa_handler = fatal_signal_handler;
  sigemptyset(&action.sa_mask);
  action.sa_flags = SA_RESETHAND;

  const int fatal_signals[] = {SIGSEGV, SIGABRT, SIGBUS, SIGILL, SIGFPE};
  for (const int signal_number : fatal_signals) {
    if (sigaction(signal_number, &action, nullptr) != 0)
      return false;
  }
  return true;
}

}  // namespace

int main(int argc, char **argv) {
  if (!install_fatal_handlers())
    return 3;
  mark("WEBEEBLOCKS_C14_STANDALONE_HANDLERS_ACTIVE\n");
  QApplication application(argc, argv);
  mark("WEBEEBLOCKS_C14_STANDALONE_QAPPLICATION_INITIALIZED\n");
  QFileDialog dialog;
  mark("WEBEEBLOCKS_C14_STANDALONE_QFILEDIALOG_CONSTRUCTED\n");
  return 0;
}
CPP

g++ -std=c++17 -g -O0 \
  -isystem "$diagnostic_webots/include/qt/QtCore" \
  -isystem "$diagnostic_webots/include/qt/QtGui" \
  -isystem "$diagnostic_webots/include/qt/QtWidgets" \
  "$standalone_cpp" \
  -L"$diagnostic_webots/lib/webots" \
  -lQt6Widgets -lQt6Gui -lQt6Core \
  -o "$standalone"

LD_LIBRARY_PATH="$diagnostic_webots/lib/webots" ldd "$real_controller" |
  tee "$artifact_dir/c10-ldd.log"
LD_LIBRARY_PATH="$diagnostic_webots/lib/webots" ldd "$standalone" |
  tee "$artifact_dir/standalone-ldd.log"
for ldd_log in "$artifact_dir/c10-ldd.log" "$artifact_dir/standalone-ldd.log"; do
  qt_lines="$(grep 'libQt6\(Core\|Gui\|Widgets\)' "$ldd_log")"
  test "$(printf '%s\n' "$qt_lines" | wc -l)" -eq 3
  if printf '%s\n' "$qt_lines" | grep -vF "$diagnostic_webots/lib/webots/"; then
    echo "Qt resolved outside the official Webots desktop SDK in $ldd_log" >&2
    exit 1
  fi
done

standalone_log="$artifact_dir/standalone.log"
c10_log="$artifact_dir/c10-webots.log"
runner="$RUNNER_TEMP/c14-same-xvfb.sh"
cat > "$runner" <<RUN
#!/usr/bin/env bash
set +e
export LD_LIBRARY_PATH="$diagnostic_webots/lib/webots"
export QT_PLUGIN_PATH="$diagnostic_webots/lib/webots/qt/plugins"
export QT_DEBUG_PLUGINS=1
export LIBGL_ALWAYS_SOFTWARE=true
export WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true

timeout -k 2s 10s "$standalone" > "$standalone_log" 2>&1
standalone_code=\$?

timeout -k 5s 45s "$diagnostic_webots/webots" \
  --stdout --stderr --batch --mode=realtime \
  "$historical/worlds/crazyflie_runtime_v2.wbt" \
  > "$c10_log" 2>&1
webots_code=\$?

printf 'standalone_exit=%s\nc10_outer_webots_exit=%s\n' "\$standalone_code" "\$webots_code" \
  > "$artifact_dir/run-exits.txt"
exit 0
RUN
chmod +x "$runner"
xvfb-run -a "$runner"

cat "$standalone_log"
cat "$c10_log"
cat "$artifact_dir/run-exits.txt"

standalone_code="$(sed -n 's/^standalone_exit=//p' "$artifact_dir/run-exits.txt")"
standalone_result=UNPROVEN
if [ "$standalone_code" = "0" ] &&
   grep -Fq 'WEBEEBLOCKS_C14_STANDALONE_QAPPLICATION_INITIALIZED' "$standalone_log" &&
   grep -Fq 'WEBEEBLOCKS_C14_STANDALONE_QFILEDIALOG_CONSTRUCTED' "$standalone_log"; then
  standalone_result=THROUGH_QFILEDIALOG
elif grep -Eq 'WEBEEBLOCKS_C14_STANDALONE_FATAL signal=SIG(SEGV|ABRT|BUS|ILL|FPE)' "$standalone_log" &&
     grep -Fq 'WEBEEBLOCKS_C14_STANDALONE_BACKTRACE_BEGIN' "$standalone_log" &&
     grep -Fq 'WEBEEBLOCKS_C14_STANDALONE_BACKTRACE_END' "$standalone_log"; then
  awk '
    /WEBEEBLOCKS_C14_STANDALONE_BACKTRACE_BEGIN/ {capture=1; next}
    /WEBEEBLOCKS_C14_STANDALONE_BACKTRACE_END/ {capture=0}
    capture {print}
  ' "$standalone_log" > "$artifact_dir/standalone-backtrace.txt"
  test -s "$artifact_dir/standalone-backtrace.txt"
  grep -Eq 'libQt6(Core|Gui|Widgets)|libQt6XcbQpa|libqxcb|QApplication'     "$artifact_dir/standalone-backtrace.txt"
  signal="$(sed -n 's/.*WEBEEBLOCKS_C14_STANDALONE_FATAL signal=\(SIG[A-Z0-9]*\).*/\1/p' "$standalone_log" | tail -n 1)"
  case "$signal" in
    SIGSEGV) expected_exit=139 ;;
    SIGABRT) expected_exit=134 ;;
    SIGBUS) expected_exit=135 ;;
    SIGILL) expected_exit=132 ;;
    SIGFPE) expected_exit=136 ;;
    *) echo "Unsupported standalone signal: $signal" >&2; exit 1 ;;
  esac
  test "$standalone_code" = "$expected_exit"
  standalone_result=FATAL_QT_FRAME
fi
test "$standalone_result" != "UNPROVEN"

grep -Fq 'WEBEEBLOCKS_FILE_BROKER_V1 DIAGNOSTIC_RENDEZVOUS' "$c10_log"
grep -Fq 'WEBEEBLOCKS_C14_C10_HANDLERS_ACTIVE' "$c10_log"

c10_result=UNPROVEN
if grep -Fq 'WEBEEBLOCKS_FILE_BROKER_V1 QFILEDIALOG_CONSTRUCTED' "$c10_log"; then
  c10_result=THROUGH_QFILEDIALOG
elif grep -Eq 'WEBEEBLOCKS_C14_C10_FATAL signal=SIG(SEGV|ABRT|BUS|ILL|FPE)' "$c10_log" &&
     grep -Fq 'WEBEEBLOCKS_C14_C10_BACKTRACE_BEGIN' "$c10_log" &&
     grep -Fq 'WEBEEBLOCKS_C14_C10_BACKTRACE_END' "$c10_log"; then
  awk '
    /WEBEEBLOCKS_C14_C10_BACKTRACE_BEGIN/ {capture=1; next}
    /WEBEEBLOCKS_C14_C10_BACKTRACE_END/ {capture=0}
    capture {print}
  ' "$c10_log" > "$artifact_dir/c10-backtrace.txt"
  test -s "$artifact_dir/c10-backtrace.txt"
  grep -Eq 'libQt6(Core|Gui|Widgets)|libQt6XcbQpa|libqxcb|QApplication|QtFileDialogProvider'     "$artifact_dir/c10-backtrace.txt"

  signal="$(sed -n 's/.*WEBEEBLOCKS_C14_C10_FATAL signal=\(SIG[A-Z0-9]*\).*/\1/p' "$c10_log" | tail -n 1)"
  process_pid="$(sed -n 's/.*WEBEEBLOCKS_C14_C10_PROCESS pid=\([0-9][0-9]*\).*/\1/p' "$c10_log" | tail -n 1)"
  exit_pid="$(sed -n 's/.*WEBEEBLOCKS_C14_C10_PROCESS_EXIT pid=\([0-9][0-9]*\) code=.*/\1/p' "$c10_log" | tail -n 1)"
  exit_code="$(sed -n 's/.*WEBEEBLOCKS_C14_C10_PROCESS_EXIT pid=[0-9][0-9]* code=\([0-9][0-9]*\).*/\1/p' "$c10_log" | tail -n 1)"
  test -n "$process_pid"
  test "$exit_pid" = "$process_pid"
  case "$signal" in
    SIGSEGV) expected_exit=139 ;;
    SIGABRT) expected_exit=134 ;;
    SIGBUS) expected_exit=135 ;;
    SIGILL) expected_exit=132 ;;
    SIGFPE) expected_exit=136 ;;
    *) echo "Unsupported C10 signal: $signal" >&2; exit 1 ;;
  esac
  test "$exit_code" = "$expected_exit"
  printf 'controller_pid=%s\nsignal=%s\ncontroller_exit=%s\n' \
    "$process_pid" "$signal" "$exit_code" > "$artifact_dir/c10-process-exit.txt"
  c10_result=FATAL_QT_FRAME
fi
test "$c10_result" != "UNPROVEN"

printf 'standalone=%s\nc10=%s\n' "$standalone_result" "$c10_result" |
  tee "$artifact_dir/classification.txt"

if [ "$standalone_result" = "THROUGH_QFILEDIALOG" ] &&
   [ "$c10_result" = "FATAL_QT_FRAME" ]; then
  printf '%s\n' 'DIAGNOSTIC_RESULT=C14_STANDALONE_OK_C10_QT_XCB_CRASH' |
    tee "$artifact_dir/result.txt"
  exit 0
fi

if [ "$standalone_result" = "FATAL_QT_FRAME" ] &&
   [ "$c10_result" = "FATAL_QT_FRAME" ]; then
  printf '%s\n' 'DIAGNOSTIC_RESULT=C14_STANDALONE_AND_C10_QT_CRASH' |
    tee "$artifact_dir/result.txt"
  exit 0
fi

printf '%s\n' 'DIAGNOSTIC_RESULT=C14_COMPARISON_UNPROVEN' |
  tee "$artifact_dir/result.txt"
exit 1
