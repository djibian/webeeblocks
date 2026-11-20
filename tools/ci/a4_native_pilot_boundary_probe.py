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
static double a4_ci_wall_time(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
    return -1.0;
  return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
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
  const int result = wb_robot_step(step);
  if (record) {
    fprintf(stderr, "A4_CI_PILOT_STEP_RETURN wall=%.3f sim_last=%.3f id=%d result=%d\n",
            a4_ci_wall_time(), prior_sim, id, result);
    fflush(stderr);
  }
  return result;
}
static void a4_ci_mark(const char *phase, int id, int kind,
                       double sim, double z, double target_z) {
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
