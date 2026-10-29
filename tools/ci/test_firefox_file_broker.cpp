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
  int openCalls = 0;
  int saveAsCalls = 0;
  int saveCalls = 0;
  int releaseCalls = 0;
};

class FakeProvider final : public webeeblocks::FileDialogProvider {
public:
  explicit FakeProvider(FakeState *state) : state_(state) {}
  std::string name() const override { return "fake-native"; }
  webeeblocks::OpenFileResult open() override {
    ++state_->openCalls;
    if (state_->cancelOpen)
      return {webeeblocks::FileOperationStatus::Cancelled, "", "", "", ""};
    return {webeeblocks::FileOperationStatus::Ok, "opaque_open_1", "élève.wbb", "{\"format\":\"webeeblocks-project\"}\n", ""};
  }
  webeeblocks::SaveFileResult saveAs(const std::string &name, const std::string &bytes) override {
    ++state_->saveAsCalls;
    state_->lastName = name;
    state_->lastBytes = bytes;
    return {webeeblocks::FileOperationStatus::Ok, "opaque_saveas_2", name, ""};
  }
  webeeblocks::SaveFileResult save(const std::string &reference, const std::string &bytes) override {
    ++state_->saveCalls;
    state_->lastReference = reference;
    state_->lastBytes = bytes;
    if (state_->missingTarget)
      return {webeeblocks::FileOperationStatus::Error, "", "", "TARGET_UNAVAILABLE"};
    return {webeeblocks::FileOperationStatus::Ok, reference, "élève.wbb", ""};
  }
  void release(const std::string &reference) override {
    ++state_->releaseCalls;
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

  // A file REQUEST with a valid ID but no operation is still consumed.
  // It must reply immediately, rather than silently timing out in the UI.
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 11") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 11 ERR INVALID_REQUEST");
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 12   ") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 12 ERR INVALID_REQUEST");
  // If no valid ID exists, do not fabricate a response to an unknown request.
  std::string noIdResponse;
  assert(broker.handleMessage("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST unknown OPEN", &noIdResponse));
  assert(noIdResponse.empty());
  // A numeric ID outside the accepted domain is likewise unrecoverable;
  // it must not generate a guessed response or call a provider operation.
  std::string nonpositiveIdResponse;
  assert(broker.handleMessage("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 0", &nonpositiveIdResponse));
  assert(nonpositiveIdResponse.empty());
  // Known operation, wrong arity: same fail-closed, ID-preserving response.
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 13 SAVE_AS") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 13 ERR INVALID_REQUEST");

  // B4-I0: invalid messages and excessive project contents must never reach
  // the dialog/file provider, even when they have a valid, reusable request ID.
  const int openBefore = state.openCalls;
  const int saveAsBefore = state.saveAsCalls;
  const int saveBefore = state.saveCalls;
  const int releaseBefore = state.releaseCalls;
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 14 OPEN unexpected") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 14 ERR INVALID_REQUEST");
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 15 SAVE_AS ZW5jb3Vycy53YmI= %%%=") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 15 ERR INVALID_REQUEST");
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 16 SAVE opaque_saveas_2 %%%=") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 16 ERR INVALID_REQUEST");
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 17 RELEASE ../escape") ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 17 ERR INVALID_REQUEST");
  std::string invalidIdResponse;
  assert(broker.handleMessage("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 2147483648 OPEN", &invalidIdResponse));
  assert(invalidIdResponse.empty());

  // Materialize 4 MiB + 1 byte of valid base64 without an external fixture.
  // The parser must reject it before invoking either SAVE or SAVE_AS.
  const std::size_t oversizeBytes = webeeblocks::FileBroker::kMaxProjectBytes + 1;
  std::string oversizeBase64;
  oversizeBase64.reserve(((oversizeBytes + 2) / 3) * 4);
  for (std::size_t i = 0; i < oversizeBytes / 3; ++i)
    oversizeBase64 += "eHh4";  // 3 ASCII 'x' bytes
  if (oversizeBytes % 3 == 1)
    oversizeBase64 += "eA==";
  else if (oversizeBytes % 3 == 2)
    oversizeBase64 += "eHg=";
  assert(oversizeBase64.size() == ((oversizeBytes + 2) / 3) * 4);
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 18 SAVE_AS ZW5jb3Vycy53YmI= " + oversizeBase64) ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 18 ERR PROJECT_TOO_LARGE");
  assert(send(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 19 SAVE opaque_saveas_2 " + oversizeBase64) ==
         "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 19 ERR PROJECT_TOO_LARGE");
  assert(state.openCalls == openBefore);
  assert(state.saveAsCalls == saveAsBefore);
  assert(state.saveCalls == saveBefore);
  assert(state.releaseCalls == releaseBefore);

  std::cout << "PASS firefox-file-broker: capabilities/open/save-as/same-reference-save/release/cancel/errors/no-browser-path/invalid-and-oversize-no-side-effects\n";
  return 0;
}
