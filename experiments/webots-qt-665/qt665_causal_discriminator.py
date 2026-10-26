#!/usr/bin/env python3
"""#665: generate C++ from exact patched R2025a methods and two discriminating Qt event tests.

Not a full-Webots integration test. A separate GDB evaluator MUST prove the
actual stack, QProgressBar::maximum address, and DeferredDelete ordering.
"""
import argparse
from pathlib import Path
import subprocess
import sys

TESTS = r"""
extern "C" __attribute__((noinline)) void qt665_marker(int phase, void *dialog, void *bar) {
  // A noinline marker is a stable GDB observation point. Do not modify Qt code.
  asm volatile("" ::: "memory");
}

static void qt665_flush() {
  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
  QApplication::processEvents();
  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
}

static bool qt665_positive() {
  WbMainWindow window;
  window.createWorldLoadingProgressDialog();
  QPointer<QProgressDialog> old = window.current();
  if (!old) return false;
  old->setModal(true);
  old->show();
  QApplication::processEvents(); // ensure Qt's shownOnce is established
  old->setRange(0, 100);
  old->setValue(12);
  // Qt's native forceShow() slot sets shownOnce; show() alone does not.
  // Invoke the actual Qt metaobject slot, never write Qt private memory.
  if (!QMetaObject::invokeMethod(old.data(), "forceShow", Qt::DirectConnection))
    return false;
  QApplication::processEvents();
  QPointer<QProgressBar> bar = old->findChild<QProgressBar *>();
  if (!bar) return false;
  void *dialogId = old.data();
  void *barId = bar.data();
  bool callback = false;
  QObject::connect(bar.data(), &QObject::destroyed, &window,
                   [=]() { qt665_marker(14, dialogId, barId); });
  qt665_marker(10, dialogId, barId);
  QTimer::singleShot(0, &window, [&]() {
    callback = true;
    qt665_marker(11, dialogId, barId);
    window.deleteWorldLoadingProgressDialog();
    qt665_marker(12, dialogId, barId);
  });
  window.setWorldLoadingProgress(51);
  qt665_marker(13, dialogId, barId);
  const bool aliveAfterProtectedReturn = !old.isNull() && !bar.isNull();
  qt665_flush();
  const bool goneAfterFlush = old.isNull() && bar.isNull();
  const bool inactive = window.current() == nullptr;
  qt665_marker(15, dialogId, barId);
  std::printf("QT665_POSITIVE callback=%d alive_after_return=%d gone_after_flush=%d inactive=%d\n",
              callback, aliveAfterProtectedReturn, goneAfterFlush, inactive);
  return callback && aliveAfterProtectedReturn && goneAfterFlush && inactive;
}

static bool qt665_negative_outer_events() {
  WbMainWindow window;
  window.createWorldLoadingProgressDialog();
  QPointer<QProgressDialog> old = window.current();
  if (!old) return false;
  old->setModal(false); // prevent QProgressDialog::setValue's nested processEvents
  old->show();
  QApplication::processEvents();
  old->setRange(0, 100);
  old->setValue(12);
  if (!QMetaObject::invokeMethod(old.data(), "forceShow", Qt::DirectConnection))
    return false;
  QPointer<QProgressBar> bar = old->findChild<QProgressBar *>();
  if (!bar) return false;
  void *dialogId = old.data();
  void *barId = bar.data();
  bool callback = false;
  QObject::connect(bar.data(), &QObject::destroyed, &window,
                   [=]() { qt665_marker(24, dialogId, barId); });
  qt665_marker(20, dialogId, barId);
  QTimer::singleShot(0, &window, [&]() {
    callback = true;
    qt665_marker(21, dialogId, barId);
    window.deleteWorldLoadingProgressDialog();
    qt665_marker(22, dialogId, barId);
  });
  window.setWorldLoadingProgress(51);
  qt665_marker(23, dialogId, barId);
  const bool aliveAfterProtectedReturn = !old.isNull() && !bar.isNull();
  qt665_flush();
  const bool goneAfterFlush = old.isNull() && bar.isNull();
  qt665_marker(25, dialogId, barId);
  std::printf("QT665_NEGATIVE callback=%d alive_after_return=%d gone_after_flush=%d\n",
              callback, aliveAfterProtectedReturn, goneAfterFlush);
  return callback && aliveAfterProtectedReturn && goneAfterFlush;
}

"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patched-cpp", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("qt665_guarded_lease_harness.py")),
         "--patched-cpp", str(args.patched_cpp), "--output", str(args.output)],
        check=True,
    )
    cpp = args.output.read_text()
    signature = "int main(int argc, char **argv) {"
    assert cpp.count(signature) == 1
    assert cpp.count("bool s4 = testCancelPreserved();") == 1
    assert cpp.count("(s1 && s2 && s3 && s4)") == 2
    cpp = cpp.replace(signature, TESTS + "\n" + "\nstatic bool qt665_late_cancel_generations() {\n  WbMainWindow window;\n  window.createWorldLoadingProgressDialog();\n  QPointer<QProgressDialog> first = window.current();\n  if (!first) return false;\n  QPointer<QPushButton> oldButton = first->findChild<QPushButton *>();\n  if (!oldButton) return false;\n  const int before = WbApplication::instance()->cancelCount;\n  window.deleteWorldLoadingProgressDialog();\n  // Late user-originated cancel on retired-but-live generation MUST NOT\n  // forward the old canceled signal to the singleton download manager.\n  const bool oldAliveBeforeDeferred = !first.isNull() && !oldButton.isNull();\n  if (oldAliveBeforeDeferred)\n    oldButton->click();\n  const bool staleCancelDisconnected =\n      WbApplication::instance()->cancelCount == before;\n  window.createWorldLoadingProgressDialog();\n  QPointer<QProgressDialog> second = window.current();\n  const bool secondDistinct = second && second != first;\n  window.setWorldLoadingProgress(4);\n  window.setWorldLoadingStatus(QStringLiteral(\"second generation\"));\n  window.deleteWorldLoadingProgressDialog();\n  window.createWorldLoadingProgressDialog();\n  QPointer<QProgressDialog> third = window.current();\n  const bool thirdDistinct = third && third != first && third != second;\n  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);\n  QApplication::processEvents();\n  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);\n  const bool oldDrained = first.isNull() && second.isNull();\n  const bool freshAlive = third && third.data() == window.current();\n  const bool unaffected = WbApplication::instance()->cancelCount == before;\n  window.deleteWorldLoadingProgressDialog();\n  QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);\n  QApplication::processEvents();\n  const bool freshDrained = third.isNull();\n  std::printf(\"QT665_LATE_CANCEL_GENERATIONS old_alive=%d disconnected=%d second_unique=%d third_unique=%d old_drained=%d fresh_alive=%d unaffected=%d fresh_drained=%d\\n\",\n       oldAliveBeforeDeferred, staleCancelDisconnected, secondDistinct,\n       thirdDistinct, oldDrained, freshAlive, unaffected, freshDrained);\n  return oldAliveBeforeDeferred && staleCancelDisconnected && secondDistinct\n         && thirdDistinct && oldDrained && freshAlive && unaffected\n         && freshDrained;\n}\n" + "\n" + signature, 1)
    cpp = cpp.replace("bool s4 = testCancelPreserved();",
                      "bool s4 = testCancelPreserved();\n"
                      "  bool s5 = qt665_positive();\n"
                      "  bool s6 = qt665_negative_outer_events();\n"\n"  bool s7 = qt665_late_cancel_generations();", 1)
    cpp = cpp.replace("(s1 && s2 && s3 && s4)",
                      "(s1 && s2 && s3 && s4 && s5 && s6 && s7)")
    args.output.write_text(cpp)


if __name__ == "__main__":
    main()
