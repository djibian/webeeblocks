#include "file_broker.hpp"
#include "file_broker_c.h"

#include <QtCore/QCoreApplication>
#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtCore/QHash>
#include <QtCore/QSaveFile>
#include <QtCore/QString>
#include <QtCore/QUuid>
#ifdef Q_OS_WIN
#include <QtCore/qt_windows.h>
#endif
#include <QtGui/QWindow>
#include <QtWidgets/QApplication>
#include <QtWidgets/QFileDialog>

#include <array>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

namespace {
std::unique_ptr<QWindow> bindDialogToForegroundOwner(QFileDialog &dialog) {
#ifdef Q_OS_WIN
  // Qt 6.5's Windows native QFileDialog helper ignores QWidget window flags;
  // IFileDialog receives only the transient parent's HWND. Capture the external
  // foreground window that initiated the broker request and bind it explicitly
  // so the native picker has a real owner in the calling desktop application.
  const HWND owner = GetForegroundWindow();
  if (!owner)
    return {};
  DWORD ownerProcessId = 0;
  if (GetWindowThreadProcessId(owner, &ownerProcessId) == 0 || ownerProcessId == 0 ||
      ownerProcessId == GetCurrentProcessId())
    return {};

  auto ownerWindow = std::unique_ptr<QWindow>(
      QWindow::fromWinId(static_cast<WId>(reinterpret_cast<quintptr>(owner))));
  if (!ownerWindow)
    return {};

  // QFileDialog is normally represented only by the platform-native picker.
  // Create its QWindow long enough to carry the foreign transient parent into
  // QDialogPrivate::transientParentWindow() -> IFileDialog::Show(owner HWND).
  (void)dialog.winId();
  QWindow *dialogWindow = dialog.windowHandle();
  if (!dialogWindow)
    return {};
  dialogWindow->setTransientParent(ownerWindow.get());
  return ownerWindow;
#else
  (void)dialog;
  return {};
#endif
}

#ifdef Q_OS_WIN
thread_local bool gNativeDialogPresentationActive = false;
thread_local bool gNativeDialogPresentationApplied = false;

LRESULT CALLBACK nativeDialogPresentationHook(int code, WPARAM wParam, LPARAM lParam) {
  if (code == HCBT_ACTIVATE && gNativeDialogPresentationActive &&
      !gNativeDialogPresentationApplied && wParam != 0) {
    const HWND window = reinterpret_cast<HWND>(wParam);
    DWORD processId = 0;
    wchar_t className[32] = {};
    if (GetWindowThreadProcessId(window, &processId) != 0 && processId == GetCurrentProcessId() &&
        GetClassNameW(window, className, 32) > 0 && lstrcmpW(className, L"#32770") == 0) {
      // Ownership alone is not a foreground guarantee on the real Windows 11
      // Firefox path. Qt 6.5.3 synchronously calls IFileDialog::Show() on this
      // thread, so a thread-local CBT hook is the smallest public Win32 boundary
      // that exposes the actual shell-picker HWND before activation completes.
      // Put that exact short-lived modal window at the top of the desktop z-order
      // and allow SetWindowPos to activate it; no browser or non-Windows path is
      // touched, and the topmost state disappears with the picker itself.
      gNativeDialogPresentationApplied = true;  // Prevent hook re-entry from SetWindowPos.
      if (!SetWindowPos(window, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOSENDCHANGING))
        gNativeDialogPresentationApplied = false;
    }
  }
  return CallNextHookEx(nullptr, code, wParam, lParam);
}

class NativeDialogPresentationGuard final {
public:
  NativeDialogPresentationGuard() {
    if (gNativeDialogPresentationActive)
      throw std::runtime_error("nested native dialog presentation guard");
    gNativeDialogPresentationApplied = false;
    gNativeDialogPresentationActive = true;
    mHook = SetWindowsHookExW(WH_CBT, nativeDialogPresentationHook, nullptr, GetCurrentThreadId());
    if (!mHook) {
      gNativeDialogPresentationActive = false;
      throw std::runtime_error("unable to install native dialog presentation hook");
    }
  }

  ~NativeDialogPresentationGuard() {
    if (mHook)
      UnhookWindowsHookEx(mHook);
    if (!gNativeDialogPresentationApplied)
      std::fprintf(stderr, "WEBEEBLOCKS_FILE_BROKER_V1 WARN native dialog HWND was not promoted\n");
    gNativeDialogPresentationActive = false;
  }

  NativeDialogPresentationGuard(const NativeDialogPresentationGuard &) = delete;
  NativeDialogPresentationGuard &operator=(const NativeDialogPresentationGuard &) = delete;

private:
  HHOOK mHook = nullptr;
};
#else
class NativeDialogPresentationGuard final {};
#endif

class QtFileDialogProvider final : public webeeblocks::FileDialogProvider {
public:
  QtFileDialogProvider() {
    std::strcpy(mProgramName.data(), "webeeblocks-file-broker");
    mArgv[0] = mProgramName.data();
    mArgv[1] = nullptr;
    if (!QCoreApplication::instance())
      mApplication = std::make_unique<QApplication>(mArgc, mArgv.data());
    if (!qobject_cast<QApplication *>(QCoreApplication::instance()))
      throw std::runtime_error("Qt application is not a QApplication");
  }

  std::string name() const override { return "qt6-native-dialog"; }

  webeeblocks::OpenFileResult open() override {
    if (!canAllocateReference())
      return openError("REFERENCE_LIMIT");
    // Declared before dialog so the foreign owner outlives the dialog itself.
    [[maybe_unused]] std::unique_ptr<QWindow> presentationOwner;
    QFileDialog dialog;
    dialog.setWindowTitle(QStringLiteral("Ouvrir un projet WebeeBlocks"));
    dialog.setFileMode(QFileDialog::ExistingFile);
    dialog.setAcceptMode(QFileDialog::AcceptOpen);
    dialog.setNameFilter(QStringLiteral("Projet WebeeBlocks (*.wbb *.json)"));
    presentationOwner = bindDialogToForegroundOwner(dialog);
    NativeDialogPresentationGuard presentation;
    if (dialog.exec() != QDialog::Accepted)
      return {webeeblocks::FileOperationStatus::Cancelled, "", "", "", ""};
    const QStringList selected = dialog.selectedFiles();
    if (selected.size() != 1)
      return openError("INVALID_SELECTION");
    const QFileInfo info(selected.front());
    const QString lowerName = info.fileName().toLower();
    if (!info.exists() || !info.isFile() || (!lowerName.endsWith(QStringLiteral(".wbb")) && !lowerName.endsWith(QStringLiteral(".json"))))
      return openError("INVALID_SELECTION");
    if (info.size() < 0 || static_cast<qulonglong>(info.size()) > webeeblocks::FileBroker::kMaxProjectBytes)
      return openError("PROJECT_TOO_LARGE");
    QFile file(info.absoluteFilePath());
    if (!file.open(QIODevice::ReadOnly))
      return openError("READ_FAILED");
    const QByteArray bytes = file.readAll();
    if (static_cast<std::size_t>(bytes.size()) > webeeblocks::FileBroker::kMaxProjectBytes)
      return openError("PROJECT_TOO_LARGE");
    const QString canonical = info.canonicalFilePath();
    if (canonical.isEmpty())
      return openError("TARGET_UNAVAILABLE");
    const std::string reference = allocateReference(canonical);
    return {webeeblocks::FileOperationStatus::Ok, reference, info.fileName().toUtf8().toStdString(),
            std::string(bytes.constData(), static_cast<std::size_t>(bytes.size())), ""};
  }

  webeeblocks::SaveFileResult saveAs(const std::string &suggestedName, const std::string &bytes) override {
    if (!canAllocateReference())
      return saveError("REFERENCE_LIMIT");
    // Declared before dialog so the foreign owner outlives the dialog itself.
    [[maybe_unused]] std::unique_ptr<QWindow> presentationOwner;
    QFileDialog dialog;
    dialog.setWindowTitle(QStringLiteral("Enregistrer le projet WebeeBlocks"));
    dialog.setAcceptMode(QFileDialog::AcceptSave);
    dialog.setFileMode(QFileDialog::AnyFile);
    dialog.setDefaultSuffix(QStringLiteral("wbb"));
    dialog.setNameFilter(QStringLiteral("Projet WebeeBlocks (*.wbb)"));
    dialog.selectFile(QString::fromUtf8(suggestedName.data(), static_cast<int>(suggestedName.size())));
    presentationOwner = bindDialogToForegroundOwner(dialog);
    NativeDialogPresentationGuard presentation;
    if (dialog.exec() != QDialog::Accepted)
      return {webeeblocks::FileOperationStatus::Cancelled, "", "", ""};
    const QStringList selected = dialog.selectedFiles();
    if (selected.size() != 1)
      return saveError("INVALID_SELECTION");
    const QString path = QFileInfo(selected.front()).absoluteFilePath();
    if (!path.toLower().endsWith(QStringLiteral(".wbb")))
      return saveError("INVALID_EXTENSION");
    const std::string writeError = writeAtomically(path, bytes, false);
    if (!writeError.empty())
      return saveError(writeError);
    const QFileInfo written(path);
    const QString canonical = written.canonicalFilePath();
    if (canonical.isEmpty())
      return saveError("TARGET_UNAVAILABLE");
    const std::string reference = allocateReference(canonical);
    return {webeeblocks::FileOperationStatus::Ok, reference, written.fileName().toUtf8().toStdString(), ""};
  }

  webeeblocks::SaveFileResult save(const std::string &reference, const std::string &bytes) override {
    const QString key = QString::fromLatin1(reference.data(), static_cast<int>(reference.size()));
    const auto it = mReferences.constFind(key);
    if (it == mReferences.cend())
      return saveError("TARGET_UNAVAILABLE");
    const QString path = it.value();
    const QFileInfo before(path);
    if (!before.exists() || !before.isFile())
      return saveError("TARGET_UNAVAILABLE");
    const std::string writeError = writeAtomically(path, bytes, true);
    if (!writeError.empty())
      return saveError(writeError);
    const QFileInfo after(path);
    if (!after.exists() || !after.isFile())
      return saveError("TARGET_UNAVAILABLE");
    return {webeeblocks::FileOperationStatus::Ok, reference, after.fileName().toUtf8().toStdString(), ""};
  }

  void release(const std::string &reference) override {
    const QString key = QString::fromLatin1(reference.data(), static_cast<int>(reference.size()));
    mReferences.remove(key);
  }

private:
  static webeeblocks::OpenFileResult openError(const std::string &code) {
    return {webeeblocks::FileOperationStatus::Error, "", "", "", code};
  }
  static webeeblocks::SaveFileResult saveError(const std::string &code) {
    return {webeeblocks::FileOperationStatus::Error, "", "", code};
  }
  bool canAllocateReference() const { return mReferences.size() < 128; }
  std::string allocateReference(const QString &path) {
    QString token;
    do {
      token = QUuid::createUuid().toString(QUuid::WithoutBraces);
      token.remove(QLatin1Char('-'));
    } while (mReferences.contains(token));
    mReferences.insert(token, path);
    return token.toLatin1().toStdString();
  }
  static std::string writeAtomically(const QString &path, const std::string &bytes, bool requireExisting) {
    if (bytes.size() > webeeblocks::FileBroker::kMaxProjectBytes)
      return "PROJECT_TOO_LARGE";
    if (requireExisting) {
      const QFileInfo info(path);
      if (!info.exists() || !info.isFile())
        return "TARGET_UNAVAILABLE";
    }
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly))
      return "WRITE_FAILED";
    const qint64 expected = static_cast<qint64>(bytes.size());
    const qint64 written = file.write(bytes.data(), expected);
    if (written != expected) {
      file.cancelWriting();
      return "WRITE_FAILED";
    }
    if (!file.commit())
      return "WRITE_FAILED";
    return "";
  }

  int mArgc = 1;
  std::array<char, 64> mProgramName{};
  std::array<char *, 2> mArgv{};
  std::unique_ptr<QApplication> mApplication;
  QHash<QString, QString> mReferences;
};
}  // namespace

namespace webeeblocks {
std::unique_ptr<FileDialogProvider> createQtFileDialogProvider() {
  return std::make_unique<QtFileDialogProvider>();
}
}  // namespace webeeblocks

struct WbFileBroker {
  explicit WbFileBroker(std::unique_ptr<webeeblocks::FileDialogProvider> provider) : broker(std::move(provider)) {}
  webeeblocks::FileBroker broker;
  std::string response;
};

extern "C" WbFileBroker *wb_file_broker_create_qt(void) {
  try {
    return new WbFileBroker(webeeblocks::createQtFileDialogProvider());
  } catch (const std::exception &error) {
    std::fprintf(stderr, "WEBEEBLOCKS_FILE_BROKER_V1 FATAL %s\n", error.what());
    return nullptr;
  }
}

extern "C" void wb_file_broker_destroy(WbFileBroker *broker) { delete broker; }

extern "C" const char *wb_file_broker_handle_message(WbFileBroker *broker, const char *message) {
  if (!broker)
    return nullptr;
  broker->response.clear();
  if (!broker->broker.handleMessage(message, &broker->response))
    return nullptr;
  return broker->response.empty() ? nullptr : broker->response.c_str();
}
