"""Host C test of the actual synchronous route cascade; not native flight."""
import pathlib
import subprocess
import tempfile
import unittest

from tools.grand_prix.route_multirate import CASCADE

ROOT = pathlib.Path(__file__).resolve().parents[2]


class MultirateTests(unittest.TestCase):
    def test_cascade(self):
        harness = r'''
#include <assert.h>
#include <math.h>
#include <string.h>
#include "pid_controller.h"
''' + CASCADE + r'''
/* Compare the composed function with the real shared PID on every tick,
 * including a perpendicular transition, reversal, variable dt and reset.
 * No held command or skipped derivative update is admissible. */
static void near(double a, double b) { assert(fabs(a-b) < 1e-9); }
static void trace(int use_route, motor_power_t *powers, double (*rp)[2]) {
  gp_multirate_t s = {0};
  gains_pid_t g = {0};
  g.kp_vel_xy = 2; g.kd_vel_xy = .5;
  g.kp_z = 10; g.ki_z = 5; g.kd_z = 5;
  g.kp_att_rp = .5; g.kd_att_rp = .1; g.kp_att_y = 1;
  init_pid_attitude_fixed_height_controller();
  for (int tick=0; tick<128; ++tick) {
    if (tick==64) {
      memset(&s,0,sizeof(s));
      init_pid_attitude_fixed_height_controller();
    }
    actual_state_t a = {0};
    desired_state_t d = {0};
    a.vx = .20*sin(tick*.11); a.vy = .19*cos(tick*.13);
    a.roll = .05*sin(tick*.20); a.pitch = .04*cos(tick*.23);
    a.altitude = .80+.003*sin(tick*.10); d.altitude = .80;
    d.vx = tick<32?.35:tick<64?0:tick<96?-.35:0;
    d.vy = tick<32?0:tick<64?.35:tick<96?0:-.35;
    const double dt = tick==96?.016:.008;
    if (use_route) {
      gp_multirate_pid(&s,a,&d,g,dt,&powers[tick]);
      assert(s.ticks == (unsigned long long)(tick%64+1));
      assert(s.ticks == s.updates);
    } else {
      pid_velocity_fixed_height_controller(a,&d,g,dt,&powers[tick]);
    }
    rp[tick][0]=d.roll; rp[tick][1]=d.pitch;
  }
}
int main(void) {
  motor_power_t reference[128], route[128];
  double ref_rp[128][2], route_rp[128][2];
  trace(0,reference,ref_rp); trace(1,route,route_rp);
  for (int i=0;i<128;i++) {
    near(reference[i].m1,route[i].m1); near(reference[i].m2,route[i].m2);
    near(reference[i].m3,route[i].m3); near(reference[i].m4,route[i].m4);
    near(ref_rp[i][0],route_rp[i][0]); near(ref_rp[i][1],route_rp[i][1]);
  }
  return 0;
}
'''
        pid = ROOT / 'controllers/crazyflie_square'
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'test.c'
            binary = pathlib.Path(directory) / 'test'
            source.write_text(harness)
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I', str(pid), str(source), str(pid / 'pid_controller.c'),
                            '-lm', '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
