#!/usr/bin/env python3
"""Compile the production native broker against injected Webots transport stubs.

The probe locks the mission-channel invariant that COMPLETE must not erase an
already-published terminal result for the current attempt and oracle, while
stale, malformed, cross-oracle, or invalid results remain non-authoritative.
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

extern "C" WbFileBroker *wb_file_broker_create_qt(void) { return nullptr; }
extern "C" void wb_file_broker_destroy(WbFileBroker *) {}
extern "C" const char *wb_file_broker_handle_message(WbFileBroker *, const char *) { return nullptr; }

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

  webeeblocks_file_broker_robot_cleanup();
  std::cout << "PASS native mission broker: COMPLETE preserves only current matching terminal outcomes; stale/cross/malformed evidence is not promoted; Reset rotates freshness\n";
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
