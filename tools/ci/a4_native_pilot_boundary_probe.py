#!/usr/bin/env python3
"""CI-only, bounded native-pilot step/WWI seam probe for the A4 R2025a witness.

Temporarily instrument the checkout's source while building only the school
controller, then restore the source byte for byte. This is neither a product
controller change nor a flight, WWI, safety or acceptance oracle.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'
BACKUP = ROOT / 'ci-artifacts/.a4-pilot-probe-source-backup.c'
MANIFEST = ROOT / 'ci-artifacts/progression-decision-h-blockly/pilot-boundary-probe.json'
MARKER = 'A4_CI_PILOT_STEP_ENTER'

PROBE = r'''
/* CI diagnostic only, inserted into the temporary A4 school build.
 * Monotonic wall time is read without an additional Webots/Supervisor call.
 * No response is generated and no watchdog or PID state is modified.
 */
#include <time.h>
#include <stdint.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
static double a4_ci_wall_time(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
    return -1.0;
  return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

/* Diagnostic circular flight recorder: no per-step stdio or Webots calls.
 * A dedicated file per process preserves the first-class last-entered seam.
 * Phase: 1 step enter, 2 step return, 3 receive enter, 4 receive return,
 * 5 parsed request, 6 activate, 7 send enter, 8 send return, 9 PID state.
 * This is evidence only, never an oracle or a watchdog.
 */
#define A4_CI_RING_CAP 16384u
typedef struct {
  uint64_t seq;
  double wall, sim, z, target_z, vz, stable_since;
  int phase, id, command;
} a4_ci_event_t;
typedef struct {
  uint64_t next;
  uint32_t version, capacity;
  a4_ci_event_t events[A4_CI_RING_CAP];
} a4_ci_ring_t;
static a4_ci_ring_t *a4_ci_ring = NULL;
static int a4_ci_ring_attempted = 0;
static double a4_ci_current_sim = -1.0;
static void a4_ci_record(int phase, int id, int command,
                         double sim, double z, double target_z,
                         double vz, double stable_since) {
  if (!a4_ci_ring_attempted) {
    a4_ci_ring_attempted = 1;
    char path[256];
    snprintf(path, sizeof(path),
             "/workspace/ci-artifacts/progression-decision-h-blockly/pilot-seams-%ld.bin",
             (long)getpid());
    const int fd = open(path, O_RDWR | O_CREAT | O_EXCL, 0600);
    if (fd >= 0) {
      if (ftruncate(fd, (off_t)sizeof(a4_ci_ring_t)) == 0) {
        void *mapped = mmap(NULL, sizeof(a4_ci_ring_t),
                            PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        if (mapped != MAP_FAILED) {
          a4_ci_ring = (a4_ci_ring_t *)mapped;
          a4_ci_ring->version = 1;
          a4_ci_ring->capacity = A4_CI_RING_CAP;
        }
      }
      close(fd);
    }
    if (!a4_ci_ring)
      fprintf(stderr, "A4_CI_PILOT_RING_UNAVAILABLE pid=%ld\n", (long)getpid());
  }
  if (!a4_ci_ring)
    return;
  const uint64_t seq = a4_ci_ring->next;
  a4_ci_event_t *e = &a4_ci_ring->events[seq % A4_CI_RING_CAP];
  e->seq = seq;
  e->wall = a4_ci_wall_time();
  e->sim = sim;
  e->z = z;
  e->target_z = target_z;
  e->vz = vz;
  e->stable_since = stable_since;
  e->phase = phase;
  e->id = id;
  e->command = command;
  __sync_synchronize();
  a4_ci_ring->next = seq + 1;
}
static const char *a4_ci_receive_text(int id, int command) {
  a4_ci_record(3, id, command, a4_ci_current_sim, NAN, NAN, NAN, -1.0);
  const char *result = wb_robot_wwi_receive_text();
  a4_ci_record(4, id, command, a4_ci_current_sim, NAN, NAN, NAN, -1.0);
  return result;
}
static void a4_ci_send_text(const char *text) {
  int id = -1;
  (void)sscanf(text, "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d", &id);
  a4_ci_record(7, id, -1, a4_ci_current_sim, NAN, NAN, NAN, -1.0);
  wb_robot_wwi_send_text(text);
  a4_ci_record(8, id, -1, a4_ci_current_sim, NAN, NAN, NAN, -1.0);
}

static int a4_ci_pilot_step(int step, int id, int command, double prior_sim) {
  static double last_wall = -1.0;
  static int last_id = -999;
  static int last_command = -999;
  static unsigned samples = 0;
  const double wall = a4_ci_wall_time();
  const int record = samples < 600 &&
    (samples == 0 || id != last_id || command != last_command ||
     (wall >= 0.0 && wall - last_wall >= 1.0));
  if (record) {
    ++samples;
    last_wall = wall;
    last_id = id;
    last_command = command;
    fprintf(stderr, "A4_CI_PILOT_STEP_ENTER wall=%.3f sim_last=%.3f id=%d cmd=%d\n",
            wall, prior_sim, id, command);
    fflush(stderr);
  }
  a4_ci_record(1, id, command, prior_sim, NAN, NAN, NAN, -1.0);
  const int result = wb_robot_step(step);
  a4_ci_record(2, id, command, prior_sim, NAN, NAN, NAN, -1.0);
  if (record) {
    fprintf(stderr, "A4_CI_PILOT_STEP_RETURN wall=%.3f sim_last=%.3f id=%d result=%d\n",
            a4_ci_wall_time(), prior_sim, id, result);
    fflush(stderr);
  }
  return result;
}
static void a4_ci_mark(const char *phase, int id, int kind,
                       double sim, double z, double target_z) {
  a4_ci_record(strcmp(phase, "receive") == 0 ? 5 : 6,
               id, kind, sim, z, target_z, NAN, -1.0);
  static unsigned samples = 0;
  if (samples++ >= 160)
    return;
  fprintf(stderr,
          "A4_CI_PILOT_BOUNDARY phase=%s wall=%.3f sim=%.3f id=%d kind=%d z=%.6f target_z=%.6f\n",
          phase, a4_ci_wall_time(), sim, id, kind, z, target_z);
  fflush(stderr);
}
'''

REPLACEMENTS = (
    ('#include "activity_scene.h"\n',
     '#include "activity_scene.h"\n' + PROBE),
    ('  while (wb_robot_step(step) != -1) {',
     '  while (a4_ci_pilot_step(step, active_id, (int)command, previous_time) != -1) {'),
    ('  wb_robot_wwi_send_text(text);\n',
     '  a4_ci_send_text(text);\n'),
    ('    while ((message = wb_robot_wwi_receive_text()) != NULL) {',
     '    while ((message = a4_ci_receive_text(active_id, (int)command)) != NULL) {'),
    ('    const double now = wb_robot_get_time();\n',
     '    const double now = wb_robot_get_time();\n'
     '    a4_ci_current_sim = now;\n'),
    ('    previous_time = now;\n    previous_x = x;\n    previous_y = y;\n    previous_z = z;\n  }\n\n  stop_motors',
     '    a4_ci_record(9, active_id, (int)command, now, z, target_z, vz, stable_since);\n'
     '    previous_time = now;\n    previous_x = x;\n    previous_y = y;\n    previous_z = z;\n  }\n\n  stop_motors'),
    ('      request_t request = parse_request(message);\n',
     '      request_t request = parse_request(message);\n'
     '      a4_ci_mark("receive", request.id, (int)request.kind, now, z, target_z);\n'),
    ('        command = CMD_TAKEOFF;\n        stable_since = -1.0;',
     '        command = CMD_TAKEOFF;\n'
     '        a4_ci_mark("activate", active_id, (int)command, now, z, target_z);\n'
     '        stable_since = -1.0;'),
    ('        command = CMD_MOVE;\n        stable_since = -1.0;',
     '        command = CMD_MOVE;\n'
     '        a4_ci_mark("activate", active_id, (int)command, now, z, target_z);\n'
     '        stable_since = -1.0;'),
    ('        command = CMD_VERTICAL;\n        stable_since = -1.0;',
     '        command = CMD_VERTICAL;\n'
     '        a4_ci_mark("activate", active_id, (int)command, now, z, target_z);\n'
     '        stable_since = -1.0;'),
)


def instrument(text: str) -> str:
    if MARKER in text:
        raise ValueError('CI probe already present: refuse duplicate instrumentation')
    for old, new in REPLACEMENTS:
        if text.count(old) != 1:
            raise ValueError('CI probe source anchor missing or ambiguous: ' + old[:65])
        text = text.replace(old, new, 1)
    for required in ('#define ACTION_TIMEOUT 25.0',
                     '#define RESET_TIMEOUT 5.0', 'response_ok(active_id)',
                     'response_error(active_id, "UNSAFE_OR_TIMEOUT")'):
        if required not in text:
            raise ValueError('CI probe cannot prove native safety source invariant: ' + required)
    return text


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def install() -> None:
    if BACKUP.exists():
        raise FileExistsError('refusing to overwrite an existing CI source backup')
    original = SOURCE.read_text(encoding='utf-8')
    patched = instrument(original)
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(original, encoding='utf-8')
    SOURCE.write_text(patched, encoding='utf-8')
    print('A4_CI_PILOT_PROBE_INSTALLED original=' + digest(original) +
          ' instrumented=' + digest(patched), flush=True)


def restore() -> None:
    if not BACKUP.exists():
        if MARKER in SOURCE.read_text(encoding='utf-8'):
            raise RuntimeError('missing backup for instrumented source')
        return
    original = BACKUP.read_text(encoding='utf-8')
    actual = SOURCE.read_text(encoding='utf-8')
    expected = instrument(original)
    if actual not in (original, expected):
        raise RuntimeError('refusing to restore a concurrently modified source')
    if actual == expected:
        SOURCE.write_text(original, encoding='utf-8')
    if SOURCE.read_text(encoding='utf-8') != original:
        raise RuntimeError('CI native source restoration failed')
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        'schema': 'a4-pilot-seam-probe-v1',
        'purpose': 'CI-only diagnostic, never an acceptance or safety oracle',
        'source_restored': True,
        'source_sha256': digest(original),
        'instrumented_sha256': digest(expected),
        'step_sample_cap': 600,
        'boundary_sample_cap': 160,
        'seam_ring_cap': 16384,
        'seam_ring_phases': {'1':'step-enter','2':'step-return',
                             '3':'wwi-receive-enter','4':'wwi-receive-return',
                             '5':'parsed-request','6':'action-activate',
                             '7':'wwi-send-enter','8':'wwi-send-return',
                             '9':'post-pid-state'},
        'seam_ring_format': 'native little-endian LP64 C struct: header uint64 next, uint32 version/capacity; records: uint64 seq; six double wall,sim,z,target_z,vz,stable_since; int phase,id,command; 4 trailing padding bytes',
    }, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    BACKUP.unlink()
    print('A4_CI_PILOT_PROBE_RESTORED ' + digest(original), flush=True)


def selftest() -> None:
    original = SOURCE.read_text(encoding='utf-8')
    patched = instrument(original)
    assert patched.count(MARKER) == 1
    assert patched.count('a4_ci_pilot_step(step, active_id, (int)command, previous_time)') == 1
    assert patched.count('a4_ci_mark("receive",') == 1
    assert patched.count('a4_ci_mark("activate",') == 3
    assert patched.count('wb_robot_step(step)') == original.count('wb_robot_step(step)')
    assert patched.count('wb_robot_wwi_send_text(text)') == original.count('wb_robot_wwi_send_text(text)')
    assert patched.count('wb_robot_wwi_receive_text()') == original.count('wb_robot_wwi_receive_text()')
    assert patched.count('a4_ci_send_text(text)') == 1
    assert patched.count('a4_ci_receive_text(active_id, (int)command)') == 1
    assert patched.count('a4_ci_record(9, active_id, (int)command, now, z, target_z, vz, stable_since)') == 1
    assert patched.count('A4_CI_RING_CAP 16384u') == 1
    assert 'MAP_SHARED' in patched
    assert 'phase, id, command' in patched
    assert patched.count('response_ok(active_id)') == original.count('response_ok(active_id)')
    assert patched.count('response_error(active_id, "UNSAFE_OR_TIMEOUT")') == original.count('response_error(active_id, "UNSAFE_OR_TIMEOUT")')
    assert patched.count('#define ACTION_TIMEOUT 25.0') == 1
    try:
        instrument(patched)
    except ValueError:
        pass
    else:
        raise AssertionError('double instrumentation must be rejected')
    assert SOURCE.read_text(encoding='utf-8') == original
    print('A4_CI_PILOT_PROBE_SELFTEST_OK ' + digest(original), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('install', 'restore', 'selftest'):
        raise SystemExit('usage: a4_native_pilot_boundary_probe.py install|restore|selftest')
    {'install': install, 'restore': restore, 'selftest': selftest}[sys.argv[1]]()
