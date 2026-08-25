#include "file_broker.hpp"
#include "file_broker_c.h"

#include <QByteArray>
#include <QFileDialog>
#include <QIODevice>
#include <QSaveFile>
#include <QString>

#include <cstdio>
#include <cstring>
#include <memory>
#include <regex>
#include <utility>

namespace {

constexpr const char *kPrefix = "WEBEEBLOCKS_FILE_BROKER_V1";

class QtFileDialogProvider final : public webeeblocks::FileDialogProvider {
public:
  std::string name() const override { return "qt6-qfiledialog"; }

  // These deliberately remain behind the provider seam during 71-C1. Their
  // presence makes the build prove the exact Webots-bundled Qt APIs selected
  // for the next transactional increment without opening a dialog in CI.
  QString selectOpenFile() const {
    return QFileDialog::getOpenFileName(nullptr, QStringLiteral("Ouvrir un projet WebeeBlocks"), QString(),
                                        QStringLiteral("Projets WebeeBlocks (*.wbb *.webeeblocks.json *.json)"));
  }

  bool atomicWrite(const QString &path, const QByteArray &bytes) const {
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size())
      return false;
    return file.commit();
  }
};

std::string safeProviderName(const std::string &value) {
  static const std::regex safe("^[a-z0-9-]{1,48}$");
  return std::regex_match(value, safe) ? value : "invalid-provider";
}

}  // namespace

namespace webeeblocks {

std::unique_ptr<FileDialogProvider> createQtFileDialogProvider() {
  return std::make_unique<QtFileDialogProvider>();
}

FileBroker::FileBroker(std::unique_ptr<FileDialogProvider> provider) : mProvider(std::move(provider)) {
}

FileBroker::~FileBroker() = default;

bool FileBroker::handleMessage(const char *message, char *response, std::size_t responseSize) const {
  if (!message || !response || responseSize == 0 || !mProvider)
    return false;
  response[0] = '\0';

  int requestId = -1;
  char extra[2] = {0};
  const std::string pattern = std::string(kPrefix) + " REQUEST %d CAPABILITIES %1s";
  if (std::sscanf(message, pattern.c_str(), &requestId, extra) != 1 || requestId < 1)
    return false;

  const std::string provider = safeProviderName(mProvider->name());
  const int written = std::snprintf(
    response, responseSize,
    "%s RESPONSE %d CAPABILITIES {\"protocol\":1,\"provider\":\"%s\",\"providerInjectable\":true,"
    "\"operationsReady\":false,\"canonicalExtension\":\".wbb\"}",
    kPrefix, requestId, provider.c_str());
  return written > 0 && static_cast<std::size_t>(written) < responseSize;
}

}  // namespace webeeblocks

struct WbFileBroker {
  explicit WbFileBroker(std::unique_ptr<webeeblocks::FileDialogProvider> provider) : value(std::move(provider)) {}
  webeeblocks::FileBroker value;
};

extern "C" WbFileBroker *wb_file_broker_create_qt(void) {
  try {
    return new WbFileBroker(webeeblocks::createQtFileDialogProvider());
  } catch (...) {
    return nullptr;
  }
}

extern "C" void wb_file_broker_destroy(WbFileBroker *broker) {
  delete broker;
}

extern "C" int wb_file_broker_handle_message(const WbFileBroker *broker, const char *message, char *response,
                                                size_t response_size) {
  return broker && broker->value.handleMessage(message, response, response_size) ? 1 : 0;
}
