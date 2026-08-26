#include "file_broker.hpp"

#include <cassert>
#include <cstring>
#include <iostream>
#include <memory>
#include <string>

class InjectedProvider final : public webeeblocks::FileDialogProvider {
public:
  std::string name() const override { return "ci-injected-dialog"; }
};

int main() {
  webeeblocks::FileBroker broker(std::make_unique<InjectedProvider>());
  char response[512];
  assert(broker.handleMessage("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 7 CAPABILITIES", response, sizeof(response)));
  const std::string value(response);
  assert(value.find("RESPONSE 7 CAPABILITIES") != std::string::npos);
  assert(value.find("\"provider\":\"ci-injected-dialog\"") != std::string::npos);
  assert(value.find("\"operationsReady\":false") != std::string::npos);
  std::memset(response, 'x', sizeof(response));
  assert(!broker.handleMessage("WEBEEBLOCKS_RUNTIME_V2 REQUEST 7 RANGE front", response, sizeof(response)));
  assert(response[0] == '\0');
  assert(!broker.handleMessage("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 7 CAPABILITIES trailing", response, sizeof(response)));
  std::cout << "PASS: injectable capability-only broker contract\n";
}
