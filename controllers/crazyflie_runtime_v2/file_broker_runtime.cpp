#undef wb_robot_wwi_receive_text

#include <webots/robot.h>

#include <QtCore/QByteArray>
#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtCore/QHash>
#include <QtCore/QRandomGenerator>
#include <QtCore/QSaveFile>
#include <QtCore/QString>
#include <QtCore/QStringList>
#include <QtWidgets/QApplication>
#include <QtWidgets/QFileDialog>

#include <cctype>
#include <cstring>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

constexpr const char *kPrefix = "WEBEEBLOCKS_FILE_BROKER_V1";
constexpr qint64 kMaximumProjectBytes = 4 * 1024 * 1024;

std::string encodeBase64Url(const QByteArray &bytes) {
  const QByteArray encoded = bytes.toBase64(QByteArray::Base64UrlEncoding | QByteArray::OmitTrailingEquals);
  return std::string(encoded.constData(), static_cast<size_t>(encoded.size()));
}

bool decodeBase64Url(const std::string &value, QByteArray *bytes) {
  if (!bytes || value.size() % 4 == 1)
    return false;
  for (const unsigned char c : value) {
    if (!(std::isalnum(c) || c == '-' || c == '_'))
      return false;
  }
  QByteArray encoded(value.data(), static_cast<int>(value.size()));
  while (encoded.size() % 4)
    encoded.append('=');
  *bytes = QByteArray::fromBase64(encoded, QByteArray::Base64UrlEncoding);
  return true;
}

bool validToken(const std::string &token) {
  if (token.empty() || token.size() > 128)
    return false;
  for (const unsigned char c : token) {
    if (!(std::isalnum(c) || c == '-' || c == '_'))
      return false;
  }
  return true;
}

std::string responsePrefix(long long id) {
  return std::string(kPrefix) + " RESPONSE " + std::to_string(id) + " ";
}

class NativeFileBroker {
public:
  NativeFileBroker() {
    QCoreApplication *existing = QCoreApplication::instance();
    if (existing) {
      if (!qobject_cast<QApplication *>(existing))
        throw std::runtime_error("non-GUI Qt application already exists");
      return;
    }
    std::memset(arg0_, 0, sizeof(arg0_));
    std::strncpy(arg0_, "webeeblocks-file-broker", sizeof(arg0_) - 1);
    argv_[0] = arg0_;
    argv_[1] = nullptr;
    application_ = std::make_unique<QApplication>(argc_, argv_);
  }

  std::string handle(const char *message) {
    std::istringstream input(message ? message : "");
    std::string prefix;
    std::string request;
    std::string operation;
    long long id = 0;
    if (!(input >> prefix >> request >> id >> operation) || prefix != kPrefix || request != "REQUEST" || id < 1)
      return std::string();

    const std::string head = responsePrefix(id);
    if (operation == "CAPABILITIES") {
      std::string extra;
      if (input >> extra)
        return head + "ERR INVALID_REQUEST";
      return head + "CAPABILITIES {\"protocol\":1,\"provider\":\"qt6-qfiledialog\",\"operationsReady\":true,\"canonicalExtension\":\".wbb\",\"opaqueSessionRefs\":true,\"sameFileSave\":true}";
    }
    if (operation == "OPEN") {
      std::string extra;
      if (input >> extra)
        return head + "ERR INVALID_REQUEST";
      return open(head);
    }
    if (operation == "SAVE_AS") {
      std::string encodedName;
      std::string encodedBytes;
      std::string extra;
      if (!(input >> encodedName >> encodedBytes) || (input >> extra))
        return head + "ERR INVALID_REQUEST";
      return saveAs(head, encodedName, encodedBytes);
    }
    if (operation == "SAVE") {
      std::string token;
      std::string encodedBytes;
      std::string extra;
      if (!(input >> token >> encodedBytes) || (input >> extra) || !validToken(token))
        return head + "ERR INVALID_REQUEST";
      return save(head, token, encodedBytes);
    }
    return head + "ERR UNSUPPORTED_OPERATION";
  }

private:
  std::string newToken() {
    for (;;) {
      const quint64 high = QRandomGenerator::global()->generate64();
      const quint64 low = QRandomGenerator::global()->generate64();
      const QString token = QString::number(high, 16).rightJustified(16, QLatin1Char('0')) +
                            QString::number(low, 16).rightJustified(16, QLatin1Char('0'));
      if (!targets_.contains(token))
        return token.toStdString();
    }
  }

  std::string open(const std::string &head) {
    QFileDialog dialog;
    dialog.setWindowTitle(QStringLiteral("Ouvrir un projet WebeeBlocks"));
    dialog.setAcceptMode(QFileDialog::AcceptOpen);
    dialog.setFileMode(QFileDialog::ExistingFile);
    dialog.setNameFilters(QStringList{QStringLiteral("Projet WebeeBlocks (*.wbb *.json)"),
                                      QStringLiteral("Tous les fichiers (*)")});
    if (dialog.exec() != QDialog::Accepted)
      return head + "CANCEL";
    const QStringList selected = dialog.selectedFiles();
    if (selected.size() != 1)
      return head + "ERR INVALID_SELECTION";
    const QString path = selected.front();
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
      return head + "ERR READ_FAILED";
    if (file.size() < 0 || file.size() > kMaximumProjectBytes)
      return head + "ERR FILE_TOO_LARGE";
    const QByteArray bytes = file.readAll();
    if (bytes.size() != file.size())
      return head + "ERR READ_FAILED";

    const std::string token = newToken();
    targets_.insert(QString::fromStdString(token), path);
    const QByteArray name = QFileInfo(path).fileName().toUtf8();
    return head + "OPEN OK " + token + " " + encodeBase64Url(name) + " " + encodeBase64Url(bytes);
  }

  std::string saveAs(const std::string &head, const std::string &encodedName, const std::string &encodedBytes) {
    QByteArray nameBytes;
    QByteArray bytes;
    if (!decodeBase64Url(encodedName, &nameBytes) || !decodeBase64Url(encodedBytes, &bytes))
      return head + "ERR INVALID_ENCODING";
    if (bytes.size() > kMaximumProjectBytes)
      return head + "ERR FILE_TOO_LARGE";

    QString suggested = QFileInfo(QString::fromUtf8(nameBytes)).fileName();
    if (suggested.isEmpty())
      suggested = QStringLiteral("projet.wbb");
    if (!suggested.endsWith(QStringLiteral(".wbb"), Qt::CaseInsensitive))
      suggested += QStringLiteral(".wbb");

    QFileDialog dialog;
    dialog.setWindowTitle(QStringLiteral("Enregistrer le projet WebeeBlocks"));
    dialog.setAcceptMode(QFileDialog::AcceptSave);
    dialog.setFileMode(QFileDialog::AnyFile);
    dialog.setNameFilter(QStringLiteral("Projet WebeeBlocks (*.wbb)"));
    dialog.setDefaultSuffix(QStringLiteral("wbb"));
    dialog.selectFile(suggested);
    if (dialog.exec() != QDialog::Accepted)
      return head + "CANCEL";
    const QStringList selected = dialog.selectedFiles();
    if (selected.size() != 1)
      return head + "ERR INVALID_SELECTION";
    QString path = selected.front();
    if (!path.endsWith(QStringLiteral(".wbb"), Qt::CaseInsensitive))
      path += QStringLiteral(".wbb");
    if (!writeExact(path, bytes))
      return head + "ERR WRITE_FAILED";

    const std::string token = newToken();
    targets_.insert(QString::fromStdString(token), path);
    const QByteArray name = QFileInfo(path).fileName().toUtf8();
    return head + "SAVE_AS OK " + token + " " + encodeBase64Url(name);
  }

  std::string save(const std::string &head, const std::string &token, const std::string &encodedBytes) {
    const QString key = QString::fromStdString(token);
    if (!targets_.contains(key))
      return head + "ERR UNKNOWN_TARGET";
    QByteArray bytes;
    if (!decodeBase64Url(encodedBytes, &bytes))
      return head + "ERR INVALID_ENCODING";
    if (bytes.size() > kMaximumProjectBytes)
      return head + "ERR FILE_TOO_LARGE";
    const QString path = targets_.value(key);
    if (!writeExact(path, bytes))
      return head + "ERR WRITE_FAILED";
    const QByteArray name = QFileInfo(path).fileName().toUtf8();
    return head + "SAVE OK " + token + " " + encodeBase64Url(name);
  }

  bool writeExact(const QString &path, const QByteArray &bytes) {
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly))
      return false;
    if (file.write(bytes) != bytes.size()) {
      file.cancelWriting();
      return false;
    }
    return file.commit();
  }

  int argc_ = 1;
  char arg0_[32] = {};
  char *argv_[2] = {nullptr, nullptr};
  std::unique_ptr<QApplication> application_;
  QHash<QString, QString> targets_;
};

NativeFileBroker &broker() {
  static NativeFileBroker *instance = new NativeFileBroker();
  return *instance;
}

long long requestId(const char *message) {
  std::istringstream input(message ? message : "");
  std::string prefix;
  std::string request;
  long long id = 0;
  if (input >> prefix >> request >> id && prefix == kPrefix && request == "REQUEST" && id >= 1)
    return id;
  return 0;
}

bool isBrokerMessage(const char *message) {
  if (!message)
    return false;
  const size_t length = std::strlen(kPrefix);
  return std::strncmp(message, kPrefix, length) == 0 && message[length] == ' ';
}

}  // namespace

extern "C" const char *webeeblocks_file_broker_receive_text(void) {
  for (;;) {
    const char *message = wb_robot_wwi_receive_text();
    if (!message)
      return nullptr;
    if (!isBrokerMessage(message))
      return message;

    std::string response;
    try {
      response = broker().handle(message);
    } catch (const std::exception &) {
      const long long id = requestId(message);
      if (id >= 1)
        response = responsePrefix(id) + "ERR PROVIDER_UNAVAILABLE";
    }
    if (!response.empty())
      wb_robot_wwi_send_text(response.c_str());
  }
}
