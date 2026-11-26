"""Host C test of the actual G1 scheduler and shared PID; not native flight."""
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
extern double pastVxError;
extern double altitudeIntegrator;
static void near(double a, double b) { assert(fabs(a-b) < 1e-6); }
int main(void) {
  gp_multirate_t s = {0};
  actual_state_t a = {0};
  desired_state_t d = {0};
  gains_pid_t g = {0};
  motor_power_t p = {0}, expected = {0};
  g.kp_vel_xy = 2; g.kd_vel_xy = .5;
  g.kp_z = 10; g.ki_z = 5; g.kd_z = 5;
  g.kp_att_rp = .5; g.kd_att_rp = .1; g.kp_att_y = 1;
  d.vx = .1; d.altitude = .1;
  init_pid_attitude_fixed_height_controller();
  desired_state_t reference = d;
  pid_velocity_fixed_height_controller(a, &reference, g, .008, &expected);
  init_pid_attitude_fixed_height_controller();
  gp_multirate_pid(&s,a,&d,g,1.008,.008,2,1,1.,0,&p);
  assert(p.m1==expected.m1 && p.m2==expected.m2);
  assert(p.m3==expected.m3 && p.m4==expected.m4);
  assert(s.ticks==1 && s.updates==1); near(d.pitch,6.45);
  d.vx=.2; d.pitch=0; d.roll=0;
  gp_multirate_pid(&s,a,&d,g,1.016,.008,2,1,1.,0,&p);
  assert(s.ticks==2 && s.updates==1); near(d.pitch,6.45);
  near(pastVxError,.1); near(altitudeIntegrator,.0016);
  d.vx=.3;
  gp_multirate_pid(&s,a,&d,g,1.024,.008,2,1,1.,0,&p);
  assert(s.updates==2); near(d.pitch,6.85);
  d.vx=.31;
  gp_multirate_pid(&s,a,&d,g,1.032,.008,2,2,1.032,0,&p);
  assert(s.updates==3); near(d.pitch,1.245);
  d.vx=.32;
  gp_multirate_pid(&s,a,&d,g,1.040,.008,6,3,1.040,1,&p);
  assert(s.updates==4); near(d.pitch,1.265);
  d.vx=.33;
  gp_multirate_pid(&s,a,&d,g,1.048,.008,6,3,1.040,1,&p);
  assert(s.updates==5); near(d.pitch,1.285);
  // An inactive gap must never supply a giant derivative interval or a held target.
  d.vx=.34;
  gp_multirate_pid(&s,a,&d,g,2.000,.008,2,3,1.040,0,&p);
  assert(s.updates==6); near(d.pitch,1.305);
  memset(&s,0,sizeof(s)); init_pid_attitude_fixed_height_controller();
  d.vx=0; d.pitch=123;
  gp_multirate_pid(&s,a,&d,g,3.008,.008,2,1,3.,0,&p);
  assert(s.updates==1 && s.ticks==1); near(d.pitch,0);
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
