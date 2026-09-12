#include "file_broker.hpp"
#include "file_broker_c.h"

#include <QtCore/QCoreApplication>
#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtCore/QHash>
#include <QtCore/QSaveFile>
#include <QtCore/QString>
#include <QtCore/QUuid>
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
class QtFileDialogProvider final : public webeeblocks::FileDialogProvider {
public:
  QtFileDialogProvider() {
    std::strcpy(mProgramName.data(), "webeeblocks-file-broker");
    mArgv[0] = mProgramName.data();
    mArgv[1] = nullptr;
    if (!QCoreApplication::instance()) {
      const QString webotsHome = qEnvironmentVariable("WEBOTS_HOME");
      if (webotsHome.isEmpty())
        throw std::runtime_error("WEBOTS_HOME is unavailable for the Qt file broker");
      const QString pluginPath = QDir(webotsHome).filePath(QStringLiteral("lib/webots/qt/plugins"));
      if (!QDir(pluginPath).exists())
        throw std::runtime_error("Webots Qt plugin directory is unavailable");
      QApplication::addLibraryPath(pluginPath);
      mApplication = std::make_unique<QApplication>(mArgc, mArgv.data());
    }
    if (!qobject_cast<QApplication *>(QCoreApplication::instance()))
      throw std::runtime_error("Qt application is not a QApplication");
  }

  std::string name() const override { return "qt6-native-dialog"; }

  webeeblocks::OpenFileResult open() override {
    if (!canAllocateReference())
      return openError("REFERENCE_LIMIT");
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
    QFileDialog dialog;
    dialog.setWindowTitle(QStringLiteral("Enregistrer le projet WebeeBlocks"));
    dialog.setAcceptMode(QFileDialog::AcceptSave);
    dialog.setFileMode(QFileDialog::AnyFile);
    dialog.setDefaultSuffix(QStringLiteral("wbb"));
    dialog.setNameFilter(QStringLiteral("Projet WebeeBlocks (*.wbb)"));
    dialog.selectFile(QString::fromUtf8(suggestedName.data(), static_cast<int>(suggestedName.size())));
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
