#!/usr/bin/env python3
"""Compile the production native broker against injected Webots transport stubs.

The probe locks two mission-channel invariants:
- COMPLETE must not erase an already-published terminal result for the current
  attempt and oracle, while stale/malformed/cross-oracle results are not promoted;
- FAILURE may name one exact current-attempt oracle without asserting executable
  completion, preserving an already-matching terminal result and otherwise
  publishing only the bounded failure-probe marker consumed by world evaluators.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[2]
BROKER = ROOT / "controllers" / "crazyflie_runtime_v2" / "file_broker_runtime.cpp"
CONTROLLER_DIR = BROKER.parent

ROBOT_H = r"""
#pragma once
#ifdef __cplusplus
extern "C" {
#endif
const char *wb_robot_wwi_receive_text(void);
void wb_robot_wwi_send_text(const char *text);
void wb_robot_wwi_send(const void *data, int size);
void wb_robot_cleanup(void);
#ifdef __cplusplus
}
#endif
"""

SUPERVISOR_H = r"""
#pragma once
#ifdef __cplusplus
extern "C" {
#endif
typedef void *WbNodeRef;
typedef void *WbFieldRef;
WbNodeRef wb_supervisor_node_get_self(void);
WbFieldRef wb_supervisor_node_get_field(WbNodeRef node, const char *name);
void wb_supervisor_field_set_sf_string(WbFieldRef field, const char *value);
const char *wb_supervisor_field_get_sf_string(WbFieldRef field);
#ifdef __cplusplus
}
#endif
"""

PROBE = r'''#include "file_broker_c.h"

#include <cassert>
#include <cstdio>
#include <cstring>
#include <deque>
#include <iostream>
#include <string>
#include <vector>

extern "C" const char *webeeblocks_file_broker_receive_text(void);
extern "C" void webeeblocks_file_broker_send(const char *data, int size);
extern "C" void webeeblocks_file_broker_robot_cleanup(void);

struct WbFileBroker {};

static std::deque<std::string> incoming;
static std::string current_message;
static std::vector<std::string> sent_text;
static std::vector<std::string> sent_binary;
static std::string custom_data;
static int node_token = 0;
static int field_token = 0;

// No Qt is loaded: exercise the production adapter with a spy provider.
static bool provider_available = true;
static int provider_creations = 0, provider_destructions = 0, provider_messages = 0;
static std::string provider_reply;
extern "C" WbFileBroker *wb_file_broker_create_qt(void) {
  ++provider_creations;
  return provider_available ? new WbFileBroker{} : nullptr;
}
extern "C" void wb_file_broker_destroy(WbFileBroker *broker) {
  ++provider_destructions;
  delete broker;
}
extern "C" const char *wb_file_broker_handle_message(WbFileBroker *, const char *message) {
  ++provider_messages;
  int id = -1;
  if (message)
    std::sscanf(message, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST %d", &id);
  provider_reply = "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE " + std::to_string(id) + " ERR FAKE_PROVIDER";
  return provider_reply.c_str();
}

extern "C" const char *wb_robot_wwi_receive_text(void) {
  if (incoming.empty())
    return nullptr;
  current_message = incoming.front();
  incoming.pop_front();
  return current_message.c_str();
}

extern "C" void wb_robot_wwi_send_text(const char *text) {
  sent_text.emplace_back(text ? text : "");
}

extern "C" void wb_robot_wwi_send(const void *data, int size) {
  if (!data || size <= 0) {
    sent_binary.emplace_back();
    return;
  }
  const char *bytes = static_cast<const char *>(data);
  sent_binary.emplace_back(bytes, bytes + size);
}

extern "C" void wb_robot_cleanup(void) {}

extern "C" void *wb_supervisor_node_get_self(void) {
  return &node_token;
}

extern "C" void *wb_supervisor_node_get_field(void *, const char *name) {
  return name && std::strcmp(name, "customData") == 0 ? static_cast<void *>(&field_token) : nullptr;
}

extern "C" void wb_supervisor_field_set_sf_string(void *, const char *value) {
  custom_data = value ? value : "";
}

extern "C" const char *wb_supervisor_field_get_sf_string(void *) {
  return custom_data.c_str();
}

static void reset_harness() {
  webeeblocks_file_broker_robot_cleanup();
  incoming.clear();
  sent_text.clear();
  sent_binary.clear();
  custom_data.clear();
  provider_available = true;
  provider_creations = provider_destructions = provider_messages = 0;
  provider_reply.clear();
  assert(webeeblocks_file_broker_receive_text() == nullptr);
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
}

static void process(std::initializer_list<std::string> messages) {
  for (const std::string &message : messages)
    incoming.push_back(message);
  assert(webeeblocks_file_broker_receive_text() == nullptr);
}

static void expect_unavailable_after_complete(const std::string &seed) {
  reset_harness();
  custom_data = seed;
  process({
    "WEBEEBLOCKS_RUNTIME_V2 REQUEST 20 COMPLETE progression-precise-movement-v1",
    "WEBEEBLOCKS_RUNTIME_V2 REQUEST 21 OUTCOME progression-precise-movement-v1"
  });
  assert(custom_data ==
    "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=1 oracle=progression-precise-movement-v1");
  assert(sent_text.size() == 2);
  assert(sent_text[0] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 20 OK");
  assert(sent_text[1] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 21 ERR OUTCOME_UNAVAILABLE");
}

int main() {
  reset_harness();
  process({"WEBEEBLOCKS_RUNTIME_V2 HELLO", "WEBEEBLOCKS_RUNTIME_V2 HELLO"});
  assert(sent_text.size() == 2);
  assert(sent_text[0] == "WEBEEBLOCKS_RUNTIME_V2 READY HELLO");
  assert(sent_text[1] == "WEBEEBLOCKS_RUNTIME_V2 READY HELLO");
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  for (const char *status : {"achieved", "not-achieved", "interrupted"}) {
    reset_harness();
    custom_data = std::string("WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=progression-precise-movement-v1 status=") + status;
    const std::string original = custom_data;
    process({
      "WEBEEBLOCKS_RUNTIME_V2 REQUEST 10 COMPLETE progression-precise-movement-v1",
      "WEBEEBLOCKS_RUNTIME_V2 REQUEST 11 OUTCOME progression-precise-movement-v1"
    });
    assert(custom_data == original);
    assert(sent_text.size() == 2);
    assert(sent_text[0] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 10 OK");
    assert(sent_text[1] == std::string("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 11 STATE ") + status);
  }

  expect_unavailable_after_complete(
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=0 oracle=progression-precise-movement-v1 status=not-achieved");
  expect_unavailable_after_complete(
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=other-oracle status=not-achieved");
  expect_unavailable_after_complete(
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=progression-precise-movement-v1 status=mystery");
  expect_unavailable_after_complete("malformed terminal evidence");

  // FAILURE preserves already-authoritative exact-oracle terminal evidence and
  // never rewrites it into a synthetic completion/probe marker.
  reset_harness();
  custom_data =
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=progression-repeat-v1 status=not-achieved";
  const std::string exact_failure = custom_data;
  process({
    "WEBEEBLOCKS_RUNTIME_V2 REQUEST 22 FAILURE progression-repeat-v1",
    "WEBEEBLOCKS_RUNTIME_V2 REQUEST 23 OUTCOME progression-repeat-v1"
  });
  assert(custom_data == exact_failure);
  assert(sent_text.size() == 2);
  assert(sent_text[0] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 22 OK");
  assert(sent_text[1] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 23 STATE not-achieved");

  // Missing/cross-oracle evidence may be replaced only with a non-completion
  // failure-probe marker for the exact current attempt and requested oracle.
  reset_harness();
  custom_data =
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=progression-precise-movement-v1 status=not-achieved";
  process({"WEBEEBLOCKS_RUNTIME_V2 REQUEST 24 FAILURE progression-repeat-v1"});
  assert(custom_data ==
    "WEBEEBLOCKS_ACTIVITY_FAILURE_PROBE_V1 attempt=1 oracle=progression-repeat-v1");
  assert(sent_text.size() == 1);
  assert(sent_text[0] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 24 OK");
  process({"WEBEEBLOCKS_RUNTIME_V2 REQUEST 25 OUTCOME progression-repeat-v1"});
  assert(sent_text.size() == 2);
  assert(sent_text[1] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 25 ERR OUTCOME_UNAVAILABLE");

  reset_harness();
  process({"WEBEEBLOCKS_RUNTIME_V2 REQUEST 26 FAILURE bad/oracle"});
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  assert(sent_text.size() == 1);
  assert(sent_text[0] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 26 ERR INVALID_MISSION_REQUEST");

  reset_harness();
  custom_data =
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=progression-precise-movement-v1 status=not-achieved";
  incoming.push_back("WEBEEBLOCKS_RUNTIME_V2 REQUEST 30 RESET");
  const char *reset = webeeblocks_file_broker_receive_text();
  assert(reset != nullptr);
  assert(std::string(reset) == "WEBEEBLOCKS_RUNTIME_V2 REQUEST 30 RESET");
  const std::string response = "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 30 OK";
  webeeblocks_file_broker_send(response.c_str(), static_cast<int>(response.size() + 1));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2");
  process({"WEBEEBLOCKS_RUNTIME_V2 REQUEST 31 OUTCOME progression-precise-movement-v1"});
  assert(sent_text.size() == 1);
  assert(sent_text[0] == "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 31 ERR OUTCOME_UNAVAILABLE");

  // B4-I0: late file messages stay inside the broker; HELLO remains a
  // no-effect liveness reply. A single lazy provider serves multiple requests.
  reset_harness();
  process({
    "WEBEEBLOCKS_RUNTIME_V2 HELLO",
    "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 71 OPEN",
    "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 72 CAPABILITIES",
    "WEBEEBLOCKS_RUNTIME_V2 HELLO"
  });
  assert(provider_creations == 1 && provider_messages == 2);
  assert(provider_destructions == 0);
  assert(sent_text.size() == 4);
  assert(sent_text[0] == "WEBEEBLOCKS_RUNTIME_V2 READY HELLO");
  assert(sent_text[1] == "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 71 ERR FAKE_PROVIDER");
  assert(sent_text[2] == "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 72 ERR FAKE_PROVIDER");
  assert(sent_text[3] == "WEBEEBLOCKS_RUNTIME_V2 READY HELLO");
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  webeeblocks_file_broker_robot_cleanup();
  assert(provider_destructions == 1);

  // Unavailable Qt provider reports a bounded error without swallowing the
  // following flight RESET request or forging successful attempt freshness.
  reset_harness();
  provider_available = false;
  incoming.push_back("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 73 OPEN");
  incoming.push_back("WEBEEBLOCKS_RUNTIME_V2 REQUEST 74 RESET");
  const char *after_unavailable = webeeblocks_file_broker_receive_text();
  assert(after_unavailable && std::strcmp(after_unavailable, "WEBEEBLOCKS_RUNTIME_V2 REQUEST 74 RESET") == 0);
  assert(provider_creations == 1 && provider_messages == 0);
  assert(sent_text.size() == 1 && sent_text[0] ==
    "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 73 ERR UNAVAILABLE");
  const std::string failed_reset = "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 74 ERR RESET_TIMEOUT";
  webeeblocks_file_broker_send(failed_reset.c_str(), static_cast<int>(failed_reset.size() + 1));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");

  // B4-I0: the unavailable-provider fallback must preserve the same strict
  // request-ID grammar as the Qt-free FileBroker parser. Otherwise malformed
  // "73junk" can forge a response for an unrelated pending browser request 73.
  reset_harness();
  provider_available = false;
  incoming.push_back("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 73junk OPEN");
  incoming.push_back("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 2147483648 OPEN");
  incoming.push_back("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 0 OPEN");
  incoming.push_back("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 75 OPEN");
  incoming.push_back("WEBEEBLOCKS_RUNTIME_V2 REQUEST 76 RESET");
  const char *after_malformed_files = webeeblocks_file_broker_receive_text();
  assert(after_malformed_files &&
    std::strcmp(after_malformed_files, "WEBEEBLOCKS_RUNTIME_V2 REQUEST 76 RESET") == 0);
  assert(provider_creations == 4 && provider_messages == 0);
  assert(sent_text.size() == 1);
  assert(sent_text[0] == "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 75 ERR UNAVAILABLE");
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  const std::string no_reset = "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 76 ERR RESET_TIMEOUT";
  webeeblocks_file_broker_send(no_reset.c_str(), static_cast<int>(no_reset.size() + 1));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");

  // A second overlapping RESET B cannot steal pending RESET A, even if B
  // replies first. The first successful matching ID rotates exactly once.
  reset_harness();
  incoming.push_back("WEBEEBLOCKS_RUNTIME_V2 REQUEST 80 RESET");
  incoming.push_back("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 81 OPEN");
  incoming.push_back("WEBEEBLOCKS_RUNTIME_V2 REQUEST 82 RESET");
  const char *reset_a = webeeblocks_file_broker_receive_text();
  assert(reset_a && std::strcmp(reset_a, "WEBEEBLOCKS_RUNTIME_V2 REQUEST 80 RESET") == 0);
  const char *reset_b = webeeblocks_file_broker_receive_text();
  assert(reset_b && std::strcmp(reset_b, "WEBEEBLOCKS_RUNTIME_V2 REQUEST 82 RESET") == 0);
  assert(provider_creations == 1 && provider_messages == 1);
  assert(sent_text.size() == 1 && sent_text[0] ==
    "WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE 81 ERR FAKE_PROVIDER");
  const std::string busy_b = "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 82 ERR BUSY";
  webeeblocks_file_broker_send(busy_b.c_str(), static_cast<int>(busy_b.size() + 1));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  const std::string ok_a = "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 80 OK";
  webeeblocks_file_broker_send(ok_a.c_str(), static_cast<int>(ok_a.size() + 1));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2");
  const std::string stale_ok_b = "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 82 OK";
  webeeblocks_file_broker_send(stale_ok_b.c_str(), static_cast<int>(stale_ok_b.size() + 1));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2");

  // Extra RESET tokens and frames containing embedded NUL are not exact
  // protocol messages and may not rotate an attempt on coincident IDs.
  reset_harness();
  incoming.push_back("WEBEEBLOCKS_RUNTIME_V2 REQUEST 90 RESET extra");
  const char *bad_reset = webeeblocks_file_broker_receive_text();
  assert(bad_reset && std::strcmp(bad_reset, "WEBEEBLOCKS_RUNTIME_V2 REQUEST 90 RESET extra") == 0);
  const std::string fake_ok = "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 90 OK";
  webeeblocks_file_broker_send(fake_ok.c_str(), static_cast<int>(fake_ok.size() + 1));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  incoming.push_back("WEBEEBLOCKS_RUNTIME_V2 REQUEST 91 RESET");
  const char *valid_reset = webeeblocks_file_broker_receive_text();
  assert(valid_reset && std::strcmp(valid_reset, "WEBEEBLOCKS_RUNTIME_V2 REQUEST 91 RESET") == 0);
  const std::string valid_ok = "WEBEEBLOCKS_RUNTIME_V2 RESPONSE 91 OK";
  const std::string embedded_nul = valid_ok + std::string(1, char(0)) + "trailing";
  webeeblocks_file_broker_send(embedded_nul.data(), static_cast<int>(embedded_nul.size()));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  webeeblocks_file_broker_send(valid_ok.c_str(), static_cast<int>(valid_ok.size() + 1));
  assert(custom_data == "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2");

  webeeblocks_file_broker_robot_cleanup();
  std::cout << "PASS native mission broker: COMPLETE preserves exact terminal outcomes; FAILURE scopes non-completion world probes; stale/cross/malformed evidence is not promoted; Reset rotates freshness\n";
  return 0;
}
'''


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="webeeblocks-broker-test-") as temp_name:
        temp = pathlib.Path(temp_name)
        include = temp / "include"
        (include / "webots" / "plugins" / "robot_window").mkdir(parents=True)
        (include / "webots" / "plugins" / "robot_window" / "default.h").write_text("#pragma once\n", encoding="utf-8")
        (include / "webots" / "robot.h").write_text(textwrap.dedent(ROBOT_H), encoding="utf-8")
        (include / "webots" / "supervisor.h").write_text(textwrap.dedent(SUPERVISOR_H), encoding="utf-8")
        probe = temp / "probe.cpp"
        probe.write_text(PROBE, encoding="utf-8")
        executable = temp / "probe"
        command = [
            os.environ.get("CXX", "c++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
            "-I", str(include), "-I", str(CONTROLLER_DIR),
            str(BROKER), str(probe), "-o", str(executable),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        subprocess.run([str(executable)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
