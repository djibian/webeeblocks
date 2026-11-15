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
static void positive(char v) {
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v),y=wb_mini_pad_y(v);
  wb_mini_sample a=sample(0,-1.4,0,.015,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(1,-1.4,0,.40,0,0);assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
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
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
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
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
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
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
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
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
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
static void skip_gate(char v) {
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
  wb_mini_sample a=sample(1,-1.4,0,.40,0,0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  a=sample(2,wb_mini_turn_x(v),0,.40,wb_mini_heading(v),0);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
static void no_turn(char v) {
  wb_mini_mission m;wb_mini_reset(&m,1,v,.015);
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
  wb_mini_reset(&m,2,'L',.015);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_WAIT);
  assert(wb_mini_sample_mission(&m,&a)==WB_MINI_FAILED);
}
static void ready_for_completion(wb_mini_mission *m,char v) {
  const double h=wb_mini_h_x(v),x=wb_mini_turn_x(v);
  wb_mini_reset(m,1,v,.015);
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
  wb_mini_reset(&m,1,v,.015);
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
  puts("PASS A7 isolated C oracle: twenty-five positive/adversarial scenarios");
  return 0;
}
