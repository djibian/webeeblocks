#include "qt_init_probe_c.h"

#include <QtCore/QCoreApplication>
#include <QtWidgets/QApplication>
#include <QtWidgets/QFileDialog>

#include <array>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <execinfo.h>
#include <memory>
#include <unistd.h>

namespace {

void write_marker(const char *message) {
  ::write(STDERR_FILENO, message, std::strlen(message));
}

void fatal_signal_handler(int signal_number) {
  switch (signal_number) {
    case SIGSEGV:
      write_marker("WEBEEBLOCKS_QT_FATAL signal=SIGSEGV\n");
      break;
    case SIGABRT:
      write_marker("WEBEEBLOCKS_QT_FATAL signal=SIGABRT\n");
      break;
    case SIGBUS:
      write_marker("WEBEEBLOCKS_QT_FATAL signal=SIGBUS\n");
      break;
    case SIGILL:
      write_marker("WEBEEBLOCKS_QT_FATAL signal=SIGILL\n");
      break;
    case SIGFPE:
      write_marker("WEBEEBLOCKS_QT_FATAL signal=SIGFPE\n");
      break;
    default:
      write_marker("WEBEEBLOCKS_QT_FATAL signal=UNKNOWN\n");
      break;
  }

  void *frames[64];
  const int count = ::backtrace(frames, 64);
  write_marker("WEBEEBLOCKS_QT_FATAL_BACKTRACE_BEGIN\n");
  ::backtrace_symbols_fd(frames, count, STDERR_FILENO);
  write_marker("WEBEEBLOCKS_QT_FATAL_BACKTRACE_END\n");
  _exit(128 + signal_number);
}

bool install_fatal_handlers() {
  // Warm libgcc's unwinder before any asynchronous fault path.
  void *warmup[1];
  (void)::backtrace(warmup, 1);

  struct sigaction action {};
  action.sa_handler = fatal_signal_handler;
  sigemptyset(&action.sa_mask);
  action.sa_flags = SA_RESETHAND;

  for (const int signal_number : {SIGSEGV, SIGABRT, SIGBUS, SIGILL, SIGFPE}) {
    if (sigaction(signal_number, &action, nullptr) != 0)
      return false;
  }
  return true;
}

}  // namespace

extern "C" int wb_qt_init_probe(void) {
  if (!install_fatal_handlers()) {
    std::fprintf(stderr, "WEBEEBLOCKS_QT_INIT_DIAGNOSTIC HANDLER_INSTALL_FAILED\n");
    std::fflush(stderr);
    return 3;
  }

  int argc = 1;
  std::array<char, 64> program_name{};
  std::array<char *, 2> argv{};
  std::strcpy(program_name.data(), "webeeblocks-qt-init-probe");
  argv[0] = program_name.data();
  argv[1] = nullptr;

  std::fprintf(stderr, "WEBEEBLOCKS_QT_INIT_DIAGNOSTIC PRE_QAPPLICATION\n");
  std::fflush(stderr);

  std::unique_ptr<QApplication> application;
  if (!QCoreApplication::instance())
    application = std::make_unique<QApplication>(argc, argv.data());
  if (!qobject_cast<QApplication *>(QCoreApplication::instance()))
    return 2;

  std::fprintf(stderr, "WEBEEBLOCKS_QT_INIT_DIAGNOSTIC QT_APP_INITIALIZED\n");
  std::fflush(stderr);

  QFileDialog dialog;
  std::fprintf(stderr, "WEBEEBLOCKS_QT_INIT_DIAGNOSTIC QFILEDIALOG_CONSTRUCTED\n");
  std::fflush(stderr);

  // Deliberate terminal marker: SIGTRAP is not handled by the fatal handler.
  ::raise(SIGTRAP);
  return 0;
}
