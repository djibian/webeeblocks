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
       'below-ground','loss-recover')
FIXTURES=ROOT/'tools/ci/fixtures'
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
    (base/'runtime.c').write_text(WRAPPERS+(composed/'runtime_u.c').read_text())
    (base/'broker.cpp').write_text(
        '#define wb_robot_wwi_receive_text gp_test_receive\n'
        '#define wb_robot_wwi_send gp_test_send\n'
        '#define wb_robot_cleanup gp_test_cleanup\n'+(composed/'file_broker_u.cpp').read_text())
    (base/'deadline.cpp').write_text('#define wb_robot_wwi_send gp_test_send\n'+
        (ROOT/'controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp').read_text())

class PoseTests(unittest.TestCase):
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
                            str(base/'deadline.cpp'),'-o',str(binary)],check=True)
            for case in CASES:
                with self.subTest(case=case):
                    result=subprocess.run([str(binary)],env={**os.environ,'GP_U_POSE_CASE':case},
                                          capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode,0,result.stdout[-4000:]+result.stderr)
                    self.assertIn(f'GP_U_POSE_PASS case={case} ',result.stdout)
                    deadlines=[line for line in result.stdout.splitlines() if line.startswith('GP_U_DEADLINE ')]
                    self.assertEqual(len(deadlines),1,result.stdout)
                    self.assertIn('time_ms=212048 command=LAND',deadlines[0])

if __name__=='__main__':unittest.main()
