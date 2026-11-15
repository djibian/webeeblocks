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
RANGE_C = ROOT / 'controllers/progression_decision_h_range_probe/progression_decision_h_range_probe.c'
RANGE_MAKE = ROOT / 'controllers/progression_decision_h_range_probe/Makefile'
RANGE_RUN = ROOT / 'tools/ci/run_classroom_decision_h_range.py'

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
/* Reuse the complete physical route with a legitimately admitted
 * higher initial centre height, not a fabricated isolated pad sample. */
static void completed_route_with_origin(wb_dh_mission *m, int attempt,
                                        wb_dh_scene scene, double origin_z) {
  wb_dh_reset(m,(unsigned long long)attempt,scene,origin_z);
  assert(tick(m,0,0,0,origin_z,0,0,0)==WB_DH_WAIT);
  assert(tick(m,1,.2,0,.750,0,0,0)==WB_DH_WAIT);
  assert(m->airborne && m->before_first && m->stage==0);
  pass_first(m,scene==WB_DH_SCENE_A?.50:.85);
  pass_second(m,scene==WB_DH_SCENE_A?.85:.50);
}
/* Real R2025a classroom scene has a 32-ms basicTimeStep. A total of
 * eight consecutive native intervals (0.256s) proves the 0.250s dwell. */
static void finish_stably(wb_dh_mission *m, double t) {
  assert(tick(m,t,1.75,0,.035,0,0,1)==WB_DH_WAIT);
  for (int i=1;i<8;++i)
    assert(tick(m,t+.032*i,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  assert(tick(m,t+.256,1.75,0,.035,0,0,0)==WB_DH_ACHIEVED);
}
int main(void) {
  wb_dh_mission m;
  completed_route(&m,1,WB_DH_SCENE_A);
  finish_stably(&m,8.0);
  assert(tick(&m,9,5,5,5,99,-1,1)==WB_DH_ACHIEVED); // immutable terminal
  completed_route(&m,2,WB_DH_SCENE_B);
  finish_stably(&m,8.0);
  /* Refute hovering falsely treated as LAND after the COMPLETE event.
   * Both variants traverse BOTH physical stations at legal heights; only
   * the final stationary craft's absolute altitude is invalid. The first
   * test even starts at the normal origin: z=0.090 is only 55 mm above it.
   * The second starts legally higher at z=0.075 and hovers at 0.140.
   * On the old relative-only oracle, either case returned ACHIEVED after
   * 8 native 32-ms intervals. That is NOT a grounded landing. */
  for(int v=0;v<2;++v) {
    const wb_dh_scene scene=v==0?WB_DH_SCENE_A:WB_DH_SCENE_B;
    for(int kind=0;kind<2;++kind) {
      const double origin=kind==0?.035:.075;
      const double hover=kind==0?.090:.140;
      completed_route_with_origin(&m,200+10*v+kind,scene,origin);
      assert(hover-origin<=WB_DH_LAND_Z);
      assert(hover>WB_DH_LAND_ABSOLUTE_Z);
      for(int i=0;i<=9;++i)
        assert(tick(&m,8.0+.032*i,1.75,0,hover,0,0,i==0)==WB_DH_WAIT);
      assert(m.landed_since == -1.0);
      assert(tick(&m,9.501,1.75,0,hover,0,0,0)==WB_DH_NOT_ACHIEVED);
      /* An authentic ground landing must still remain admissible after
       * the same legally started and completed route. */
      completed_route_with_origin(&m,240+10*v+kind,scene,origin);
      finish_stably(&m,8.0);
    }
  }
  // Neither A nor B may infer 250 ms of observed stillness from two
  // isolated poses 260 ms apart; a fresh continuous 32-ms series may win.
  for(int v=0;v<2;++v) {
    wb_dh_scene scene=v==0?WB_DH_SCENE_A:WB_DH_SCENE_B;
    completed_route(&m,40+v,scene);
    assert(tick(&m,8,1.75,0,.035,0,0,1)==WB_DH_WAIT);
    assert(tick(&m,8.260,1.75,0,.035,0,0,0)==WB_DH_WAIT);
    assert(m.landed_since == 8.260);
    for(int i=1;i<8;++i)
      assert(tick(&m,8.260+.032*i,1.75,0,.035,0,0,0)==WB_DH_WAIT);
    assert(tick(&m,8.516,1.75,0,.035,0,0,0)==WB_DH_ACHIEVED);
    // One missed native tick (64 ms) invalidates only accumulated dwell,
    // not the entire attempt. Eight fresh observations may still succeed.
    completed_route(&m,50+v,scene);
    assert(tick(&m,8,1.75,0,.035,0,0,1)==WB_DH_WAIT);
    assert(tick(&m,8.032,1.75,0,.035,0,0,0)==WB_DH_WAIT);
    assert(tick(&m,8.096,1.75,0,.035,0,0,0)==WB_DH_WAIT);
    assert(m.landed_since == 8.096);
    for(int i=1;i<8;++i)
      assert(tick(&m,8.096+.032*i,1.75,0,.035,0,0,0)==WB_DH_WAIT);
    assert(tick(&m,8.352,1.75,0,.035,0,0,0)==WB_DH_ACHIEVED);
  }
  // First native observation midway through the route must never count as
  // a legitimate blue start, even if later gate/landing poses look correct.
  for (int v=0; v<2; ++v) {
    wb_dh_scene scene=v==0 ? WB_DH_SCENE_A : WB_DH_SCENE_B;
    wb_dh_reset(&m,(unsigned long long)(70+v),scene,.035);
    assert(tick(&m,1,.570,0,.40,0,0,0)==WB_DH_NOT_ACHIEVED);
    assert(tick(&m,2,.750,0,v==0?.50:.85,0,0,0)==WB_DH_NOT_ACHIEVED);
    assert(tick(&m,8,1.750,0,.035,0,0,1)==WB_DH_NOT_ACHIEVED);
    // Reset is not permanently poisoned: a freshly observed blue start wins.
    completed_route(&m,80+v,scene);
    finish_stably(&m,8.0);
    for (int variant=0; variant<7; ++variant) {
      wb_dh_reset(&m,(unsigned long long)(90+10*v+variant),scene,.035);
      wb_dh_sample invalid = {
        .time=0,.x=0,.y=0,.z=.035,.vx=0,.vy=0,.vz=0,
        .obstacle_contact=0,.completed=0
      };
      if (variant == 0) invalid.x=.090;
      if (variant == 1) invalid.y=.090;
      if (variant == 2) invalid.z=.100;
      if (variant == 3) invalid.vx=.130;
      if (variant == 4) invalid.vy=.130;
      if (variant == 5) invalid.vz=.130;
      if (variant == 6) invalid.completed=1;
      assert(wb_dh_sample_mission(&m,&invalid)==WB_DH_NOT_ACHIEVED);
      assert(wb_dh_sample_mission(&m,&invalid)==WB_DH_NOT_ACHIEVED);
    }
  }
  // An observer attached when the craft is already 0.40 m above the
  // true z=0 floor must not redefine that altitude as its landing ground.
  // This is an independently reset attempt, not a tampered source scene.
  for (int v=0; v<2; ++v) {
    wb_dh_scene scene=v==0 ? WB_DH_SCENE_A : WB_DH_SCENE_B;
    wb_dh_reset(&m,(unsigned long long)(150+v),scene,.400);
    assert(tick(&m,0,0,0,.400,0,0,0)==WB_DH_NOT_ACHIEVED);
    assert(tick(&m,1,.20,0,.800,0,0,0)==WB_DH_NOT_ACHIEVED);
    assert(tick(&m,8,1.75,0,.400,0,0,1)==WB_DH_NOT_ACHIEVED);
    // Grounded attempts still retain their correct H / threshold / landing.
    completed_route(&m,160+v,scene);
    finish_stably(&m,8.0);
  }
  // RESET must clear all mission stages/markers and not inherit a PASS.
  wb_dh_reset(&m,3,WB_DH_SCENE_A,.035);
  assert(!m.stage&&!m.airborne&&!m.before_first&&!m.completion_seen);
  assert(m.landed_since == -1.0);
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
  // An instantaneous valid landing sample must never earn a mission PASS.
  completed_route(&m,26,WB_DH_SCENE_A);
  assert(tick(&m,8,1.75,0,.035,0,0,1)==WB_DH_WAIT);
  assert(tick(&m,8.18,1.75,.20,.035,0,0,0)==WB_DH_WAIT);
  assert(m.landed_since == -1.0); // the whole craft left the pad
  assert(tick(&m,8.25,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  for(int i=1;i<8;++i)
    assert(tick(&m,8.25+.032*i,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  assert(tick(&m,8.506,1.75,0,.035,0,0,0)==WB_DH_ACHIEVED);
  // A late arrival with less than the required continuous dwell fails.
  completed_route(&m,27,WB_DH_SCENE_B);
  assert(tick(&m,8,1.75,.12,.035,0,0,1)==WB_DH_WAIT);
  assert(tick(&m,9.39,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  assert(tick(&m,9.51,1.75,0,.035,0,0,0)==WB_DH_NOT_ACHIEVED);
  // A valid landing that develops motion must restart its dwell clock.
  completed_route(&m,28,WB_DH_SCENE_A);
  assert(tick(&m,8,1.75,0,.035,0,0,1)==WB_DH_WAIT);
  assert(tick(&m,8.16,1.75,0,.035,.30,0,0)==WB_DH_WAIT);
  assert(m.landed_since == -1.0);
  assert(tick(&m,8.30,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  for(int i=1;i<8;++i)
    assert(tick(&m,8.30+.032*i,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  assert(tick(&m,8.556,1.75,0,.035,0,0,0)==WB_DH_ACHIEVED);
  // A truly continuous 0.256-s dwell ending AFTER 1.5 s must lose:
  // first stable sample 9.248 then seven native 32-ms ticks to 9.472.
  completed_route(&m,29,WB_DH_SCENE_B);
  assert(tick(&m,8,1.75,.12,.035,0,0,1)==WB_DH_WAIT);
  assert(tick(&m,9.240,1.75,.12,.035,0,0,0)==WB_DH_WAIT);
  assert(tick(&m,9.248,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  for(int i=1;i<8;++i)
    assert(tick(&m,9.248+.032*i,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  assert(tick(&m,9.504,1.75,0,.035,0,0,0)==WB_DH_NOT_ACHIEVED);
  assert(tick(&m,9.512,1.75,0,.035,0,0,0)==WB_DH_NOT_ACHIEVED);
  // At EXACT 1.500 s, equality overrides a simultaneous 0.252-s dwell.
  completed_route(&m,33,WB_DH_SCENE_A);
  assert(tick(&m,8,1.75,.12,.035,0,0,1)==WB_DH_WAIT);
  assert(tick(&m,9.248,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  for(int i=1;i<8;++i)
    assert(tick(&m,9.248+.032*i,1.75,0,.035,0,0,0)==WB_DH_WAIT);
  assert(tick(&m,9.500,1.75,0,.035,0,0,0)==WB_DH_NOT_ACHIEVED);
  // Existing timely success (8.256), motion/pad reset and RESET persist.
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
        self.assertIn('WB_DH_LAND_DWELL_SEC 0.250', content)
        self.assertIn('WB_DH_LAND_ABSOLUTE_Z 0.070', content)
        self.assertIn('s->z - m->origin_z <= WB_DH_LAND_Z &&', content)
        self.assertIn('s->z <= WB_DH_LAND_ABSOLUTE_Z', content)
        self.assertIn('WB_DH_MAX_OBSERVATION_GAP_SEC 0.048', content)
        self.assertIn('s->time - m->last_time > WB_DH_MAX_OBSERVATION_GAP_SEC', content)
        self.assertIn('WB_DH_START_XY_TOL 0.080', content)
        self.assertIn('WB_DH_START_Z_TOL 0.060', content)
        self.assertIn('WB_DH_START_MAX_SPEED 0.120', content)
        self.assertIn('WB_DH_BLUE_GROUND_Z 0.035', content)
        self.assertIn('WB_DH_BLUE_GROUND_Z_TOL 0.060', content)
        self.assertIn('m->landed_since = -1.0', content)
        self.assertIn('s->time - m->landed_since >= WB_DH_LAND_DWELL_SEC', content)
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
        self.assertIn('WEBEEBLOCKS_DECISION_H_FIRST_SAMPLE', observer)
        self.assertIn('WEBEEBLOCKS_DECISION_H_VERDICT_SAMPLE', observer)
        self.assertIn('WEBEEBLOCKS_DECISION_H_CONTACT_UNAVAILABLE', observer)
        self.assertIn('WEBEEBLOCKS_DECISION_H_CONTACT_NONFLOOR', observer)
        self.assertIn('WEBEEBLOCKS_DECISION_H_READY', observer)
        self.assertIn('WEBEEBLOCKS_ACTIVITY_OUTCOME_V1', observer)
        range_source = RANGE_C.read_text(encoding='utf-8')
        range_make = RANGE_MAKE.read_text(encoding='utf-8')
        range_run = RANGE_RUN.read_text(encoding='utf-8')
        self.assertIn('wb_distance_sensor_get_value(front)', range_source)
        self.assertIn('wb_supervisor_field_set_sf_vec3f(position_field, pose)', range_source)
        self.assertIn('C_SOURCES = progression_decision_h_range_probe.c', range_make)
        self.assertIn('A4_RANGE_REAL_PASS', range_run)
        self.assertIn('b - a > 0.40', range_run)
        self.assertNotIn('wb_motor_set_', range_source)
        self.assertNotIn('wb_supervisor_node_set_velocity', range_source)
        for forbidden in ('wb_motor_set_', 'wb_supervisor_node_set_velocity',
                          'radio_link', 'crazyflie_runtime_v2/Makefile'):
            self.assertNotIn(forbidden, observer)


if __name__ == '__main__':
    unittest.main()
