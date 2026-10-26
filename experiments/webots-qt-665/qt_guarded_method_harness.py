#!/usr/bin/env python3
"""Generate a Qt adversarial harness from the EXACT patched Webots methods.

This compiles copied, byte-identical *method implementations* in a minimal
Qt shell. It is not a full Webots binary, or proof of Webots native A/B.
"""
import argparse
from pathlib import Path

HEADER = r"""
#include <QtCore/QEvent>
#include <QtCore/QList>
#include <QtCore/QPointer>
#include <QtCore/QTimer>
#include <QtWidgets/QApplication>
#include <QtWidgets/QMainWindow>
#include <QtWidgets/QProgressBar>
#include <QtWidgets/QProgressDialog>
#include <QtWidgets/QPushButton>
#include <functional>
#include <cstdio>

class WbApplication : public QObject {
public:
  static WbApplication *instance() {
    static WbApplication application;
    return &application;
  }
  void setWorldLoadingCanceled() { ++cancelCount; }
  int cancelCount = 0;
};

class WbGuiApplication {
public:
  static void setWindowsDarkMode(QWidget *) {}
};

class WbMainWindow : public QMainWindow {
public:
  WbMainWindow() : mWorldLoadingProgressDialog(nullptr), mWorldLoadingProgressOperationDepth(0) {}
  void createWorldLoadingProgressDialog();
  void deleteWorldLoadingProgressDialog();
  void setWorldLoadingProgress(const int progress);
  void setWorldLoadingStatus(const QString &status);
  void runWorldLoadingProgressOperation(const std::function<void()> &operation);
  QProgressDialog *current() const { return mWorldLoadingProgressDialog; }
  unsigned int operationDepth() const { return mWorldLoadingProgressOperationDepth; }
private:
  QProgressDialog *mWorldLoadingProgressDialog;
  unsigned int mWorldLoadingProgressOperationDepth;
  QList<QProgressDialog *> mRetiredWorldLoadingProgressDialogs;
};
"""

FOOTER = r"""
static bool testRetireWhileSetValueAndRecreate() {
  WbMainWindow window;
  window.createWorldLoadingProgressDialog();
  QPointer<QProgressDialog> old = window.current();
  if (!old) return false;
  old->setRange(0, 100);
  QPointer<QProgressBar> oldBar = old->findChild<QProgressBar *>();
  if (!oldBar) return false;

  bool callback = false;
  bool oldAliveInside = false;
  bool guardedFrame = false;
  bool freshIdentity = false;
  QPointer<QProgressDialog> fresh;
  QTimer::singleShot(0, &window, [&]() {
    callback = true;
    guardedFrame = window.operationDepth() > 0;
    window.deleteWorldLoadingProgressDialog();
    window.deleteWorldLoadingProgressDialog(); // idempotent
    oldAliveInside = !old.isNull() && !oldBar.isNull();
    window.createWorldLoadingProgressDialog();
    fresh = window.current();
    freshIdentity = !fresh.isNull() && fresh.data() != old.data();
  });
  window.setWorldLoadingProgress(51); // QProgressDialog modal nested event loop
  bool oldAliveAfterReturn = !old.isNull() && !oldBar.isNull();
  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
  QApplication::processEvents();
  bool retiredWasDestroyed = old.isNull() && oldBar.isNull();
  bool freshRemainsActive = !fresh.isNull() && window.current() == fresh.data();

  window.setWorldLoadingStatus(QStringLiteral("second generation"));
  bool freshSurvivedStatus = !fresh.isNull();
  window.deleteWorldLoadingProgressDialog();
  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
  QApplication::processEvents();
  bool freshDestroyed = fresh.isNull();

  std::printf("retire_mid_setValue: callback=%d guarded=%d old_alive_inside=%d old_alive_at_return=%d "
              "fresh_distinct=%d old_destroyed_after_return=%d fresh_active=%d status_safe=%d fresh_drained=%d\n",
              callback, guardedFrame, oldAliveInside, oldAliveAfterReturn, freshIdentity,
              retiredWasDestroyed, freshRemainsActive, freshSurvivedStatus, freshDestroyed);
  return callback && guardedFrame && oldAliveInside && oldAliveAfterReturn && freshIdentity &&
         retiredWasDestroyed && freshRemainsActive && freshSurvivedStatus && freshDestroyed;
}

static bool testRetireDuringCreation() {
  WbMainWindow window;
  bool callback = false;
  bool guarded = false;
  QPointer<QProgressDialog> captured;
  QTimer::singleShot(0, &window, [&]() {
    callback = true;
    guarded = window.operationDepth() > 0;
    captured = window.current();
    window.deleteWorldLoadingProgressDialog();
  });
  window.createWorldLoadingProgressDialog();
  bool aliveAfter = !captured.isNull();
  bool inactive = window.current() == nullptr;
  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
  QApplication::processEvents();
  bool drained = captured.isNull();
  std::printf("retire_during_creation: callback=%d guarded=%d alive_after=%d inactive=%d drained=%d\n",
              callback, guarded, aliveAfter, inactive, drained);
  return callback && guarded && aliveAfter && inactive && drained;
}

static bool testRetireDuringStatus() {
  WbMainWindow window;
  window.createWorldLoadingProgressDialog();
  QPointer<QProgressDialog> original = window.current();
  bool callback = false;
  bool guarded = false;
  QTimer::singleShot(0, &window, [&]() {
    callback = true;
    guarded = window.operationDepth() > 0;
    window.deleteWorldLoadingProgressDialog();
  });
  window.setWorldLoadingStatus(QStringLiteral("progress update"));
  bool oldAlive = !original.isNull();
  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
  QApplication::processEvents();
  bool drained = original.isNull();
  std::printf("retire_during_status: callback=%d guarded=%d alive_after=%d drained=%d\n",
              callback, guarded, oldAlive, drained);
  return callback && guarded && oldAlive && drained;
}

static bool testCancelPreserved() {
  WbMainWindow window;
  window.createWorldLoadingProgressDialog();
  auto *dialog = window.current();
  if (!dialog) return false;
  auto *button = dialog->findChild<QPushButton *>();
  if (!button) return false;
  int before = WbApplication::instance()->cancelCount;
  button->click();
  int after = WbApplication::instance()->cancelCount;
  window.deleteWorldLoadingProgressDialog();
  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
  QApplication::processEvents();
  std::printf("cancel_preserved: before=%d after=%d\n", before, after);
  return after == before + 1;
}

int main(int argc, char **argv) {
  QApplication application(argc, argv);
  bool s1 = testRetireWhileSetValueAndRecreate();
  bool s2 = testRetireDuringCreation();
  bool s3 = testRetireDuringStatus();
  bool s4 = testCancelPreserved();
  std::printf("QT665_GUARDED_METHODS_VERDICT=%s\n", (s1 && s2 && s3 && s4) ? "PASS" : "FAIL");
  return (s1 && s2 && s3 && s4) ? 0 : 1;
}
"""

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patched-cpp", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    cpp = arguments.patched_cpp.read_text()
    start = cpp.index("void WbMainWindow::runWorldLoadingProgressOperation(")
    stop = cpp.index("void WbMainWindow::startAnimationRecording()", start)
    methods = cpp[start:stop]
    required = (
        "void WbMainWindow::createWorldLoadingProgressDialog()",
        "void WbMainWindow::deleteWorldLoadingProgressDialog()",
        "void WbMainWindow::setWorldLoadingProgress(",
        "void WbMainWindow::setWorldLoadingStatus(",
        "mRetiredWorldLoadingProgressDialogs.append(dialog)",
    )
    if not all(term in methods for term in required):
        raise RuntimeError("The exact upstream-patched methods are not present")
    arguments.output.write_text(HEADER + "\n" + methods + "\n" + FOOTER)


if __name__ == "__main__":
    main()
