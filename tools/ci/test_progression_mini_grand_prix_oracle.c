/* Compile: cc -std=c11 -Wall -Wextra -Werror -pedantic
 *   -Icontrollers/progression_mini_grand_prix_v1
 *   tools/ci/test_progression_mini_grand_prix_oracle.c -lm -o /tmp/a7-oracle
 * Then execute /tmp/a7-oracle. Pure C, NOT a Webots/native flight PASS.
 */
#include "mini_core.h"
#include <assert.h>
#include <stdio.h>
static wb_mini_sample sample(double t,double x,double y,double z,double yaw,int done) {
  wb_mini_sample a={0};
  a.time=t;a.x=x;a.y=y;a.z=z;a.yaw=yaw;a.completed=done;
  return a;
}
/* Test-only helper: every legitimate fresh attempt begins with one native
 * observed ground sample at the blue start, not a fake H-entry sample. */
static void blue_start(wb_mini_mission *m,char v,unsigned long long attempt) {
  wb_mini_reset(m,attempt,v,.015);
  wb_mini_sample a=sample(0,-1.40,0,.015,0,0);
  assert(wb_mini_sample_mission(m,&a)==WB_MINI_WAIT);
}
static void positive(char v) {
  wb_mini_mission m;blue_start(&m,v,1);
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v),y=wb_mini_pad_y(v);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(2,h-.18,0,.40,0,0);assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(3,h,0,.40,0,0);assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(4,h+.18,0,.40,0,0);assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(5,x,0,.40,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6,x,y,.015,wb_mini_heading(v),1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  /* Native program completion is one pulse, NOT a permanent level. */
  a=sample(6.24,x,y,.015,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.26,x,y,.015,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_ACHIEVED);
}
static void bypass(char v) {
  wb_mini_mission m;blue_start(&m,v,1);
  const double h=wb_mini_h_x(v);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(2,h-.18,v=='L'?.55:-.55,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(3,h,v=='L'?.55:-.55,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
/* Exact previously reproduced NO_GO: gate centre, retreat upstream,
 * lateral bypass outside the opening, then jump to downstream. */
static void backtrack_lateral_bypass(char v) {
  wb_mini_mission m;blue_start(&m,v,1);
  const double h=wb_mini_h_x(v),side=v=='L'?.55:-.55;
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(2,h-.18,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(3,h,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  assert(m.center_seen);
  a=sample(4,h-.30,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  assert(!m.center_seen);
  a=sample(5,h-.30,side,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6,h+.30,side,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  assert(!m.crossed);
}
/* Both discrete endpoints can lie outside the tight H strip, while the
 * interpolated segment enters its forbidden lateral volume. */
static void swept_lateral_bypass(char v) {
  wb_mini_mission m;blue_start(&m,v,1);
  const double h=wb_mini_h_x(v),side=v=='L'?.55:-.55;
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(2,h-.18,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(3,h,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(4,h+.18,side,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
/* Retracing steps is not itself a collision. Re-centering and a legal
 * forward underpass must remain possible for a pupil correcting an error. */
static void corrected_retry(char v) {
  wb_mini_mission m;blue_start(&m,v,1);
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v),y=wb_mini_pad_y(v);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(2,h-.18,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(3,h,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(4,h-.30,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  assert(!m.center_seen);
  a=sample(5,h-.18,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6,h,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(7,h+.18,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  assert(m.crossed);
  a=sample(8,x,0,.40,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(9,x,y,.015,wb_mini_heading(v),1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(9.26,x,y,.015,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_ACHIEVED);
}

/* First observed sample near a physical obstacle cannot prove a fresh
 * departure from the blue starting area, even with valid attempt identity. */
static void absent_blue_start(char v) {
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
  const double h=wb_mini_h_x(v);
  wb_mini_sample a=sample(1,h-.18,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(2,h,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
/* Do not accept a spoofed starting sample with wrong pose, vertical state,
 * motion, yaw, or a prematurely published completion pulse. */
static void invalid_blue_pose(char v) {
  wb_mini_mission m;
  for(int mode=0;mode<7;++mode) {
    wb_mini_reset(&m,1,v,.015);
    wb_mini_sample a=sample(0,-1.40,0,.015,0,0);
    if(mode==0)a.x+=.20;
    if(mode==1)a.y+=.20;
    if(mode==2)a.z+=.20;
    if(mode==3)a.yaw=.45;
    if(mode==4)a.vx=.30;
    if(mode==5)a.vz=.30;
    if(mode==6)a.completed=1;
    assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
    a=sample(1,-1.40,0,.015,0,0);
    assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  }
}
/* After an invalid first observation, a NEW attempt (not replay on the
 * old token) may start at the legitimate blue marker and take off. */
static void fresh_blue_reset(char v) {
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
  wb_mini_sample a=sample(1,wb_mini_h_x(v)-.18,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  blue_start(&m,v,2);
  assert(m.attempt==2);
  a=sample(1,-1.40,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
}


/* The sample's z-origin_z was formerly enough to make a stationary hover
 * 40 cm above the actual floor look like touchdown. Native floor is z=0. */
static void airborne_origin_must_fail(char v) {
  wb_mini_mission m;wb_mini_reset(&m,1,v,.400);
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v),y=wb_mini_pad_y(v);
  wb_mini_sample a=sample(0,-1.40,0,.400,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(1,-1.40,0,.620,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(2,h-.18,0,.400,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(3,h,0,.400,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(4,h+.18,0,.400,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(5,x,0,.400,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(6,x,y,.400,wb_mini_heading(v),1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(6.26,x,y,.400,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
/* A reference below the physical floor is also untrusted, even if its
 * first sample perfectly agrees with the forged local origin. */
static void underground_origin_must_fail(char v) {
  wb_mini_mission m;wb_mini_reset(&m,1,v,-.200);
  wb_mini_sample a=sample(0,-1.40,0,-.200,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(1,-1.40,0,.400,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
/* Realistic body-rest variations remain admissible after a NEW reset:
 * offset is relative to the real floor and does not encode scene identity. */
static void genuine_ground_origin_can_land(char v) {
  wb_mini_mission m;wb_mini_reset(&m,2,v,.030);
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v),y=wb_mini_pad_y(v);
  wb_mini_sample a=sample(0,-1.40,0,.030,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(1,-1.40,0,.420,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(2,h-.18,0,.420,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(3,h,0,.420,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(4,h+.18,0,.420,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(5,x,0,.420,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6,x,y,.030,wb_mini_heading(v),1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.26,x,y,.030,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_ACHIEVED);
}

static void skip_gate(char v) {
  wb_mini_mission m;blue_start(&m,v,1);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(2,wb_mini_turn_x(v),0,.40,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
static void no_turn(char v) {
  wb_mini_mission m;blue_start(&m,v,1);
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v),y=wb_mini_pad_y(v);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(2,h-.18,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(3,h,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(4,h+.18,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(5,x,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(6,x,y,.015,0,1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
static void contact_and_stale(void) {
  wb_mini_mission m;wb_mini_reset(&m,1,'L',.015);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);a.contact=1;
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(2,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  blue_start(&m,'L',2);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
static void ready_for_completion(wb_mini_mission *m,char v) {
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v);
  blue_start(m,v,1);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(m,&a)==WB_MINI_WAIT);
  a=sample(2,h-.18,0,.40,0,0);
  assert(wb_mini_sample_mission(m,&a)==WB_MINI_WAIT);
  a=sample(3,h,0,.40,0,0);
  assert(wb_mini_sample_mission(m,&a)==WB_MINI_WAIT);
  a=sample(4,h+.18,0,.40,0,0);
  assert(wb_mini_sample_mission(m,&a)==WB_MINI_WAIT);
  a=sample(5,x,0,.40,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(m,&a)==WB_MINI_WAIT);
}
static void settle_pulse_and_motion(char v) {
  wb_mini_mission m;
  ready_for_completion(&m,v);
  const double x=wb_mini_turn_x(v),y=wb_mini_pad_y(v);
  wb_mini_sample a=sample(6,x,y,.015,wb_mini_heading(v),1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.20,x,y,.015,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.23,x,y,.015,wb_mini_heading(v),0);a.vx=.3;
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.40,x,y,.015,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.63,x,y,.015,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.66,x,y,.015,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_ACHIEVED);
}
/* A trajectory that crossed H and turned cannot claim program COMPLETE
 * at the corner and then travel the remaining 0.95 m as a settling action. */
static void completion_away_from_pad_y(char v) {
  wb_mini_mission m;ready_for_completion(&m,v);
  const double x=wb_mini_turn_x(v),y=wb_mini_pad_y(v),yaw=wb_mini_heading(v);
  wb_mini_sample a=sample(6,x,0,.40,yaw,1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(6.26,x,y,.015,yaw,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
/* The same completion boundary must reject a distant X even if Y is right. */
static void completion_away_from_pad_x(char v) {
  wb_mini_mission m;ready_for_completion(&m,v);
  const double x=wb_mini_turn_x(v),y=wb_mini_pad_y(v),yaw=wb_mini_heading(v);
  wb_mini_sample a=sample(6,x+.40,y,.40,yaw,1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
/* A small and correctly oriented settling drift after COMPLETE is allowed:
 * do not over-constrain a child using the native landing PID. */
static void completion_near_pad_can_settle(char v) {
  wb_mini_mission m;ready_for_completion(&m,v);
  const double x=wb_mini_turn_x(v),y=wb_mini_pad_y(v),yaw=wb_mini_heading(v);
  const double near=y+(v=='L'?-.14:.14);
  wb_mini_sample a=sample(6,x,near,.015,yaw,1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.20,x,y,.015,yaw,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(6.46,x,y,.015,yaw,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_ACHIEVED);
}
static void terminal_timeout(char v) {
  wb_mini_mission m;
  ready_for_completion(&m,v);
  const double x=wb_mini_turn_x(v),y=wb_mini_pad_y(v);
  wb_mini_sample a=sample(6,x,y,.40,wb_mini_heading(v),1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(7.51,x,y,.40,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(8,x,y,.015,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
static void completion_before_turn(char v) {
  wb_mini_mission m;
  blue_start(&m,v,1);
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(2,h-.18,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(3,h,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(4,h+.18,0,.40,0,0);wb_mini_sample_mission(&m,&a);
  a=sample(5,x,0,.40,wb_mini_heading(v),1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
static void yaw_reversal_lateral_slide(char v) {
  wb_mini_mission m;
  ready_for_completion(&m,v);
  const double x=wb_mini_turn_x(v), y=wb_mini_pad_y(v);
  /* A single correct corner yaw cannot authorize a subsequent side-slide
   * after returning to the initial heading. Both variants must refuse. */
  wb_mini_sample a=sample(5.20,x,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(5.50,x,y*.50,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(6.00,x,y,.015,wb_mini_heading(v),1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
static void late_dwell_boundary(char v) {
  wb_mini_mission m;
  ready_for_completion(&m,v);
  const double x=wb_mini_turn_x(v),y=wb_mini_pad_y(v),yaw=wb_mini_heading(v);
  wb_mini_sample a=sample(6.000,x,y,.40,yaw,1);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(7.240,x,y,.40,yaw,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(7.248,x,y,.015,yaw,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(7.496,x,y,.015,yaw,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  /* 0.256 s stable, but 1.504 s after completion: must fail. */
  a=sample(7.504,x,y,.015,yaw,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
  a=sample(7.600,x,y,.015,yaw,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
int main(void) {
  positive('L');positive('R');
  airborne_origin_must_fail('L');airborne_origin_must_fail('R');
  underground_origin_must_fail('L');underground_origin_must_fail('R');
  genuine_ground_origin_can_land('L');genuine_ground_origin_can_land('R');
  absent_blue_start('L');absent_blue_start('R');
  invalid_blue_pose('L');invalid_blue_pose('R');
  fresh_blue_reset('L');fresh_blue_reset('R');
  completion_away_from_pad_y('L');completion_away_from_pad_y('R');
  completion_away_from_pad_x('L');completion_away_from_pad_x('R');
  completion_near_pad_can_settle('L');completion_near_pad_can_settle('R');
  backtrack_lateral_bypass('L');backtrack_lateral_bypass('R');
  swept_lateral_bypass('L');swept_lateral_bypass('R');
  corrected_retry('L');corrected_retry('R');
  yaw_reversal_lateral_slide('L');yaw_reversal_lateral_slide('R');
  late_dwell_boundary('L');late_dwell_boundary('R');
  settle_pulse_and_motion('L');settle_pulse_and_motion('R');
  terminal_timeout('L');terminal_timeout('R');
  completion_before_turn('L');completion_before_turn('R');
  bypass('L');bypass('R');
  skip_gate('L');skip_gate('R');
  no_turn('L');no_turn('R');
  contact_and_stale();
  puts("PASS A7 isolated C oracle: forty-three positive/adversarial scenarios");
  return 0;
}
