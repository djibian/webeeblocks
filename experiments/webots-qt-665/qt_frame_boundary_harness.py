#!/usr/bin/env python3
"""Generate new frame/parent falsification cases; never substitutes for Webots.

Method bodies remain verbatim. Observe their Qt frames independently using GDB.
The parent case is deliberately destructive and runs in its own process.
"""
import argparse
from pathlib import Path
from qt_guarded_method_harness import HEADER

FOOTER = r'''
#include <cstring>
int main(int argc, char **argv) {
  QApplication app(argc, argv);
  if (argc != 2) return 2;
  const bool parent = std::strcmp(argv[1], "parent") == 0;
  const bool external = std::strcmp(argv[1], "external") == 0;
  const bool retire = std::strcmp(argv[1], "retire") == 0;
  if (!parent && !external && !retire) return 2;
  QPointer<WbMainWindow> window = new WbMainWindow;
  window->createWorldLoadingProgressDialog();
  QPointer<QProgressDialog> old = window->current();
  QPointer<QProgressBar> bar = old->findChild<QProgressBar *>();
  old->setMinimumDuration(0);
  old->setValue(1);
  if (external) old->setModal(false);
  bool callback = false;
  QTimer::singleShot(0, &app, [&]() {
    callback = true;
    if (parent) delete window.data();
    else window->deleteWorldLoadingProgressDialog();
    std::printf("CALLBACK mode=%s window_alive=%d dialog_alive=%d bar_alive=%d\n",
                argv[1], !window.isNull(), !old.isNull(), !bar.isNull());
    std::fflush(stdout);
  });
  window->setWorldLoadingProgress(51);
  std::printf("METHOD_RETURN mode=%s callback=%d window_alive=%d dialog_alive=%d bar_alive=%d\n",
              argv[1], callback, !window.isNull(), !old.isNull(), !bar.isNull());
  std::fflush(stdout);
  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
  QApplication::processEvents();
  if (window) delete window.data();
  return callback ? 0 : 3;
}
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--patched-cpp', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    cpp = args.patched_cpp.read_text()
    start = cpp.index('void WbMainWindow::runWorldLoadingProgressOperation(')
    end = cpp.index('void WbMainWindow::startAnimationRecording()', start)
    args.output.write_text(HEADER + cpp[start:end] + FOOTER)

if __name__ == '__main__':
    main()
