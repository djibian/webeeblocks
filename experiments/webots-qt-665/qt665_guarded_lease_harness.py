#!/usr/bin/env python3
"""Method-identical harness of the experimental parent-shutdown guarded patch.

The five method bodies, detached lease and destructor come from the already
patched upstream C++ file. Only unrelated GUI fields are minimal stubs.
"""
import argparse
from pathlib import Path
import subprocess
import sys

def once(text, old, new, label):
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {text.count(old)}")
    return text.replace(old, new, 1)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--patched-cpp", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    script = Path(__file__).with_name("qt_guarded_method_harness.py")
    subprocess.run([sys.executable, str(script), "--patched-cpp",
                    str(args.patched_cpp), "--output", str(args.output)], check=True)
    data = args.output.read_text()
    original = args.patched_cpp.read_text()
    a = original.index("// Shared by active operations, even if the owning main window is destroyed.")
    b = original.index("WbMainWindow::WbMainWindow(", a)
    lease_source = original[a:b]
    a = original.index("WbMainWindow::~WbMainWindow() {")
    b = original.index("void WbMainWindow::lockFullScreen", a)
    destructor_source = original[a:b]
    data = once(data, "#include <functional>",
                "#include <functional>\n#include <memory>", "memory")
    data = once(data, "class WbMainWindow : public QMainWindow {",
                lease_source + "\nclass WbMainWindow : public QMainWindow {", "lease class")
    data = once(data,
                "WbMainWindow() : mWorldLoadingProgressDialog(nullptr), mWorldLoadingProgressOperationDepth(0) {}",
                "WbMainWindow() : mWorldLoadingProgressDialog(nullptr), mWorldLoadingProgressOperationDepth(0),\n"
                "    mWorldLoadingProgressLease(std::make_shared<WbWorldLoadingProgressLease>()) {}\n"
                "  ~WbMainWindow();", "constructor and destructor")
    data = once(data, "  QList<QProgressDialog *> mRetiredWorldLoadingProgressDialogs;",
                "  QList<QProgressDialog *> mRetiredWorldLoadingProgressDialogs;\n"
                "  std::shared_ptr<WbWorldLoadingProgressLease> mWorldLoadingProgressLease;\n"
                "  QByteArray *mFactoryLayout = nullptr;", "mock state fields")
    data = once(data,
                "void WbMainWindow::runWorldLoadingProgressOperation(",
                destructor_source + "\nvoid WbMainWindow::runWorldLoadingProgressOperation(",
                "actual patched destructor")
    args.output.write_text(data)

if __name__ == "__main__":
    main()
