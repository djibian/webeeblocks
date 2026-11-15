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
int main(void) {
  positive('L');positive('R');
  settle_pulse_and_motion('L');settle_pulse_and_motion('R');
  terminal_timeout('L');terminal_timeout('R');
  completion_before_turn('L');completion_before_turn('R');
  bypass('L');bypass('R');
  skip_gate('L');skip_gate('R');
  no_turn('L');no_turn('R');
  contact_and_stale();
  puts("PASS A7 isolated C oracle: fifteen positive/adversarial scenarios");
  return 0;
}
