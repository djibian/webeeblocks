#!/usr/bin/env python3
"""Fail-closed experimental R2025a shutdown fix layered after #701 source patch.

Temporary evidence transformation. The unchanged original #701 patch remains
the baseline; never mistake the old ELF SHA for a build of this new variant.
"""
import argparse
from pathlib import Path

def once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {n}")
    return text.replace(old, new, 1)

def transform_header(text):
    text = once(text, "#include <functional>",
                "#include <functional>\n#include <memory>", "memory include")
    text = once(text, "class WbBuildEditor;",
                "struct WbWorldLoadingProgressLease;\n\nclass WbBuildEditor;", "lease forward")
    text = once(text, "  QList<QProgressDialog *> mRetiredWorldLoadingProgressDialogs;",
                "  QList<QProgressDialog *> mRetiredWorldLoadingProgressDialogs;\n"
                "  std::shared_ptr<WbWorldLoadingProgressLease> mWorldLoadingProgressLease;", "lease member")
    return text

LEASE = """// Shared by active operations, even if the owning main window is destroyed.
// Its last owner schedules deletion ONLY after all protected Qt calls return.
struct WbWorldLoadingProgressLease {
  QList<QPointer<QObject>> orphaned;
  ~WbWorldLoadingProgressLease() {
    for (const QPointer<QObject> &dialog : orphaned) {
      if (dialog)
        dialog->deleteLater();
    }
  }
};

"""

DESTRUCTOR = """WbMainWindow::~WbMainWindow() {
  // QObject parent destruction otherwise deletes an active progress bar in
  // the middle of the nested QProgressDialog::setValue() event dispatch.
  if (mWorldLoadingProgressOperationDepth > 0) {
    QList<QProgressDialog *> dialogs = mRetiredWorldLoadingProgressDialogs;
    if (mWorldLoadingProgressDialog)
      dialogs.append(mWorldLoadingProgressDialog);
    mWorldLoadingProgressDialog = nullptr;
    mRetiredWorldLoadingProgressDialogs.clear();
    for (QProgressDialog *dialog : dialogs) {
      // Detach before QObject::~QObject deletes this window\x27s children.
      dialog->disconnect();
      dialog->setParent(nullptr);
      mWorldLoadingProgressLease->orphaned.append(QPointer<QObject>(dialog));
    }
  }
  delete mFactoryLayout;
}
"""

def transform_cpp(text):
    text = once(text, "WbMainWindow::WbMainWindow(bool minimizedOnStart, WbTcpServer *tcpServer, QWidget *parent) :",
                LEASE + "WbMainWindow::WbMainWindow(bool minimizedOnStart, WbTcpServer *tcpServer, QWidget *parent) :",
                "lifetime state definition")
    text = once(text, "  mWorldLoadingProgressOperationDepth(0),",
                "  mWorldLoadingProgressOperationDepth(0),\n"
                "  mWorldLoadingProgressLease(std::make_shared<WbWorldLoadingProgressLease>()),",
                "lease initialization")
    text = once(text, "WbMainWindow::~WbMainWindow() {\n  delete mFactoryLayout;\n}",
                DESTRUCTOR.rstrip(), "parent destructor")
    text = once(text,
                "void WbMainWindow::runWorldLoadingProgressOperation(const std::function<void()> &operation) {\n"
                "  ++mWorldLoadingProgressOperationDepth;",
                "void WbMainWindow::runWorldLoadingProgressOperation(const std::function<void()> &operation) {\n"
                "  // A heap lease outlives this QObject if a nested callback deletes it.\n"
                "  const std::shared_ptr<WbWorldLoadingProgressLease> lease = mWorldLoadingProgressLease;\n"
                "  ++mWorldLoadingProgressOperationDepth;", "operation state capture")
    start = text.index("void WbMainWindow::createWorldLoadingProgressDialog() {")
    end = text.index("void WbMainWindow::deleteWorldLoadingProgressDialog() {", start)
    create = text[start:end]
    create = once(create, "runWorldLoadingProgressOperation([this, dialog, cancelButton]() {",
                  "runWorldLoadingProgressOperation([window = QPointer<WbMainWindow>(this), dialog, cancelButton]() {",
                  "create weak window")
    for literal in ("Cancel", "Loading world", "Opening world file"):
        create = once(create, f"tr(\"{literal}\")", f"WbMainWindow::tr(\"{literal}\")",
                      "create static translation " + literal)
    original = "if (mWorldLoadingProgressDialog != dialog)"
    expected = create.count(original)
    if expected != 4:
        raise RuntimeError(f"creation dialog guards: expected 4, found {expected}")
    create = create.replace(original, "if (!window || window->mWorldLoadingProgressDialog != dialog)")
    create = once(create, "if (mWorldLoadingProgressDialog == dialog)",
                  "if (window && window->mWorldLoadingProgressDialog == dialog)",
                  "create final guard")
    text = text[:start] + create + text[end:]
    text = once(text, "runWorldLoadingProgressOperation([this, dialog, progress]() {",
                "runWorldLoadingProgressOperation([window = QPointer<WbMainWindow>(this), dialog, progress]() {",
                "progress weak window")
    text = once(text, "runWorldLoadingProgressOperation([this, dialog, status]() {",
                "runWorldLoadingProgressOperation([window = QPointer<WbMainWindow>(this), dialog, status]() {",
                "status weak window")
    for meth in ("setWorldLoadingProgress", "setWorldLoadingStatus"):
        start = text.index(f"void WbMainWindow::{meth}(")
        end = text.index("\n}", start) + 2
        before = text[start:end]
        after = once(before, "if (mWorldLoadingProgressDialog == dialog)",
                     "if (window && window->mWorldLoadingProgressDialog == dialog)",
                     meth + " post-reentrance weak window")
        text = text[:start] + after + text[end:]
    return text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots-tree", type=Path, required=True)
    args = parser.parse_args()
    tree = args.webots_tree
    hpp = tree / "src/webots/gui/WbMainWindow.hpp"
    cpp = tree / "src/webots/gui/WbMainWindow.cpp"
    header, code = hpp.read_text(), cpp.read_text()
    revised_hpp, revised_cpp = transform_header(header), transform_cpp(code)
    hpp.write_text(revised_hpp)
    cpp.write_text(revised_cpp)
    print("QT665_PARENT_SHUTDOWN_LEASE_SOURCE_TRANSFORMATION=APPLIED")

if __name__ == "__main__":
    main()
