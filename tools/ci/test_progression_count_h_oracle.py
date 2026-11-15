#!/usr/bin/env python3
"""Native-compiled adversarial Activity 6 behavioral oracle checks.

This does not stand in for real Webots R2025a physics, authentic rear/front
raycasts, or Blockly/AST → interpreter → simulation / Save-Open qualification.
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "controllers/progression_count_h_v1/count_core.h"
DRIVER = r'''
#include "count_core.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

static wb_count_sample s(double t, double x, double y, double z,
                         double speed, int contact, int done) {
  wb_count_sample q={t,x,y,z,speed,0.0,0.0,contact,done};
  return q;
}
static wb_count_verdict feed_step(wb_count_mission *m, double *clock,
                                  double dt,double x,double y,double z,
                                  double speed,int contact,int done) {
  *clock += dt;
  const wb_count_sample q=s(*clock,x,y,z,speed,contact,done);
  return wb_count_sample_mission(m,&q);
}
static wb_count_verdict feed(wb_count_mission *m, double *clock,
                             double x, double y, double z,
                             double speed, int contact, int done) {
  return feed_step(m,clock,0.10,x,y,z,speed,contact,done);
}

/* Synthetic continuous route; not a claimed physical Crazyflie flight. */
static wb_count_verdict route(unsigned n, unsigned long long attempt,
                              int wrong_pad, int skip_center,
                              int high, int side, int early_done,
                              int missing_contact, int collision) {
  wb_count_mission m;
  wb_count_reset(&m,attempt,n,0.0);
  double clock=0.0;
  for(int i=0;i<=250;i++) {
    const double x=-1.40+i*0.01152; /* reaches exactly 1.48 */
    if(skip_center && n==1 && fabs(x+0.850)<0.10) continue;
    const int at_gate=fabs(x-wb_count_gate_x(0))<WB_COUNT_GATE_ENVELOPE;
    const double z=(high && at_gate)?0.95:0.40;
    const double y=(side && at_gate)?0.28:0.0;
    const int invalid=(missing_contact && i==2)?-1:((collision && i==2)?1:0);
    const int done=early_done && i==2;
    const wb_count_verdict result=feed(&m,&clock,x,y,z,0.10,invalid,done);
    if(result==WB_COUNT_NOT_ACHIEVED) return result;
  }
  const double destination=wrong_pad?wb_count_target_y(n==1?2:1):wb_count_target_y(n);
  /* The final landing involves lateral movement only after all gates. */
  for(int i=1;i<=55;i++) {
    const double y=destination*i/55.0;
    if(feed(&m,&clock,1.48,y,0.40,0.10,0,0)!=WB_COUNT_WAIT)
      return m.verdict;
  }
  /* Completion is a single event. One low-speed sample cannot establish
   * sustained landing, and subsequent samples need not repeat completion. */
  const wb_count_verdict first=feed(&m,&clock,1.48,destination,0.02,0.0,0,1);
  if(first!=WB_COUNT_WAIT) return first;
  /* Preserve each actual 32-ms landing observation, even on wrong pad;
   * the wrong-pad negative must still reach the 1.5-s deadline. */
  for(int k=0;k<55;k++) {
    const wb_count_verdict v=
      feed_step(&m,&clock,.032,1.48,destination,0.02,0.0,0,0);
    if(v!=WB_COUNT_WAIT) return v;
  }
  return m.verdict;
}

static void test_successes(void) {
  for(unsigned n=1;n<=3;n++)
    assert(route(n,700+n,0,0,0,0,0,0,0)==WB_COUNT_ACHIEVED);
}
static void test_wrong_target_fails(void) {
  for(unsigned n=1;n<=3;n++)
    assert(route(n,710+n,1,0,0,0,0,0,0)==WB_COUNT_NOT_ACHIEVED);
}
static void test_skip_and_illegal_routes_fail(void) {
  assert(route(1,801,0,1,0,0,0,0,0)==WB_COUNT_NOT_ACHIEVED);
  assert(route(1,802,0,0,1,0,0,0,0)==WB_COUNT_NOT_ACHIEVED);
  assert(route(1,803,0,0,0,1,0,0,0)==WB_COUNT_NOT_ACHIEVED);
  assert(route(1,804,0,0,0,0,1,0,0)==WB_COUNT_NOT_ACHIEVED);
  assert(route(1,805,0,0,0,0,0,1,0)==WB_COUNT_NOT_ACHIEVED);
  assert(route(1,806,0,0,0,0,0,0,1)==WB_COUNT_NOT_ACHIEVED);
}
/* An H centre observation is not a permanent crossing token.  Every
 * variant must reject a later sideways bypass after a return upstream. */
static void test_backtrack_lateral_bypass_rejected(void) {
  for (unsigned n=1;n<=3;n++) {
    wb_count_mission m;
    wb_count_reset(&m,1900+n,n,0.0);
    double clock=0.0,h=wb_count_gate_x(0);
    assert(feed(&m,&clock,-1.40,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h-.18,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(m.observed_center);
    assert(feed(&m,&clock,h-.30,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(!m.observed_center);
    assert(feed(&m,&clock,h-.30,.55,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h+.30,.55,.40,0,0,0)==WB_COUNT_NOT_ACHIEVED);
    assert(m.crossed==0);
  }
}
/* Endpoints can be outside the H strip, but a swept crossing between them
 * is still unsafe.  Neither a sideways nor high-altitude shortcut may pass. */
static void test_swept_gate_shortcuts_rejected(void) {
  for (unsigned n=1;n<=3;n++) for (int kind=0;kind<2;kind++) {
    wb_count_mission m;
    wb_count_reset(&m,2000+10*n+kind,n,0.0);
    double clock=0.0,h=wb_count_gate_x(0);
    assert(feed(&m,&clock,-1.40,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h-.18,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h,0,.40,0,0,0)==WB_COUNT_WAIT);
    if (kind==0)
      assert(feed(&m,&clock,h+.18,.55,.40,0,0,0)==WB_COUNT_NOT_ACHIEVED);
    else
      assert(feed(&m,&clock,h+.18,0,.95,0,0,0)==WB_COUNT_NOT_ACHIEVED);
    assert(m.crossed==0);
  }
}
/* A failed first approach is correctable: returning upstream, re-centring
 * and passing every actual H legally must still allow the proper landing. */
static void test_backtrack_corrected_retry_can_succeed(void) {
  for (unsigned n=1;n<=3;n++) {
    wb_count_mission m;
    wb_count_reset(&m,2100+n,n,0.0);
    double clock=0.0,h=wb_count_gate_x(0);
    assert(feed(&m,&clock,-1.40,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h-.18,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h-.30,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(!m.observed_center);
    assert(feed(&m,&clock,h-.18,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,h+.18,0,.40,0,0,0)==WB_COUNT_WAIT);
    assert(m.crossed==1);
    for (unsigned i=1;i<n;i++) {
      h=wb_count_gate_x(i);
      assert(feed(&m,&clock,h-.18,0,.40,0,0,0)==WB_COUNT_WAIT);
      assert(feed(&m,&clock,h,0,.40,0,0,0)==WB_COUNT_WAIT);
      assert(feed(&m,&clock,h+.18,0,.40,0,0,0)==WB_COUNT_WAIT);
      assert(m.crossed==i+1);
    }
    const double y=wb_count_target_y(n);
    assert(feed(&m,&clock,1.48,y,.40,0,0,0)==WB_COUNT_WAIT);
    assert(feed(&m,&clock,1.48,y,.02,0,0,1)==WB_COUNT_WAIT);
    for (int k=0;k<8;k++) {
      const wb_count_verdict result=
        feed_step(&m,&clock,.032,1.48,y,.02,0,0,0);
      if(k<7)assert(result==WB_COUNT_WAIT);
      else assert(result==WB_COUNT_ACHIEVED);
    }
    assert(m.crossed==n && m.verdict==WB_COUNT_ACHIEVED);
  }
}

static void test_invalid_time_and_data(void) {
  wb_count_mission m;
  wb_count_reset(&m,23,2,0.0);
  wb_count_sample a=s(0.1,-1.40,0,0.4,0.1,0,0);
  assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
  assert(wb_count_sample_mission(&m,&a)==WB_COUNT_NOT_ACHIEVED);
  wb_count_reset(&m,24,2,0.0);
  a.time=NAN;
  assert(wb_count_sample_mission(&m,&a)==WB_COUNT_NOT_ACHIEVED);
  wb_count_reset(&m,25,2,0.0);
  a.time=-0.1;
  assert(wb_count_sample_mission(&m,&a)==WB_COUNT_NOT_ACHIEVED);
  wb_count_reset(&m,0,2,0.0);
  assert(wb_count_sample_mission(&m,&a)==WB_COUNT_NOT_ACHIEVED);
  wb_count_reset(&m,1,4,0.0);
  assert(wb_count_sample_mission(&m,&a)==WB_COUNT_NOT_ACHIEVED);
}
static void test_backwards_reentry_and_fresh_attempt(void) {
  wb_count_mission m;
  wb_count_reset(&m,26,1,0.0);
  double t=0;
  for(int i=0;i<=110;i++) {
    const double x=-1.40+i*0.010;
    assert(feed(&m,&t,x,0,0.4,0.10,0,0)==WB_COUNT_WAIT);
  }
  assert(m.crossed==1);
  assert(feed(&m,&t,-1.10,0,0.4,0.10,0,0)==WB_COUNT_NOT_ACHIEVED);
  wb_count_reset(&m,27,1,0.0);
  assert(m.crossed==0 && m.verdict==WB_COUNT_WAIT && !m.completion_seen);
  assert(feed(&m,&t,-1.40,0,0.4,0.10,0,0)==WB_COUNT_WAIT);
}
/* Build an already counted true 1/2/3-H route, without completing it. */
static void ready_to_land(wb_count_mission *m, unsigned n) {
  wb_count_reset(m,900+n,n,0.0);
  for(int i=0;i<=250;i++) {
    const double x=-1.40+i*0.01152;
    wb_count_sample a=s(0.10*(double)(i+1),x,0,0.4,0.10,0,0);
    assert(wb_count_sample_mission(m,&a)==WB_COUNT_WAIT);
  }
  assert(m->crossed==n && !m->completion_seen);
}
static void test_stable_landing_and_deadline(void) {
  for(unsigned n=1;n<=3;n++) {
    wb_count_mission m;
    const double y=wb_count_target_y(n);
    ready_to_land(&m,n);
    wb_count_sample a=s(100.000,1.48,y,.02,0,0,1);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(100.032,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    /* A moving tick interrupts stability; 250 ms start again later. */
    a=s(100.064,1.48,y,.02,.35,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(100.096,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    for(int i=1;i<=8;++i) {
      a=s(100.096+.032*i,1.48,y,.02,0,0,0);
      assert(wb_count_sample_mission(&m,&a)==
             (i<8?WB_COUNT_WAIT:WB_COUNT_ACHIEVED));
    }
    wb_count_reset(&m,1200+n,n,0.0);
    assert(m.crossed==0 && !m.completion_seen &&
           !m.stable_since_valid && m.verdict==WB_COUNT_WAIT);
    ready_to_land(&m,n);
    a=s(100.000,1.48,y,.02,0,0,1);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(100.032,1.48,y+.12,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(100.064,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    for(int i=1;i<=8;++i) {
      a=s(100.064+.032*i,1.48,y,.02,0,0,0);
      assert(wb_count_sample_mission(&m,&a)==
             (i<8?WB_COUNT_WAIT:WB_COUNT_ACHIEVED));
    }
    /* Deadline takes precedence even if a late tick is stationary. */
    ready_to_land(&m,n);
    a=s(100.000,1.48,0.0,.40,0,0,1);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(101.240,1.48,0.0,.40,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(101.248,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(101.496,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(101.504,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_NOT_ACHIEVED);
    a=s(101.512,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_NOT_ACHIEVED);
    ready_to_land(&m,n);
    a=s(100.000,1.48,0.0,.40,0,0,1);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(101.250,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(101.500,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_NOT_ACHIEVED);
  }
}
/* Do not treat two poses 260 ms apart as 260 ms of observed stillness.
 * Replayed samples must be consecutive at the exact 32-ms physics cadence.
 * Also falsify the loss of just ONE 32-ms Webots frame. */
static void test_missing_landing_observation_restarts_dwell(void) {
  for(unsigned n=1;n<=3;++n) {
    wb_count_mission m;
    const double y=wb_count_target_y(n);
    ready_to_land(&m,n);
    wb_count_sample a=s(100.000,1.48,y,.02,0,0,1);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(100.260,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    assert(fabs(m.stable_since-100.260)<1e-8);
    for(int i=1;i<=8;++i) {
      a=s(100.260+.032*i,1.48,y,.02,0,0,0);
      assert(wb_count_sample_mission(&m,&a)==
             (i<8?WB_COUNT_WAIT:WB_COUNT_ACHIEVED));
    }
    ready_to_land(&m,n);
    a=s(100.000,1.48,y,.02,0,0,1);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    a=s(100.064,1.48,y,.02,0,0,0);
    assert(wb_count_sample_mission(&m,&a)==WB_COUNT_WAIT);
    assert(fabs(m.stable_since-100.064)<1e-8);
    for(int i=1;i<=8;++i) {
      a=s(100.064+.032*i,1.48,y,.02,0,0,0);
      assert(wb_count_sample_mission(&m,&a)==
             (i<8?WB_COUNT_WAIT:WB_COUNT_ACHIEVED));
    }
  }
}
int main(void) {
  test_successes();
  test_backtrack_lateral_bypass_rejected();
  test_swept_gate_shortcuts_rejected();
  test_backtrack_corrected_retry_can_succeed();
  test_stable_landing_and_deadline();
  test_missing_landing_observation_restarts_dwell();
  test_wrong_target_fails();
  test_skip_and_illegal_routes_fail();
  test_invalid_time_and_data();
  test_backwards_reentry_and_fresh_attempt();
  puts("PASS Activity 6 native C oracle: three missions, false-target, bypass, clock, contact, and fresh RESET");
  return 0;
}
'''


class CountHCoreTests(unittest.TestCase):
    def test_native_c_behavioral_oracle(self):
        compiler = shutil.which("cc") or shutil.which("gcc")
        if not compiler:
            self.fail("native C compiler is required (no Python fallback)")
        self.assertTrue(CORE.is_file(), "missing native Activity 6 oracle")
        with tempfile.TemporaryDirectory(prefix="wb-count-h-") as tmp:
            path = Path(tmp)
            src = path / "native_count_h.c"
            out = path / "native_count_h"
            src.write_text(DRIVER, encoding="utf-8")
            subprocess.run(
                [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", str(CORE.parent), str(src), "-lm", "-o", str(out)],
                check=True, cwd=ROOT,
            )
            completed = subprocess.run(
                [str(out)], cwd=ROOT, capture_output=True, text=True,
                check=True,
            )
        self.assertIn("PASS Activity 6 native C oracle", completed.stdout)

    def test_core_matches_actual_draft_scene_geometry(self):
        # Do not silently test a synthetic layout different from the proposed
        # physical WBO: each true collider and all 3 pads must match this core.
        positions = (-0.850, 0.000, 0.850)
        for n in (1, 2, 3):
            scene = (ROOT / f"worlds/scenes/count-h-{n}-v1.wbo").read_text(
                encoding="utf-8"
            )
            for i in range(1, n + 1):
                match = re.search(
                    rf"DEF ACTIVITY6_{n}_H_{i}_BAR Solid \{{\s*"
                    rf"translation (-?[0-9.]+) 0 0\.74",
                    scene,
                )
                self.assertIsNotNone(match, (n, i))
                self.assertAlmostEqual(float(match.group(1)), positions[i - 1])
            for y in (0.0, 0.550, -0.550):
                self.assertIn(
                    f"Pose {{ translation 1.48 {y:.3f} 0.002", scene
                )
            self.assertIn(f"DEF ACTIVITY6_{n}_TERMINAL Solid", scene)
            self.assertIn("translation 1.86 0 0.55", scene)

    def test_no_syntax_or_browser_authority(self):
        source = CORE.read_text(encoding="utf-8")
        self.assertNotIn("Blockly.", source)
        self.assertNotIn("wb_robot_get_device", source)
        self.assertNotIn("wb_supervisor_node", source)
        self.assertNotIn("wb_count_sample_mission(AST", source)
        self.assertIn("WB_COUNT_NOT_ACHIEVED", source)
        self.assertIn("#define WB_COUNT_LAND_DWELL_SEC 0.250", source)


if __name__ == "__main__":
    unittest.main()
