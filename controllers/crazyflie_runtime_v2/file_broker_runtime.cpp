#include "file_broker_c.h"

#include <webots/plugins/robot_window/default.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>

namespace {
constexpr const char *kPrefix = "WEBEEBLOCKS_FILE_BROKER_V1 ";
constexpr const char *kRuntimePrefix = "WEBEEBLOCKS_RUNTIME_V2 ";
constexpr const char *kRuntimeHello = "WEBEEBLOCKS_RUNTIME_V2 HELLO";
constexpr const char *kRuntimeReady = "WEBEEBLOCKS_RUNTIME_V2 READY";
constexpr const char *kRuntimeEnvironment = "runtime-v2-obstacles-v1";
constexpr const char *kLandedZoneOracle = "landed-zone-v1";
constexpr double kLandedAltitudeTolerance = 0.08;
constexpr double kMaxOutcomeRadius = 2.0;
WbFileBroker *gBroker = nullptr;
unsigned long long gRuntimeAttempt = 1;
WbNodeRef gRuntimeSelf = nullptr;
double gRuntimeInitialZ = NAN;
bool gRuntimeBaselineInitialized = false;

bool isBrokerMessage(const char *message) {
  return message && std::strncmp(message, kPrefix, std::strlen(kPrefix)) == 0;
}

bool isRuntimeMessage(const char *message) {
  return message && std::strncmp(message, kRuntimePrefix, std::strlen(kRuntimePrefix)) == 0;
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

int runtimeRequestId(const char *message) {
  int id = -1;
  if (message)
    std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d", &id);
  return id;
}

void sendUnavailable(const char *message) {
  const int id = requestId(message);
  if (id < 1)
    return;
  const std::string response = "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE " + std::to_string(id) + " ERR UNAVAILABLE";
  wb_robot_wwi_send_text(response.c_str());
}

void sendRuntimeValue(int id, double value) {
  char response[160];
  std::snprintf(response, sizeof(response), "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d VALUE %.9f", id, value);
  wb_robot_wwi_send_text(response);
}

void sendRuntimeError(int id, const char *reason) {
  char response[192];
  std::snprintf(response, sizeof(response), "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d ERR %s", id, reason);
  wb_robot_wwi_send_text(response);
}

void ensureRuntimeBaseline() {
  if (gRuntimeBaselineInitialized)
    return;
  gRuntimeBaselineInitialized = true;
  gRuntimeSelf = wb_supervisor_node_get_self();
  if (!gRuntimeSelf)
    return;
  const double *position = wb_supervisor_node_get_position(gRuntimeSelf);
  if (position && std::isfinite(position[2]))
    gRuntimeInitialZ = position[2];
}

bool hasExpectedRuntimeEnvironment() {
  if (!gRuntimeSelf || !std::isfinite(gRuntimeInitialZ))
    return false;
  return wb_supervisor_node_get_from_def("FIRST_OBSTACLE") != nullptr &&
         wb_supervisor_node_get_from_def("SECOND_OBSTACLE") != nullptr;
}

bool isRuntimeResetRequest(const char *message) {
  int id = -1;
  char extra[2] = {0};
  return message && std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d RESET %1s", &id, extra) == 1 && id >= 1;
}

bool parseRuntimeAttemptRequest(const char *message, int *id) {
  char extra[2] = {0};
  int parsed_id = -1;
  if (!message || std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d ATTEMPT %1s", &parsed_id, extra) != 1 || parsed_id < 1)
    return false;
  *id = parsed_id;
  return true;
}

bool parseRuntimeOutcomeRequest(const char *message, int *id, unsigned long long *attempt,
                                char *environment, char *oracle, double *target_x,
                                double *target_y, double *radius) {
  char extra[2] = {0};
  int parsed_id = -1;
  unsigned long long parsed_attempt = 0;
  char parsed_environment[64] = {0};
  char parsed_oracle[64] = {0};
  double parsed_x = 0.0;
  double parsed_y = 0.0;
  double parsed_radius = 0.0;
  const int count = message ? std::sscanf(
    message,
    "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d OUTCOME %llu %63s %63s %lf %lf %lf %1s",
    &parsed_id, &parsed_attempt, parsed_environment, parsed_oracle,
    &parsed_x, &parsed_y, &parsed_radius, extra) : 0;
  if (count != 7 || parsed_id < 1 || parsed_attempt < 1)
    return false;
  *id = parsed_id;
  *attempt = parsed_attempt;
  std::strncpy(environment, parsed_environment, 63);
  environment[63] = '\0';
  std::strncpy(oracle, parsed_oracle, 63);
  oracle[63] = '\0';
  *target_x = parsed_x;
  *target_y = parsed_y;
  *radius = parsed_radius;
  return true;
}

bool handleRuntimeInfrastructureMessage(const char *message) {
  if (!isRuntimeMessage(message))
    return false;

  ensureRuntimeBaseline();

  int id = -1;
  if (parseRuntimeAttemptRequest(message, &id)) {
    if (!hasExpectedRuntimeEnvironment()) {
      sendRuntimeError(id, "OUTCOME_ENVIRONMENT_UNAVAILABLE");
      return true;
    }
    sendRuntimeValue(id, static_cast<double>(gRuntimeAttempt));
    return true;
  }

  unsigned long long attempt = 0;
  char environment[64] = {0};
  char oracle[64] = {0};
  double target_x = 0.0;
  double target_y = 0.0;
  double radius = 0.0;
  if (parseRuntimeOutcomeRequest(message, &id, &attempt, environment, oracle, &target_x, &target_y, &radius)) {
    if (!hasExpectedRuntimeEnvironment()) {
      sendRuntimeError(id, "OUTCOME_ENVIRONMENT_UNAVAILABLE");
      return true;
    }
    if (attempt != gRuntimeAttempt) {
      sendRuntimeError(id, "STALE_ATTEMPT");
      return true;
    }
    if (std::strcmp(environment, kRuntimeEnvironment) != 0) {
      sendRuntimeError(id, "OUTCOME_ENVIRONMENT_MISMATCH");
      return true;
    }
    if (std::strcmp(oracle, kLandedZoneOracle) != 0) {
      sendRuntimeError(id, "OUTCOME_ORACLE_UNAVAILABLE");
      return true;
    }
    if (!std::isfinite(target_x) || !std::isfinite(target_y) || !std::isfinite(radius) ||
        radius <= 0.0 || radius > kMaxOutcomeRadius) {
      sendRuntimeError(id, "INVALID_OUTCOME_REQUEST");
      return true;
    }
    const double *position = wb_supervisor_node_get_position(gRuntimeSelf);
    if (!position || !std::isfinite(position[0]) || !std::isfinite(position[1]) || !std::isfinite(position[2])) {
      sendRuntimeError(id, "OUTCOME_OBSERVATION_UNAVAILABLE");
      return true;
    }
    const bool landed = std::fabs(position[2] - gRuntimeInitialZ) <= kLandedAltitudeTolerance;
    const bool inside_zone = std::hypot(position[0] - target_x, position[1] - target_y) <= radius;
    sendRuntimeValue(id, landed && inside_zone ? 1.0 : 0.0);
    return true;
  }

  if (isRuntimeResetRequest(message)) {
    ++gRuntimeAttempt;
    return false;
  }
  return false;
}
}  // namespace

extern "C" const char *webeeblocks_file_broker_receive_text(void) {
  const char *message = nullptr;
  while ((message = wb_robot_wwi_receive_text()) != nullptr) {
    // A Robot Window may attach after the controller's one-shot startup READY.
    // Reply only once the controller has entered its normal receive loop; this
    // is a liveness handshake and never executes or replays a student action.
    if (isRuntimeHello(message)) {
      ensureRuntimeBaseline();
      wb_robot_wwi_send_text(kRuntimeReady);
      continue;
    }
    if (handleRuntimeInfrastructureMessage(message))
      continue;
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
