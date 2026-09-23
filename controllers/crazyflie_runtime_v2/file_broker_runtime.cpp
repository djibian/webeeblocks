#include "file_broker_c.h"

#include <webots/plugins/robot_window/default.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#include <cctype>
#include <climits>
#include <cstdio>
#include <cstring>
#include <string>

namespace {
constexpr const char *kPrefix = "WEBEEBLOCKS_FILE_BROKER_V1 ";
constexpr const char *kRuntimeHello = "WEBEEBLOCKS_RUNTIME_V2 HELLO";
constexpr const char *kRuntimeReady = "WEBEEBLOCKS_RUNTIME_V2 READY";
constexpr const char *kAttemptPrefix = "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 ";
constexpr const char *kCompletionPrefix = "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1";
constexpr const char *kFailureProbePrefix = "WEBEEBLOCKS_ACTIVITY_FAILURE_PROBE_V1";
WbFileBroker *gBroker = nullptr;
WbFieldRef gActivityCustomData = 0;
unsigned long long gActivityAttempt = 1;
int gPendingResetRequest = -1;
bool gActivityChannelInitialized = false;

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

bool isSafeOracle(const char *oracle) {
  if (!oracle || !*oracle)
    return false;
  for (const unsigned char *cursor = reinterpret_cast<const unsigned char *>(oracle); *cursor; ++cursor) {
    if (!std::isalnum(*cursor) && *cursor != '_' && *cursor != '-' && *cursor != '.')
      return false;
  }
  return true;
}

void publishActivityAttempt(void) {
  if (!gActivityCustomData)
    return;
  char marker[128];
  std::snprintf(marker, sizeof(marker), "%s%llu", kAttemptPrefix, gActivityAttempt);
  wb_supervisor_field_set_sf_string(gActivityCustomData, marker);
}

void publishActivityCompletion(const char *oracle) {
  if (!gActivityCustomData || !isSafeOracle(oracle))
    return;
  char marker[192];
  std::snprintf(marker, sizeof(marker), "%s attempt=%llu oracle=%s", kCompletionPrefix, gActivityAttempt, oracle);
  wb_supervisor_field_set_sf_string(gActivityCustomData, marker);
}

void publishActivityFailureProbe(const char *oracle) {
  if (!gActivityCustomData || !isSafeOracle(oracle))
    return;
  char marker[192];
  std::snprintf(marker, sizeof(marker), "%s attempt=%llu oracle=%s", kFailureProbePrefix, gActivityAttempt, oracle);
  wb_supervisor_field_set_sf_string(gActivityCustomData, marker);
}

bool hasCurrentActivityOutcome(const char *oracle) {
  if (!gActivityCustomData || !isSafeOracle(oracle))
    return false;
  const char *data = wb_supervisor_field_get_sf_string(gActivityCustomData);
  unsigned long long attempt = 0;
  char publishedOracle[64] = {0};
  char status[32] = {0};
  char trailing[2] = {0};
  if (!data || std::sscanf(data,
      "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%63s status=%31s %1s",
      &attempt, publishedOracle, status, trailing) != 3)
    return false;
  if (attempt != gActivityAttempt || std::strcmp(publishedOracle, oracle) != 0)
    return false;
  return std::strcmp(status, "achieved") == 0 || std::strcmp(status, "not-achieved") == 0 ||
         std::strcmp(status, "interrupted") == 0;
}

bool ensureActivityChannel(void) {
  if (gActivityChannelInitialized)
    return gActivityCustomData != 0;
  gActivityChannelInitialized = true;
  WbNodeRef self = wb_supervisor_node_get_self();
  if (!self)
    return false;
  gActivityCustomData = wb_supervisor_node_get_field(self, "customData");
  if (!gActivityCustomData)
    return false;
  publishActivityAttempt();
  return true;
}

void sendRuntimeError(int id, const char *code) {
  char response[192];
  std::snprintf(response, sizeof(response), "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d ERR %s", id, code);
  wb_robot_wwi_send_text(response);
}

void sendRuntimeState(int id, const char *status) {
  char response[192];
  std::snprintf(response, sizeof(response), "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d STATE %s", id, status);
  wb_robot_wwi_send_text(response);
}

bool handleMissionCompletionRequest(const char *message) {
  if (!message)
    return false;
  int id = -1;
  char command[32] = {0};
  if (std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s", &id, command) != 2 ||
      std::strcmp(command, "COMPLETE") != 0)
    return false;

  char oracle[64] = {0};
  char extra[2] = {0};
  if (id < 1 || std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d COMPLETE %63s %1s", &id, oracle, extra) != 2 ||
      !isSafeOracle(oracle)) {
    if (id >= 1)
      sendRuntimeError(id, "INVALID_MISSION_REQUEST");
    return true;
  }
  if (!ensureActivityChannel()) {
    sendRuntimeError(id, "OUTCOME_UNAVAILABLE");
    return true;
  }
  if (!hasCurrentActivityOutcome(oracle))
    publishActivityCompletion(oracle);
  char response[192];
  std::snprintf(response, sizeof(response), "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d OK", id);
  wb_robot_wwi_send_text(response);
  return true;
}

bool handleMissionFailureProbeRequest(const char *message) {
  if (!message)
    return false;
  int id = -1;
  char command[32] = {0};
  if (std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s", &id, command) != 2 ||
      std::strcmp(command, "FAILURE") != 0)
    return false;

  char oracle[64] = {0};
  char extra[2] = {0};
  if (id < 1 || std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d FAILURE %63s %1s", &id, oracle, extra) != 2 ||
      !isSafeOracle(oracle)) {
    if (id >= 1)
      sendRuntimeError(id, "INVALID_MISSION_REQUEST");
    return true;
  }
  if (!ensureActivityChannel()) {
    sendRuntimeError(id, "OUTCOME_UNAVAILABLE");
    return true;
  }
  if (!hasCurrentActivityOutcome(oracle))
    publishActivityFailureProbe(oracle);
  char response[192];
  std::snprintf(response, sizeof(response), "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d OK", id);
  wb_robot_wwi_send_text(response);
  return true;
}

bool handleOutcomeRequest(const char *message) {
  if (!message)
    return false;
  int id = -1;
  char command[32] = {0};
  if (std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s", &id, command) != 2 ||
      std::strcmp(command, "OUTCOME") != 0)
    return false;

  char oracle[64] = {0};
  char extra[2] = {0};
  if (id < 1 || std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d OUTCOME %63s %1s", &id, oracle, extra) != 2 ||
      !isSafeOracle(oracle)) {
    if (id >= 1)
      sendRuntimeError(id, "INVALID_OUTCOME_REQUEST");
    return true;
  }
  if (!ensureActivityChannel()) {
    sendRuntimeError(id, "OUTCOME_UNAVAILABLE");
    return true;
  }

  const char *data = wb_supervisor_field_get_sf_string(gActivityCustomData);
  unsigned long long attempt = 0;
  char publishedOracle[64] = {0};
  char status[32] = {0};
  char trailing[2] = {0};
  if (!data || std::sscanf(data,
      "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%63s status=%31s %1s",
      &attempt, publishedOracle, status, trailing) != 3) {
    sendRuntimeError(id, "OUTCOME_UNAVAILABLE");
    return true;
  }
  if (attempt != gActivityAttempt) {
    sendRuntimeError(id, "STALE_OUTCOME");
    return true;
  }
  if (std::strcmp(publishedOracle, oracle) != 0) {
    sendRuntimeError(id, "OUTCOME_MISMATCH");
    return true;
  }
  if (std::strcmp(status, "achieved") != 0 && std::strcmp(status, "not-achieved") != 0 &&
      std::strcmp(status, "interrupted") != 0) {
    sendRuntimeError(id, "INVALID_OUTCOME");
    return true;
  }
  sendRuntimeState(id, status);
  return true;
}

bool resetRequestId(const char *message, int *id) {
  if (!message || !id)
    return false;
  int parsedId = -1;
  char command[32] = {0};
  char extra[2] = {0};
  if (std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s %1s", &parsedId, command, extra) != 2 ||
      parsedId < 1 || std::strcmp(command, "RESET") != 0)
    return false;
  *id = parsedId;
  return true;
}

void observeRuntimeResponse(const char *message) {
  if (!message || gPendingResetRequest < 1)
    return;
  int id = -1;
  char payload[96] = {0};
  if (std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d %95[^\n]", &id, payload) != 2 ||
      id != gPendingResetRequest)
    return;
  if (std::strcmp(payload, "OK") == 0) {
    if (gActivityAttempt == ULLONG_MAX)
      gActivityAttempt = 0;
    else
      ++gActivityAttempt;
    if (ensureActivityChannel())
      publishActivityAttempt();
  }
  gPendingResetRequest = -1;
}

const char *nullTerminatedMessage(const char *data, int size) {
  if (!data || size < 1)
    return nullptr;
  const void *terminator = std::memchr(data, '\0', static_cast<size_t>(size));
  if (terminator != data + size - 1)
    return nullptr;
  return data;
}
}  // namespace

extern "C" const char *webeeblocks_file_broker_receive_text(void) {
  ensureActivityChannel();
  const char *message = nullptr;
  while ((message = wb_robot_wwi_receive_text()) != nullptr) {
    // A Robot Window may attach after the controller's one-shot startup READY.
    // Reply only once the controller has entered its normal receive loop; this
    // is a liveness handshake and never executes or replays a student action.
    if (isRuntimeHello(message)) {
      wb_robot_wwi_send_text(kRuntimeReady);
      continue;
    }
    if (handleMissionCompletionRequest(message))
      continue;
    if (handleMissionFailureProbeRequest(message))
      continue;
    if (handleOutcomeRequest(message))
      continue;
    int resetId = -1;
    if (resetRequestId(message, &resetId) && gPendingResetRequest < 1)
      gPendingResetRequest = resetId;
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

extern "C" void webeeblocks_file_broker_send(const char *data, int size) {
  const char *message = nullTerminatedMessage(data, size);
  if (message && std::strcmp(message, kRuntimeReady) == 0)
    ensureActivityChannel();
  observeRuntimeResponse(message);
  wb_robot_wwi_send(data, size);
}

extern "C" void webeeblocks_file_broker_robot_cleanup(void) {
  if (gBroker) {
    wb_file_broker_destroy(gBroker);
    gBroker = nullptr;
  }
  gActivityCustomData = 0;
  gActivityAttempt = 1;
  gPendingResetRequest = -1;
  gActivityChannelInitialized = false;
  wb_robot_cleanup();
}
