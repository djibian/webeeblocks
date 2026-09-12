#include "file_broker.hpp"

#include <cassert>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace {
struct FakeState {
  std::string lastName;
  std::string lastBytes;
  std::string lastReference;
  std::vector<std::string> releasedReferences;
  bool cancelOpen = false;
  bool missingTarget = false;
};

class FakeProvider final : public webeeblocks::FileDialogProvider {
public:
  explicit FakeProvider(FakeState *state) : state_(state) {}
  std::string name() const override { return "fake-native"; }
  webeeblocks::OpenFileResult open() override {
    if (state_->cancelOpen)
      return {webeeblocks::FileOperationStatus::Cancelled, "", "", "", ""};
    return {webeeblocks::FileOperationStatus::Ok, "opaque_open_1", "élève.wbb", "{\"format\":\"webeeblocks-project\"}\n", ""};
  }
  webeeblocks::SaveFileResult saveAs(const std::string &name, const std::string &bytes) override {
    state_->lastName = name;
    state_->lastBytes = bytes;
    return {webeeblocks::FileOperationStatus::Ok, "opaque_saveas_2", name, ""};
  }
  webeeblocks::SaveFileResult save(const std::string &reference, const std::string &bytes) override {
    state_->lastReference = reference;
    state_->lastBytes = bytes;
    if (state_->missingTarget)
      return {webeeblocks::FileOperationStatus::Error, "", "", "TARGET_UNAVAILABLE"};
    return {webeeblocks::FileOperationStatus::Ok, reference, "élève.wbb", ""};
  }
  void release(const std::string &reference) override {
    state_->releasedReferences.push_back(reference);
  }
private:
  FakeState *state_;
};

std::string send(webeeblocks::FileBroker &broker, const std::string &message) {
  std::string response;
  assert(broker.handleMessage(message.c_str(), &response));
  assert(!response.empty());
  return response;
}
}  // namespace

int main() {
  FakeState state;
  webeeblocks::FileBroker broker(std::make_unique<FakeProvider>(&state));
  std::string ignored;
  assert(!broker.handleMessage("WEBEEBLOCKS_RUNTIME_V2 READY", &ignored));

  const auto capabilities = send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 1 CAPABILITIES");
  assert(capabilities.find("\"operationsReady\":true") != std::string::npos);
  assert(capabilities.find("\"sameFileSave\":true") != std::string::npos);
  assert(capabilities.find("\"referenceRelease\":true") != std::string::npos);

  const auto opened = send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 2 OPEN");
  assert(opened.find("RESPONSE 2 OPEN OK opaque_open_1 ") != std::string::npos);
  assert(opened.find("/tmp/") == std::string::npos);

  const std::string bytes64 = "eyJvayI6MX0K";  // {"ok":1}\n
  const auto saveAs = send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 3 SAVE_AS ZW5jb3Vycy53YmI= " + bytes64);
  assert(saveAs.find("RESPONSE 3 SAVE_AS OK opaque_saveas_2 ") != std::string::npos);
  assert(state.lastName == "encours.wbb");
  assert(state.lastBytes == "{\"ok\":1}\n");

  const auto save = send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 4 SAVE opaque_saveas_2 " + bytes64);
  assert(save.find("RESPONSE 4 SAVE OK opaque_saveas_2 ") != std::string::npos);
  assert(state.lastReference == "opaque_saveas_2");
  assert(state.lastBytes == "{\"ok\":1}\n");

  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 5 RELEASE opaque_open_1") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 5 RELEASE OK");
  assert(state.releasedReferences.size() == 1);
  assert(state.releasedReferences.back() == "opaque_open_1");

  // A browser-supplied path is rejected at the protocol boundary; the provider
  // can receive only a basename proposal and an opaque reference.
  const auto pathInjection = send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 6 SAVE_AS L3RtcC9ldmlsLndiYg== " + bytes64);
  assert(pathInjection == "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 6 ERR INVALID_REQUEST");

  state.cancelOpen = true;
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 7 OPEN") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 7 OPEN CANCELLED");
  state.cancelOpen = false;

  state.missingTarget = true;
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 8 SAVE opaque_saveas_2 " + bytes64) ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 8 ERR TARGET_UNAVAILABLE");

  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 9 SAVE ../escape " + bytes64) ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 9 ERR INVALID_REQUEST");
  const auto releaseCount = state.releasedReferences.size();
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 10 RELEASE ../escape") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 10 ERR INVALID_REQUEST");
  assert(state.releasedReferences.size() == releaseCount);

  std::cout << "PASS firefox-file-broker: capabilities/open/save-as/same-reference-save/release/cancel/errors/no-browser-path\n";
  return 0;
}
