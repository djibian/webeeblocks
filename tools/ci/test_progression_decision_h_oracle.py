#!/usr/bin/env python3
"""Execute real compiled C Activity 4 oracle against positive and negative traces.

No simulated-Webots or authentic student sensor PASS is inferred. This is a
strictly isolated C core: native Webots scene/craft/contact attestation, pupil
Blockly/AST, selected native variant, front ray, RESET and Save/Open are later
qualification steps and cannot be replaced with source tests.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = ROOT / 'controllers/progression_decision_h_v1'
CORE = CORE_DIR / 'decision_core.h'
OBSERVER = CORE_DIR / 'progression_decision_h_v1.c'
MAKEFILE = CORE_DIR / 'Makefile'

DRIVER = r'''
#include "decision_core.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static wb_dh_verdict tick(wb_dh_mission *m, double t, double x, double y,
                          double z, double vx, int contact, int done) {
  wb_dh_sample s = {.time=t,.x=x,.y=y,.z=z,.vx=vx,.vy=0,.vz=0,
                    .obstacle_contact=contact,.completed=done};
  return wb_dh_sample_mission(m,&s);
}
static void takeoff(wb_dh_mission *m, int attempt, wb_dh_scene scene) {
  wb_dh_reset(m,(unsigned long long)attempt,scene,.035);
  assert(tick(m,0,0,0,.035,0,0,0)==WB_DH_WAIT);
  assert(tick(m,1,.2,0,.750,0,0,0)==WB_DH_WAIT);
  assert(m->airborne && m->before_first && m->stage==0);
}
static void pass_first(wb_dh_mission *m, double z) {
  assert(tick(m,2,.55,0,z,0,0,0)==WB_DH_WAIT);
  assert(tick(m,3,.75,0,z,0,0,0)==WB_DH_WAIT);
  assert(m->stage==1);
  assert(tick(m,4,.93,0,z,0,0,0)==WB_DH_WAIT);
  assert(m->stage==2);
}
static void pass_second(wb_dh_mission *m, double z) {
  assert(tick(m,5,1.11,0,z,0,0,0)==WB_DH_WAIT);
  assert(m->before_second);
  assert(tick(m,6,1.35,0,z,0,0,0)==WB_DH_WAIT);
  assert(m->stage==3);
  assert(tick(m,7,1.55,0,z,0,0,0)==WB_DH_WAIT);
  assert(m->stage==4);
}
static void completed_route(wb_dh_mission *m, int attempt, wb_dh_scene scene) {
  takeoff(m,attempt,scene);
  pass_first(m,scene==WB_DH_SCENE_A?.50:.85);
  pass_second(m,scene==WB_DH_SCENE_A?.85:.50);
}
int main(void) {
  wb_dh_mission m;
  completed_route(&m,1,WB_DH_SCENE_A);
  assert(tick(&m,8,1.75,0,.035,0,0,1)==WB_DH_ACHIEVED);
  assert(tick(&m,9,5,5,5,99,-1,1)==WB_DH_ACHIEVED); // immutable terminal
  completed_route(&m,2,WB_DH_SCENE_B);
  assert(tick(&m,8,1.75,0,.035,0,0,1)==WB_DH_ACHIEVED);
  // RESET must clear all mission stages/markers and not inherit a PASS.
  wb_dh_reset(&m,3,WB_DH_SCENE_A,.035);
  assert(!m.stage&&!m.airborne&&!m.before_first&&!m.completion_seen);
  assert(tick(&m,0,1.75,0,.035,0,0,1)==WB_DH_NOT_ACHIEVED);
  // Wrong blind constant altitude: near gate is H in A, raised threshold in B.
  takeoff(&m,4,WB_DH_SCENE_A);
  assert(tick(&m,2,.75,0,.85,0,0,0)==WB_DH_NOT_ACHIEVED);
  takeoff(&m,5,WB_DH_SCENE_B);
  assert(tick(&m,2,.75,0,.50,0,0,0)==WB_DH_NOT_ACHIEVED);
  // 1.20m high blind overflight remains a real geometric bypass, not a PASS.
  takeoff(&m,6,WB_DH_SCENE_A);
  assert(tick(&m,2,.75,0,1.20,0,0,0)==WB_DH_NOT_ACHIEVED);
  takeoff(&m,7,WB_DH_SCENE_B);
  assert(tick(&m,2,.75,0,1.20,0,0,0)==WB_DH_NOT_ACHIEVED);
  // Even with a correct first gate, wrong height at the far gate is rejected.
  takeoff(&m,8,WB_DH_SCENE_A);
  pass_first(&m,.50);
  assert(tick(&m,5,1.35,0,.50,0,0,0)==WB_DH_NOT_ACHIEVED);
  takeoff(&m,9,WB_DH_SCENE_B);
  pass_first(&m,.85);
  assert(tick(&m,5,1.35,0,.85,0,0,0)==WB_DH_NOT_ACHIEVED);
  // Never certify skip, sideways bypass, unknown contacts, or contact.
  takeoff(&m,10,WB_DH_SCENE_A);
  assert(tick(&m,2,1.75,0,.035,0,0,1)==WB_DH_NOT_ACHIEVED);
  takeoff(&m,11,WB_DH_SCENE_A);
  assert(tick(&m,2,.55,.35,.5,0,0,0)==WB_DH_NOT_ACHIEVED);
  takeoff(&m,12,WB_DH_SCENE_A);
  assert(tick(&m,2,.30,0,.5,0,-1,0)==WB_DH_NOT_ACHIEVED);
  takeoff(&m,13,WB_DH_SCENE_B);
  assert(tick(&m,2,.30,0,.5,0,1,0)==WB_DH_NOT_ACHIEVED);
  // Completion at right pad but only one obstacle is not achievement.
  takeoff(&m,14,WB_DH_SCENE_A);
  pass_first(&m,.50);
  assert(tick(&m,5,1.75,0,.035,0,0,1)==WB_DH_NOT_ACHIEVED);
  // Landing must be stationary, entire craft on the pad, and below 7 cm.
  for(int k=0;k<4;++k) {
    completed_route(&m,20+k,WB_DH_SCENE_B);
    double x=k==0?1.85:1.75;
    double y=k==1?.12:0;
    double z=k==2?.25:.035;
    double vx=k==3?.35:0;
    assert(tick(&m,8,x,y,z,vx,0,1)==WB_DH_WAIT);
    assert(tick(&m,10,x,y,z,vx,0,0)==WB_DH_NOT_ACHIEVED);
  }
  // Wrong chronology, unknown observations, invalid scene, repeated timestamp.
  takeoff(&m,30,WB_DH_SCENE_A);
  assert(tick(&m,1,.2,0,.75,0,0,0)==WB_DH_NOT_ACHIEVED);
  takeoff(&m,31,WB_DH_SCENE_A);
  assert(tick(&m,2,.20,0,NAN,0,0,0)==WB_DH_NOT_ACHIEVED);
  wb_dh_reset(&m,32,(wb_dh_scene)99,.035);
  assert(tick(&m,0,0,0,.035,0,0,0)==WB_DH_NOT_ACHIEVED);
  assert(!wb_dh_clearance(.75,.85,.75,1));
  assert(!wb_dh_clearance(.75,.50,.75,0));
  assert(wb_dh_clearance(.75,.50,.75,1));
  assert(wb_dh_clearance(.75,.85,.75,0));
  assert(!strcmp(WB_DH_ORACLE,"progression-decision-h-v1"));
  puts("PASS A4 native C core: both variants, directed under-H/over-curb, negatives, RESET");
  return 0;
}
'''

class DecisionHOracleTests(unittest.TestCase):
    def test_compiled_c_both_variants_and_adversaries(self):
        cc = shutil.which('cc')
        self.assertIsNotNone(cc, 'a real C compiler is required, no mock fallback')
        with tempfile.TemporaryDirectory(prefix='wb-a4-c-oracle-') as temp:
            source = Path(temp) / 'driver.c'
            binary = Path(temp) / 'driver'
            source.write_text(DRIVER, encoding='utf-8')
            build = subprocess.run(
                [cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(CORE_DIR), str(source), '-lm', '-o', str(binary)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            outcome = subprocess.run(
                [str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)
            self.assertIn('PASS A4 native C core:', outcome.stdout)

    def test_separate_evaluator_no_real_flight_binary(self):
        content = CORE.read_text(encoding='utf-8')
        self.assertIn('WB_DH_ORACLE "progression-decision-h-v1"', content)
        self.assertIn('WB_DH_SCENE_A', content)
        self.assertIn('WB_DH_SCENE_B', content)
        self.assertIn('wb_dh_sample_mission', content)
        self.assertNotIn('radio_link', content)
        self.assertNotIn('#include <webots/', content)
        observer = OBSERVER.read_text(encoding='utf-8')
        makefile = MAKEFILE.read_text(encoding='utf-8')
        self.assertIn('C_SOURCES = progression_decision_h_v1.c', makefile)
        self.assertIn('resources/Makefile.include', makefile)
        self.assertIn('WB_DH_CHILDREN 29', observer)
        self.assertIn('verify_scene(&scene)', observer)
        self.assertIn('valid_observer(group)', observer)
        self.assertIn('wb_supervisor_node_get_contact_points', observer)
        self.assertIn('wb_supervisor_node_enable_contact_points_tracking', observer)
        self.assertIn('wb_dh_sample_mission(&mission, &sample)', observer)
        self.assertIn('parse_attempt(data, &attempt)', observer)
        self.assertIn('parse_completion(data, mission.attempt)', observer)
        self.assertIn('WEBEEBLOCKS_DECISION_H_FATAL', observer)
        self.assertIn('WEBEEBLOCKS_DECISION_H_READY', observer)
        self.assertIn('WEBEEBLOCKS_ACTIVITY_OUTCOME_V1', observer)
        for forbidden in ('wb_motor_set_', 'wb_supervisor_node_set_velocity',
                          'radio_link', 'crazyflie_runtime_v2/Makefile'):
            self.assertNotIn(forbidden, observer)


if __name__ == '__main__':
    unittest.main()
