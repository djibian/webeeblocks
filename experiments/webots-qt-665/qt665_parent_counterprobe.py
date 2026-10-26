#!/usr/bin/env python3
"""Parent-destruction counterprobe from original patched Webots methods.

Run in a dedicated inferior; expected unsafe behavior must NOT be hidden.
The probe uses the actual modal Qt slot and destroys the window in its
nested Qt callback. It does not modify Qt or the five source methods.
"""
from pathlib import Path
import argparse
import subprocess
import sys

PARENT_CASE = r"""
static int qt665_parent_probe() {
  auto *window = new WbMainWindow;
  window->createWorldLoadingProgressDialog();
  QPointer<QProgressDialog> old = window->current();
  if (!old) return 31;
  old->show();
  old->setModal(true);
  old->setRange(0, 100);
  old->setValue(12);
  if (!QMetaObject::invokeMethod(old.data(), "forceShow", Qt::DirectConnection))
    return 32;
  QApplication::processEvents();
  QPointer<QProgressBar> bar = old->findChild<QProgressBar *>();
  if (!bar) return 33;
  void *dialogId = old.data(), *barId = bar.data();
  QObject::connect(bar.data(), &QObject::destroyed, QApplication::instance(),
     [=]() { qt665_marker(33, dialogId, barId); });
  qt665_marker(30, dialogId, barId);
  QTimer::singleShot(0, QApplication::instance(),
    [window, dialogId, barId]() {
      qt665_marker(31, dialogId, barId);
      delete window;  // adversarial synchronous parent deletion
      qt665_marker(32, dialogId, barId);
    });
  window->setWorldLoadingProgress(51);
  qt665_marker(34, dialogId, barId);
  return 0;
}
"""

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--patched-cpp", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    script = Path(__file__).with_name("qt665_causal_discriminator.py")
    subprocess.run([sys.executable, str(script), "--patched-cpp",
                    str(args.patched_cpp), "--output", str(args.output)], check=True)
    content = args.output.read_text()
    marker = "int main(int argc, char **argv) {"
    assert content.count(marker) == 1
    content = content.replace(marker, PARENT_CASE + "\n" + marker, 1)
    startup = "  QApplication application(argc, argv);"
    assert content.count(startup) == 1
    content = content.replace(startup, startup +
      '\n  if (qEnvironmentVariableIntValue("QT665_PARENT_PROBE") == 1)'
      '\n    return qt665_parent_probe();', 1)
    args.output.write_text(content)

if __name__ == "__main__":
    main()
