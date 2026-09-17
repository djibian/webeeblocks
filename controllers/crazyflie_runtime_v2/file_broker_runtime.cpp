#include "file_broker_c.h"

#include <webots/plugins/robot_window/default.h>
#include <webots/robot.h>

#include <cstdio>
#include <cstring>
#include <string>

namespace {
constexpr const char *kPrefix = "WEBEEBLOCKS_FILE_BROKER_V1 ";
constexpr const char *kRuntimeHello = "WEBEEBLOCKS_RUNTIME_V2 HELLO";
constexpr const char *kRuntimeReady = "WEBEEBLOCKS_RUNTIME_V2 READY";
WbFileBroker *gBroker = nullptr;

bool isBrokerMessage(const char *message) {
  return message && std::strncmp(message, kPrefix, std::strlen(kPrefix)) == 0;
}

bool isRuntimeHello(const char *message) {
  return message && std::strcmp(message, kRuntimeHello) == 0;
}

int requestId(const char *message) {
  int id = -1;
  if (message)
    std::sscanf(message, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST %d", &id);
  return id;
}

void sendUnavailable(const char *message) {
  const int id = requestId(message);
  if (id < 1)
    return;
  const std::string response = "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE " + std::to_string(id) + " ERR UNAVAILABLE";
  wb_robot_wwi_send_text(response.c_str());
}
}  // namespace

extern "C" const char *webeeblocks_file_broker_receive_text(void) {
  const char *message = nullptr;
  while ((message = wb_robot_wwi_receive_text()) != nullptr) {
    // A Robot Window may attach after the controller's one-shot startup READY.
    // Reply only once the controller has entered its normal receive loop; this
    // is a liveness handshake and never executes or replays a student action.
    if (isRuntimeHello(message)) {
      wb_robot_wwi_send_text(kRuntimeReady);
      continue;
    }
    if (!isBrokerMessage(message))
      return message;
    if (!gBroker)
      gBroker = wb_file_broker_create_qt();
    if (!gBroker) {
      sendUnavailable(message);
      continue;
    }
    const char *response = wb_file_broker_handle_message(gBroker, message);
    if (response)
      wb_robot_wwi_send_text(response);
  }
  return nullptr;
}

extern "C" void webeeblocks_file_broker_robot_cleanup(void) {
  if (gBroker) {
    wb_file_broker_destroy(gBroker);
    gBroker = nullptr;
  }
  wb_robot_cleanup();
}