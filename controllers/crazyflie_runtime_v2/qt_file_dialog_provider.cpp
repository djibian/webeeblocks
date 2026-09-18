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
#include <shobjidl.h>
#else
#include <QtWidgets/QFileDialog>
#endif
#include <QtWidgets/QApplication>

#include <array>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

namespace {
#ifdef Q_OS_WIN
constexpr HRESULT kDialogCancelled = HRESULT_FROM_WIN32(ERROR_CANCELLED);

struct ComRelease {
  template <typename T>
  void operator()(T *value) const {
    if (value)
      value->Release();
  }
};

template <typename T>
using ComPtr = std::unique_ptr<T, ComRelease>;

class ComApartmentGuard final {
public:
  ComApartmentGuard() : mResult(CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED)) {}
  ~ComApartmentGuard() {
    if (mResult == S_OK || mResult == S_FALSE)
      CoUninitialize();
  }

  bool ready() const { return mResult == S_OK || mResult == S_FALSE; }

private:
  HRESULT mResult = E_FAIL;
};

HWND externalForegroundOwner() {
  const HWND owner = GetForegroundWindow();
  if (!owner || !IsWindow(owner))
    return nullptr;
  DWORD ownerProcessId = 0;
  if (GetWindowThreadProcessId(owner, &ownerProcessId) == 0 || ownerProcessId == 0 ||
      ownerProcessId == GetCurrentProcessId())
    return nullptr;
  return owner;
}

thread_local HWND gNativeDialogExpectedOwner = nullptr;
thread_local bool gNativeDialogPresentationActive = false;
thread_local bool gNativeDialogPresentationApplied = false;

LRESULT CALLBACK nativeDialogPresentationHook(int code, WPARAM wParam, LPARAM lParam) {
  if (code == HCBT_ACTIVATE && gNativeDialogPresentationActive &&
      !gNativeDialogPresentationApplied && wParam != 0 && gNativeDialogExpectedOwner) {
    const HWND window = reinterpret_cast<HWND>(wParam);
    DWORD processId = 0;
    const DWORD windowThreadId = GetWindowThreadProcessId(window, &processId);
    wchar_t className[32] = {};
    const HWND foreground = GetForegroundWindow();
    if (windowThreadId == GetCurrentThreadId() && processId == GetCurrentProcessId() &&
        GetClassNameW(window, className, 32) > 0 && lstrcmpW(className, L"#32770") == 0 &&
        GetWindow(window, GW_OWNER) == gNativeDialogExpectedOwner &&
        (foreground == gNativeDialogExpectedOwner || foreground == window)) {
      // This hook runs on the exact thread that executes IFileDialog::Show().
      // Its input queue is temporarily joined to the still-foreground external
      // owner, so normal foreground activation is permitted without TOPMOST.
      const BOOL raised = SetWindowPos(window, HWND_TOP, 0, 0, 0, 0,
                                       SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW |
                                           SWP_NOACTIVATE | SWP_NOOWNERZORDER);
      const BOOL foregrounded = SetForegroundWindow(window);
      gNativeDialogPresentationApplied = raised && foregrounded;
      if (!gNativeDialogPresentationApplied) {
        std::fprintf(stderr,
                     "WEBEEBLOCKS_FILE_DIALOG_FOREGROUND activation_failed\n");
      }
    }
  }
  return CallNextHookEx(nullptr, code, wParam, lParam);
}

class NativeDialogPresentationGuard final {
public:
  explicit NativeDialogPresentationGuard(HWND owner) : mOwner(owner) {
    if (!mOwner)
      return;
    DWORD ownerProcessId = 0;
    mOwnerThreadId = GetWindowThreadProcessId(mOwner, &ownerProcessId);
    mDialogThreadId = GetCurrentThreadId();
    if (mOwnerThreadId == 0 || ownerProcessId == 0 || ownerProcessId == GetCurrentProcessId() ||
        GetForegroundWindow() != mOwner)
      return;

    if (mDialogThreadId != mOwnerThreadId) {
      SetLastError(ERROR_SUCCESS);
      if (!AttachThreadInput(mDialogThreadId, mOwnerThreadId, TRUE)) {
        std::fprintf(stderr,
                     "WEBEEBLOCKS_FILE_DIALOG_FOREGROUND attach_thread_input_failed=%lu\n",
                     static_cast<unsigned long>(GetLastError()));
        return;
      }
      mInputAttached = true;
    }

    if (gNativeDialogPresentationActive) {
      std::fprintf(stderr,
                   "WEBEEBLOCKS_FILE_DIALOG_FOREGROUND nested_presentation_guard\n");
      detachInput();
      return;
    }

    gNativeDialogExpectedOwner = mOwner;
    gNativeDialogPresentationApplied = false;
    gNativeDialogPresentationActive = true;
    mOwnsState = true;
    mHook = SetWindowsHookExW(WH_CBT, nativeDialogPresentationHook, nullptr, mDialogThreadId);
    if (!mHook) {
      std::fprintf(stderr,
                   "WEBEEBLOCKS_FILE_DIALOG_FOREGROUND cbt_hook_install_failed=%lu\n",
                   static_cast<unsigned long>(GetLastError()));
      resetState();
      detachInput();
    }
  }

  ~NativeDialogPresentationGuard() {
    if (mHook)
      (void)UnhookWindowsHookEx(mHook);
    if (mOwnsState && !gNativeDialogPresentationApplied) {
      std::fprintf(stderr,
                   "WEBEEBLOCKS_FILE_DIALOG_FOREGROUND native_picker_not_activated\n");
    }
    if (mOwnsState)
      resetState();
    detachInput();
  }

  NativeDialogPresentationGuard(const NativeDialogPresentationGuard &) = delete;
  NativeDialogPresentationGuard &operator=(const NativeDialogPresentationGuard &) = delete;

private:
  void detachInput() {
    if (!mInputAttached)
      return;
    if (!AttachThreadInput(mDialogThreadId, mOwnerThreadId, FALSE)) {
      std::fprintf(stderr,
                   "WEBEEBLOCKS_FILE_DIALOG_FOREGROUND detach_thread_input_failed=%lu\n",
                   static_cast<unsigned long>(GetLastError()));
    }
    mInputAttached = false;
  }

  void resetState() {
    gNativeDialogExpectedOwner = nullptr;
    gNativeDialogPresentationApplied = false;
    gNativeDialogPresentationActive = false;
    mOwnsState = false;
  }

  HWND mOwner = nullptr;
  DWORD mOwnerThreadId = 0;
  DWORD mDialogThreadId = 0;
  HHOOK mHook = nullptr;
  bool mInputAttached = false;
  bool mOwnsState = false;
};

struct NativeDialogResult {
  enum class Status { Ok, Cancelled, Error } status = Status::Error;
  QString path;
};

NativeDialogResult resultPath(IFileDialog *dialog) {
  IShellItem *rawItem = nullptr;
  if (!dialog || FAILED(dialog->GetResult(&rawItem)) || !rawItem)
    return {};
  ComPtr<IShellItem> item(rawItem);
  PWSTR rawPath = nullptr;
  if (FAILED(item->GetDisplayName(SIGDN_FILESYSPATH, &rawPath)) || !rawPath)
    return {};
  const QString path = QString::fromWCharArray(rawPath);
  CoTaskMemFree(rawPath);
  if (path.isEmpty())
    return {};
  return {NativeDialogResult::Status::Ok, path};
}

NativeDialogResult showNativeOpenDialog() {
  ComApartmentGuard apartment;
  if (!apartment.ready())
    return {};

  IFileOpenDialog *rawDialog = nullptr;
  if (FAILED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER,
                              IID_IFileOpenDialog, reinterpret_cast<void **>(&rawDialog))) ||
      !rawDialog)
    return {};
  ComPtr<IFileOpenDialog> dialog(rawDialog);

  FILEOPENDIALOGOPTIONS options = 0;
  if (FAILED(dialog->GetOptions(&options)) ||
      FAILED(dialog->SetOptions(options | FOS_FORCEFILESYSTEM | FOS_FILEMUSTEXIST |
                                FOS_PATHMUSTEXIST | FOS_NOCHANGEDIR)))
    return {};
  const COMDLG_FILTERSPEC filter = {L"Projet WebeeBlocks", L"*.wbb;*.json"};
  if (FAILED(dialog->SetFileTypes(1, &filter)) ||
      FAILED(dialog->SetTitle(L"Ouvrir un projet WebeeBlocks")))
    return {};

  const HWND owner = externalForegroundOwner();
  NativeDialogPresentationGuard presentation(owner);
  const HRESULT shown = dialog->Show(owner);
  if (shown == kDialogCancelled)
    return {NativeDialogResult::Status::Cancelled, {}};
  if (FAILED(shown))
    return {};
  return resultPath(dialog.get());
}

NativeDialogResult showNativeSaveDialog(const std::string &suggestedName) {
  ComApartmentGuard apartment;
  if (!apartment.ready())
    return {};

  IFileSaveDialog *rawDialog = nullptr;
  if (FAILED(CoCreateInstance(CLSID_FileSaveDialog, nullptr, CLSCTX_INPROC_SERVER,
                              IID_IFileSaveDialog, reinterpret_cast<void **>(&rawDialog))) ||
      !rawDialog)
    return {};
  ComPtr<IFileSaveDialog> dialog(rawDialog);

  FILEOPENDIALOGOPTIONS options = 0;
  if (FAILED(dialog->GetOptions(&options)) ||
      FAILED(dialog->SetOptions(options | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST |
                                FOS_OVERWRITEPROMPT | FOS_NOCHANGEDIR)))
    return {};
  const COMDLG_FILTERSPEC filter = {L"Projet WebeeBlocks", L"*.wbb"};
  const std::wstring suggested =
      QString::fromUtf8(suggestedName.data(), static_cast<int>(suggestedName.size())).toStdWString();
  if (FAILED(dialog->SetFileTypes(1, &filter)) ||
      FAILED(dialog->SetDefaultExtension(L"wbb")) ||
      FAILED(dialog->SetFileName(suggested.c_str())) ||
      FAILED(dialog->SetTitle(L"Enregistrer le projet WebeeBlocks")))
    return {};

  const HWND owner = externalForegroundOwner();
  NativeDialogPresentationGuard presentation(owner);
  const HRESULT shown = dialog->Show(owner);
  if (shown == kDialogCancelled)
    return {NativeDialogResult::Status::Cancelled, {}};
  if (FAILED(shown))
    return {};
  return resultPath(dialog.get());
}
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
#ifdef Q_OS_WIN
    const NativeDialogResult native = showNativeOpenDialog();
    if (native.status == NativeDialogResult::Status::Cancelled)
      return {webeeblocks::FileOperationStatus::Cancelled, "", "", "", ""};
    if (native.status != NativeDialogResult::Status::Ok)
      return openError("DIALOG_FAILED");
    const QString selectedPath = native.path;
#else
    QFileDialog dialog;
    dialog.setWindowTitle(QStringLiteral("Ouvrir un projet WebeeBlocks"));
    dialog.setFileMode(QFileDialog::ExistingFile);
    dialog.setAcceptMode(QFileDialog::AcceptOpen);
    dialog.setNameFilter(QStringLiteral("Projet WebeeBlocks (*.wbb *.json)"));
    if (dialog.exec() != QDialog::Accepted)
      return {webeeblocks::FileOperationStatus::Cancelled, "", "", "", ""};
    const QStringList selected = dialog.selectedFiles();
    if (selected.size() != 1)
      return openError("INVALID_SELECTION");
    const QString selectedPath = selected.front();
#endif
    const QFileInfo info(selectedPath);
    const QString lowerName = info.fileName().toLower();
    if (!info.exists() || !info.isFile() ||
        (!lowerName.endsWith(QStringLiteral(".wbb")) &&
         !lowerName.endsWith(QStringLiteral(".json"))))
      return openError("INVALID_SELECTION");
    if (info.size() < 0 ||
        static_cast<qulonglong>(info.size()) > webeeblocks::FileBroker::kMaxProjectBytes)
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
    return {webeeblocks::FileOperationStatus::Ok, reference,
            info.fileName().toUtf8().toStdString(),
            std::string(bytes.constData(), static_cast<std::size_t>(bytes.size())), ""};
  }

  webeeblocks::SaveFileResult saveAs(const std::string &suggestedName,
                                      const std::string &bytes) override {
    if (!canAllocateReference())
      return saveError("REFERENCE_LIMIT");
#ifdef Q_OS_WIN
    const NativeDialogResult native = showNativeSaveDialog(suggestedName);
    if (native.status == NativeDialogResult::Status::Cancelled)
      return {webeeblocks::FileOperationStatus::Cancelled, "", "", ""};
    if (native.status != NativeDialogResult::Status::Ok)
      return saveError("DIALOG_FAILED");
    const QString selectedPath = native.path;
#else
    QFileDialog dialog;
    dialog.setWindowTitle(QStringLiteral("Enregistrer le projet WebeeBlocks"));
    dialog.setAcceptMode(QFileDialog::AcceptSave);
    dialog.setFileMode(QFileDialog::AnyFile);
    dialog.setDefaultSuffix(QStringLiteral("wbb"));
    dialog.setNameFilter(QStringLiteral("Projet WebeeBlocks (*.wbb)"));
    dialog.selectFile(
        QString::fromUtf8(suggestedName.data(), static_cast<int>(suggestedName.size())));
    if (dialog.exec() != QDialog::Accepted)
      return {webeeblocks::FileOperationStatus::Cancelled, "", "", ""};
    const QStringList selected = dialog.selectedFiles();
    if (selected.size() != 1)
      return saveError("INVALID_SELECTION");
    const QString selectedPath = selected.front();
#endif
    const QString path = QFileInfo(selectedPath).absoluteFilePath();
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
    return {webeeblocks::FileOperationStatus::Ok, reference,
            written.fileName().toUtf8().toStdString(), ""};
  }

  webeeblocks::SaveFileResult save(const std::string &reference,
                                    const std::string &bytes) override {
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
    return {webeeblocks::FileOperationStatus::Ok, reference,
            after.fileName().toUtf8().toStdString(), ""};
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
  static std::string writeAtomically(const QString &path, const std::string &bytes,
                                     bool requireExisting) {
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
  explicit WbFileBroker(std::unique_ptr<webeeblocks::FileDialogProvider> provider)
      : broker(std::move(provider)) {}
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

extern "C" const char *wb_file_broker_handle_message(WbFileBroker *broker,
                                                       const char *message) {
  if (!broker)
    return nullptr;
  broker->response.clear();
  if (!broker->broker.handleMessage(message, &broker->response))
    return nullptr;
  return broker->response.empty() ? nullptr : broker->response.c_str();
}
