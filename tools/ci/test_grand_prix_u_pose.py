"""Exercise the complete composed C runtime, broker and deadline authority."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import os
import unittest
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.grand_prix.prepare_u_runtime import prepare

CASES=('no-fault','deadline-error','early-error','timeout','land-timeout',
       'land','error-ground','gps-nan','imu-nan','gyro-nan','bounce','moving',
       'below-ground','loss-recover',
       *(f'reset-gyro-{axis}-{failure}' for axis in 'xyz' for failure in ('loss','recover','high')),
       *(f'reset-gyro-{axis}-final-recover' for axis in 'xyz'),
       'reset-gps-null','reset-imu-null','reset-gyro-null','reset-yaw-infinite',
       'reset-yaw-high','reset-yaw-recover',
       'reset-gps-recover','reset-imu-recover','reset-gap-recover','reset-queue',
       *(f'flight-yaw-{value}-recover' for value in
         ('infinite','negative-infinite','extreme','negative-extreme','max','nan')),
       'flight-yaw-infinite-loss','flight-yaw-extreme-loss','flight-yaw-deadline-recover',
       *(f'reset-yaw-{value}-{failure}' for value in
         ('extreme','negative-extreme','max') for failure in ('loss','recover')),
       'reset-yaw-extreme-first-recover','reset-yaw-extreme-final-recover',
       'reset-yaw-periodic-loss','reset-roll-extreme-loss','reset-pitch-extreme-loss')

def expected_reset(case):
    return case in ('land','error-ground','loss-recover','reset-queue') or case.endswith('-recover')

def expected_teleports(case):
    return expected_reset(case) or case.startswith('reset-')
FIXTURES=ROOT/'tools/ci/fixtures'
FILE_PROBES=(('land','cold'),('land','warm'),('early-error','cold'),
             ('land-timeout','cold'),('land','startup-reset'))
WRAPPERS='''#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/gps.h>
#include <webots/gyro.h>
#include <webots/inertial_unit.h>
int gp_test_step(int);
const double* gp_test_gps(int);
const double* gp_test_gyro(int);
const double* gp_test_imu(int);
void gp_test_teleport(WbFieldRef,const double*);
#define main gp_runtime_main
#define wb_robot_step gp_test_step
#define wb_gps_get_values gp_test_gps
#define wb_gyro_get_values gp_test_gyro
#define wb_inertial_unit_get_roll_pitch_yaw gp_test_imu
#define wb_supervisor_field_set_sf_vec3f gp_test_teleport
'''

def instrument(base):
    prepare()
    composed=ROOT/'controllers/grand_prix_u_flight/build'
    runtime=(composed/'runtime_u.c').read_text()
    motor='      wb_motor_set_velocity(m4, motor_power(power.m4));'
    if runtime.count(motor)!=1:raise RuntimeError('composed motor anchor changed')
    runtime=runtime.replace(motor,motor+'''
      if (llround(now * 1000.0) == 212048) {
        printf("GP_U_CONTROL_APPLIED time_ms=212048 command=%s\\n", command == CMD_LAND ? "LAND" : "OTHER");
        fflush(stdout);
      }''')
    (base/'runtime.c').write_text(WRAPPERS+runtime)
    (base/'broker.cpp').write_text(
        '#define wb_robot_wwi_receive_text gp_test_receive\n'
        '#define wb_robot_wwi_send gp_test_send\n'
        '#define wb_robot_cleanup gp_test_cleanup\n'+(composed/'file_broker_u.cpp').read_text())
    (base/'deadline.cpp').write_text('#define wb_robot_wwi_send gp_test_send\n'+
        (ROOT/'controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp').read_text())

class PoseTests(unittest.TestCase):
    def test_bounded_angle_and_imu_domain(self):
        prepare()
        source=(ROOT/'controllers/grand_prix_u_flight/build/runtime_u.c').read_text()
        helpers=source[source.index('static int gp_valid_attitude'):source.index('static void stop_motors')]
        with tempfile.TemporaryDirectory(prefix='gp-u-angles-') as tmp:
            base=Path(tmp)
            (base/'angles.c').write_text('#include <math.h>\n#include <float.h>\n#include <assert.h>\n'
                '#define PI 3.14159265358979323846\n'+helpers+'''
int main(void) {
  assert(wrap_angle(PI) == PI && wrap_angle(-PI) == PI);
  assert(wrap_angle(0) == 0 && wrap_angle(2*PI) == 0);
  assert(wrap_angle(nextafter(PI, INFINITY)) < 0);
  assert(wrap_angle(nextafter(-PI, -INFINITY)) > 0);
  const double bad[] = {NAN, INFINITY, -INFINITY, 1e20, -1e20, DBL_MAX, -DBL_MAX, 2*PI};
  for (unsigned i=0; i<sizeof(bad)/sizeof(*bad); ++i) {
    const double result=wrap_angle(bad[i]);
    assert(isfinite(bad[i]) ? (isfinite(result) && result > -PI && result <= PI) : isnan(result));
    double rpy[3]={0,0,0};
    for (int axis=0;axis<3;++axis) {
      rpy[axis]=bad[i]; assert(!gp_valid_attitude(rpy)); rpy[axis]=0;
    }
  }
  for (int exponent=-1074;exponent<=1023;++exponent) {
    const double value=ldexp(1.0,exponent);
    for(int sign=-1;sign<=1;sign+=2) {
      const double result=wrap_angle(sign*value);
      assert(isfinite(result) && result > -PI && result <= PI);
    }
  }
  double rpy[3]={PI,PI/2,-PI}; assert(gp_valid_attitude(rpy));
  rpy[2]=nextafter(PI,INFINITY); assert(!gp_valid_attitude(rpy));
  rpy[2]=0; rpy[1]=nextafter(PI/2,INFINITY); assert(!gp_valid_attitude(rpy));
  assert(!gp_valid_attitude(0));
}
''')
            subprocess.run(['gcc','-std=c11',str(base/'angles.c'),'-lm','-o',str(base/'angles')],check=True)
            subprocess.run([str(base/'angles')],check=True,timeout=2)

    def test_real_composition_pose_provenance(self):
        self.assertIsNotNone(shutil.which('gcc'))
        self.assertIsNotNone(shutil.which('c++'))
        with tempfile.TemporaryDirectory(prefix='gp-u-pose-') as tmp:
            base=Path(tmp);(base/'webots/plugins/robot_window').mkdir(parents=True)
            header=(FIXTURES/'gp_u_pose_webots.h').read_text()
            for name in ('robot','motor','gps','gyro','inertial_unit','distance_sensor','led','supervisor'):
                (base/'webots'/f'{name}.h').write_text(header)
            (base/'webots/plugins/robot_window/default.h').write_text('#include <webots/robot.h>\n')
            instrument(base)
            inc=['-I'+str(base),'-I'+str(ROOT/'controllers/crazyflie_runtime_v2'),
                 '-I'+str(ROOT/'controllers/crazyflie_square'),'-I'+str(ROOT/'controllers/grand_prix_u_flight')]
            subprocess.run(['gcc','-std=c11',*inc,'-include',str(ROOT/'controllers/grand_prix_u_flight/grand_prix_u_hook.h'),
                            '-c',str(base/'runtime.c'),'-o',str(base/'runtime.o')],check=True)
            binary=base/'pose'
            subprocess.run(['c++','-std=c++17','-DNDEBUG',*inc,str(base/'runtime.o'),
                            str(FIXTURES/'gp_u_pose_driver.cpp'),str(base/'broker.cpp'),
                            str(base/'deadline.cpp'),str(ROOT/'controllers/crazyflie_runtime_v2/file_broker.cpp'),
                            *map(str,(ROOT/'controllers/crazyflie_runtime_v2').glob('activity_scene.cpp')),
                            '-pthread','-o',str(binary)],check=True)
            for case in CASES:
                with self.subTest(case=case):
                    result=subprocess.run([str(binary)],env={**os.environ,'GP_U_POSE_CASE':case},
                                          capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode,0,result.stdout[-4000:]+result.stderr)
                    self.assertIn(f'GP_U_POSE_PASS case={case} ',result.stdout)
                    deadlines=[line for line in result.stdout.splitlines() if line.startswith('GP_U_DEADLINE ')]
                    self.assertEqual(len(deadlines),1,result.stdout)
                    self.assertIn('time_ms=212048 command=LAND',deadlines[0])
            for case,probe in FILE_PROBES:
                with self.subTest(case=case,files=probe):
                    result=subprocess.run([str(binary)],env={**os.environ,'GP_U_POSE_CASE':case,'GP_U_FILE_PROBE':probe},
                                          capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode,0,result.stdout[-5000:]+result.stderr)
                    self.assertIn(f'GP_U_FILE_PASS probe={probe} ',result.stdout)
                    deadlines=[line for line in result.stdout.splitlines() if line.startswith('GP_U_DEADLINE ')]
                    self.assertEqual(len(deadlines),0 if probe=='startup-reset' else 1,result.stdout)
                    if deadlines:self.assertIn('time_ms=212048 command=LAND',deadlines[0])
                    if (case=='land' and probe!='startup-reset') or case=='land-timeout':
                        self.assertEqual(result.stdout.count('GP_U_CONTROL_APPLIED time_ms=212048 command=LAND'),1)

if __name__=='__main__':unittest.main()
