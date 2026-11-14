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
  a=sample(7.6,x,y,.015,wb_mini_heading(v),1);
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
int main(void) {
  positive('L');positive('R');
  bypass('L');bypass('R');
  skip_gate('L');skip_gate('R');
  no_turn('L');no_turn('R');
  contact_and_stale();
  puts("PASS A7 isolated C oracle: nine positive/adversarial scenarios");
  return 0;
}
