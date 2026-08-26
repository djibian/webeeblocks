#include "file_broker.hpp"
#include "file_broker_c.h"

#include <QApplication>
#include <QCoreApplication>
#include <QFileDialog>

#include <array>
#include <cstdio>
#include <cstring>
#include <memory>
#include <regex>
#include <stdexcept>
#include <utility>

namespace {
constexpr const char *kPrefix = "WEBEEBLOCKS_FILE_BROKER_V1";

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
    std::puts("WEBEEBLOCKS_FILE_BROKER_V1 QT_APP_INITIALIZED");
    mDialog = std::make_unique<QFileDialog>();
    std::puts("WEBEEBLOCKS_FILE_BROKER_V1 QFILEDIALOG_CONSTRUCTED");
    std::fflush(stdout);
  }

  std::string name() const override { return "qt6-qfiledialog-constructed"; }

private:
  int mArgc = 1;
  std::array<char, 64> mProgramName{};
  std::array<char *, 2> mArgv{};
  std::unique_ptr<QApplication> mApplication;
  std::unique_ptr<QFileDialog> mDialog;
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

FileBroker::FileBroker(std::unique_ptr<FileDialogProvider> provider) : mProvider(std::move(provider)) {}
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
  } catch (const std::exception &error) {
    std::fprintf(stderr, "WEBEEBLOCKS_FILE_BROKER_V1 FATAL %s\n", error.what());
    return nullptr;
  }
}
extern "C" void wb_file_broker_destroy(WbFileBroker *broker) { delete broker; }
extern "C" int wb_file_broker_handle_message(const WbFileBroker *broker, const char *message, char *response,
                                               size_t response_size) {
  return broker && broker->value.handleMessage(message, response, response_size) ? 1 : 0;
}
