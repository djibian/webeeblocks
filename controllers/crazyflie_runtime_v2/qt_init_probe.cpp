#include "qt_init_probe_c.h"

#include <QtCore/QCoreApplication>
#include <QtWidgets/QApplication>
#include <QtWidgets/QFileDialog>

#include <array>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <memory>
#include <unistd.h>

extern "C" int wb_qt_init_probe(void) {
  int argc = 1;
  std::array<char, 64> program_name{};
  std::array<char *, 2> argv{};
  std::strcpy(program_name.data(), "webeeblocks-qt-init-probe");
  argv[0] = program_name.data();
  argv[1] = nullptr;

  std::fprintf(
    stderr,
    "WEBEEBLOCKS_QT_INIT_DIAGNOSTIC RENDEZVOUS pid=%ld before=QApplication\n",
    static_cast<long>(::getpid()));
  std::fflush(stderr);
  ::raise(SIGSTOP);

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

  ::raise(SIGTRAP);
  return 0;
}
