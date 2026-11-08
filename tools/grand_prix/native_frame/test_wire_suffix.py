#!/usr/bin/env python3
"""Host-only regression of the actual native frame decoder added by the patch.

No simulated or physical flight, Webots execution, GUI or end-to-end wire
transport is qualified by this isolated C decoder test.
"""
from pathlib import Path
import os
import subprocess
import tempfile

PATCH = Path(__file__).with_name("webots-r2025a.patch")


def decoder(patch):
    start = "+static void read_physics_frame(WbRequest *r) {"
    if patch.count(start) != 1:
        raise AssertionError("expected exactly one added decoder")
    lines = patch.splitlines()
    offset = lines.index(start)
    body = []
    for line in lines[offset:]:
        if not line.startswith("+") or line.startswith("+++"):
            raise AssertionError("decoder no longer wholly added by patch")
        body.append(line[1:])
        if line == "+}":
            return "\n".join(body) + "\n"
    raise AssertionError("decoder not closed")


def assert_terminal_frame(patch):
    a = patch.split("diff --git a/src/webots/control/WbController.cpp", 1)[1]
    a = a.split("diff --git", 1)[0]
    positions = [
        a.index("mRobot->dispatchAnswer(stream);"),
        a.index("mRobot->writeImmediateAnswer(stream);"),
        a.index("mRobot->supervisorUtilities()->writePhysicsFrame(stream,"),
        a.index("int size = streamSizeManagement(stream);"),
    ]
    if positions != sorted(positions) or a.count("->writePhysicsFrame(") != 1:
        raise AssertionError("experimental reply must be the terminal wire suffix")


C_BEGIN = r"""
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define WB_SUPERVISOR_PHYSICS_FRAME_VERSION 1
#define WB_SUPERVISOR_PHYSICS_FRAME_MAX_CONTACTS 128
typedef struct { double point[3]; int32_t node_id; } WbContactPoint;
typedef struct {
  double time_ms;
  unsigned char incarnation[16];
  int32_t supervisor_id, solid_id;
  double position[3], orientation[9], velocity[6];
  int32_t contact_count;
  WbContactPoint contacts[128];
} WbSupervisorPhysicsFrame;
typedef struct { unsigned char data[4096]; int pointer, size; } WbRequest;
static int physics_frame_sent_id;
static bool physics_frame_ready;
static WbSupervisorPhysicsFrame physics_frame;
static struct { int id; } node = {7}, *self_node_ref = &node;
static int request_get_size(WbRequest *r) { return r->size; }
static int request_get_position(WbRequest *r) { return r->pointer; }
static void request_set_position(WbRequest *r, int i) { r->pointer = i; }
static void *request_read_data(WbRequest *r, int n) {
  if (n < 0 || n > r->size - r->pointer) abort();
  void *p = r->data + r->pointer; r->pointer += n; return p;
}
static bool robot_is_immediate_message(void) { return false; }
"""

C_END = r"""
static void append(WbRequest *r, const void *p, int n) {
  if (n < 0 || r->size + n > (int)sizeof(r->data)) abort();
  memcpy(r->data + r->size, p, n); r->size += n;
}
static void i32(WbRequest *r, int32_t x) { append(r, &x, sizeof(x)); }
static void check(int ok, const char *msg) {
  if (!ok) { fprintf(stderr, "FAIL %s\n", msg); exit(1); }
}
static void probe(int32_t version, int32_t count, int truncate, int extra, int expect) {
  WbRequest r = {{0}, 0, 0};
  const unsigned char ordinary = 0x5a, poison = 0x42, incarnation[16] = {1};
  append(&r, &ordinary, 1); i32(&r, version); i32(&r, count);
  if (count >= 0 && count <= 128) {
    append(&r, incarnation, 16);
    i32(&r, 7); i32(&r, 8);
    const double scalars[19] = {8};
    append(&r, scalars, sizeof(scalars));
    for (int i = 0; i < count; ++i) {
      const double xyz[3] = {1, 2, 3};
      append(&r, xyz, sizeof(xyz)); i32(&r, 15);
    }
  }
  check(truncate >= 0 && truncate <= r.size - 1, "invalid fixture truncation");
  r.size -= truncate;
  while (extra--) append(&r, &poison, 1);
  r.pointer = 1; // The ordinary prefix was already consumed by its own handler.
  physics_frame_sent_id = 8;
  physics_frame_ready = true;
  read_physics_frame(&r);
  check(r.pointer == r.size, "decoder left bytes unread");
  check(r.data[0] == ordinary, "preceding ordinary response was corrupted");
  check(physics_frame_ready == !!expect, "malformed suffix was accepted");
  check(physics_frame_sent_id == 0, "outstanding request not consumed");
  if (expect)
    check(physics_frame.supervisor_id == 7 && physics_frame.solid_id == 8,
          "valid frame identity not decoded");
}
int main(void) {
  probe(1, 0, 0, 0, 1);    // Valid zero-contact frame
  probe(1, 1, 0, 0, 1);    // Valid one-contact frame
  probe(1, -1, 0, 0, 0);   // Native refusal
  probe(99, 0, 0, 0, 0);   // Unsupported format
  probe(1, -2, 0, 0, 0);   // Invalid negative count
  probe(1, 129, 0, 0, 0); // Exceeds contact bound
  probe(1, 0, 1, 0, 0);   // Truncated payload
  probe(1, 1, 6, 0, 0);   // Truncated contact
  probe(1, 0, 0, 1, 0);   // Extra payload
  probe(1, -1, 0, 1, 0);  // Refusal with unexpected bytes
  puts("PASS: terminal C frame decoder rejects malformed suffixes");
  return 0;
}
"""


def main():
    patch = PATCH.read_text(encoding="utf-8")
    assert_terminal_frame(patch)
    with tempfile.TemporaryDirectory(prefix="webeeblocks-gp-wire-") as tmp:
        source = Path(tmp) / "decoder.c"
        binary = Path(tmp) / "decoder"
        source.write_text(C_BEGIN + decoder(patch) + C_END, encoding="utf-8")
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra",
                        "-Werror", "-O2", str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
