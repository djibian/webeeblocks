#!/usr/bin/env python3
"""Host evidence oracles. Passing these is not a physical GO or flight PASS."""
from __future__ import annotations
import argparse
import ctypes as ct
from fractions import Fraction
import math
from pathlib import Path
import tempfile
import unittest
import hosted
import research

def rank(matrix):
    a=[[Fraction(v) for v in r] for r in matrix]; pivot=0
    for col in range(len(a[0])):
        row=next((i for i in range(pivot,len(a)) if a[i][col]),None)
        if row is None: continue
        a[pivot],a[row]=a[row],a[pivot]
        divisor=a[pivot][col]; a[pivot]=[v/divisor for v in a[pivot]]
        for i in range(len(a)):
            if i!=pivot:
                divisor=a[i][col]; a[i]=[x-divisor*y for x,y in zip(a[i],a[pivot])]
        pivot+=1
    return pivot

class ScientificOracles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='world-z-tests-')
        cls.lib=hosted.build(Path(cls.tmp.name),FIRMWARE)
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_observability_is_conditional_on_pressure_datum(self):
        # H, HA, HA² for x=[z,v,ba]; a_m is known input, ba_dot=0.
        self.assertEqual(rank([[1,0,0],[0,1,0],[0,0,-1]]),3)
        # Add constant unknown pressure bias: [z,v,ba,bp], y=z+bp.
        self.assertEqual(rank([[1,0,0,1],[0,1,0,0],[0,0,-1,0],[0,0,0,0]]),3)

    def test_analytic_acceleration_and_bias_propagation(self):
        s=hosted.init(self.lib,bias=.02,qa=0,qb=0,sz=0,sv=0,sb=0)
        for _ in range(400): research.predict(self.lib,s,.07,.01)
        self.assertAlmostEqual(s.x[0],.5*.05*4**2,places=5)
        self.assertAlmostEqual(s.x[1],.05*4,places=5)

    def test_process_covariance_exact_continuous_noise(self):
        s=hosted.init(self.lib,qa=.03,qb=.02,sz=0,sv=0,sb=0)
        research.predict(self.lib,s,0,.1)
        self.assertAlmostEqual(s.p[0][0],.03*.1**3/3+.02*.1**5/20,places=10)
        self.assertAlmostEqual(s.p[1][2],-.02*.1**2/2,places=10)
        self.assertAlmostEqual(s.p[2][2],.02*.1,places=9)

    def test_bad_time_and_nonfinite_inputs_latch_failure(self):
        for dt in [0,-.01,.101,float('nan')]:
            s=hosted.init(self.lib)
            self.assertFalse(self.lib.world_z_predict(ct.byref(s),0,dt))
            self.assertFalse(self.lib.world_z_predict(ct.byref(s),0,.01))
        s=hosted.init(self.lib)
        self.assertFalse(self.lib.world_z_baro(ct.byref(s),float('inf'),.25))

    def test_no_pressure_adaptation_of_bias_in_slow_observer(self):
        s=hosted.init(self.lib,bias=.01)
        for _ in range(400):
            research.predict(self.lib,s,.01,.01)
            research.correct(self.lib,s,.3,slow=True)
        self.assertAlmostEqual(s.x[2],.01,places=8)
        self.assertGreater(s.x[0],0) # pressure still has finite authority

    def test_projection_uses_all_axes_and_normalized_independent_quaternion(self):
        theta=.2; q=[math.cos(theta/2),0,math.sin(theta/2),0]
        a=[-math.sin(theta),0,math.cos(theta)]
        self.assertAlmostEqual(hosted.project(self.lib,q,a),0,places=5)
        self.assertAlmostEqual(hosted.project(self.lib,q,[(1+.1/9.81)*v for v in a]),.1,places=5)
        with self.assertRaises(ValueError): hosted.project(self.lib,[1.1,0,0,0],a)

    def test_real_bitcraze_attitude_has_no_range_or_flow_input(self):
        def run():
            self.lib.lab_attitude_reset()
            q=None
            for _ in range(3000):
                q=hosted.attitude(self.lib,[0,0,1],[0,0,0],.01)
            return hosted.project(self.lib,q,[0,0,1])
        self.assertAlmostEqual(run(),0,places=5)
        self.lib.lab_stock_tof(1.1,.35)
        self.lib.lab_stock_flow_z(1.1,.4,.35,0)
        self.assertAlmostEqual(run(),0,places=5)

    def test_stock_measurement_routines_refute_naive_tof_removal(self):
        self.assertLess(abs(self.lib.lab_stock_tof(1.1,.35)-.35),.0002)
        self.assertGreater(abs(self.lib.lab_stock_flow_z(1.1,.4,.35,0)-1.1),.05)
        self.assertAlmostEqual(self.lib.lab_zero_hz_coupling(),.06,places=7)

    def test_local_depth_rotation_and_lever_arm_roundtrip(self):
        w=[.03,-.06,.02]; lever=[.01,-.02,-.03]; dt=.01; r=.35
        vx=.4; vy=-.15
        vcamx=vx+w[1]*lever[2]-w[2]*lever[1]
        vcamy=vy+w[2]*lever[0]-w[0]*lever[2]
        dx=dt*35/.71674*(vcamx/r-w[1])/.1
        dy=dt*35/.71674*(vcamy/r+w[0])/.1
        result=hosted.flow(self.lib,dx,dy,dt,r,omega=w,lever=lever)
        self.assertAlmostEqual(result[0],vx,places=6)
        self.assertAlmostEqual(result[1],vy,places=6)
        self.assertIsNone(hosted.flow(self.lib,dx,dy,dt,r,age=.031))
        self.assertIsNone(hosted.flow(self.lib,dx,dy,dt,r,plane=False))
        self.assertIsNone(hosted.flow(self.lib,dx,dy,dt,float('nan')))

    def test_surface_and_horizontal_injections_cannot_mutate_vertical_state(self):
        a=hosted.init(self.lib); b=hosted.init(self.lib)
        for i in range(800):
            research.predict(self.lib,a,0,.01); research.predict(self.lib,b,0,.01)
            if i%2==0:
                research.correct(self.lib,a,0); research.correct(self.lib,b,0)
            hosted.flow(self.lib,100*math.sin(i),20,.01,.35 if 200<i<600 else 1.1)
        self.assertEqual(bytes(a),bytes(b))

    def test_sensor_identical_worlds_have_different_true_altitude(self):
        result,_=research.scientific_results(self.lib)
        x=result['sensor_indistinguishability']
        self.assertLess(x['max_sensor_difference'],1e-12)
        self.assertGreater(x['world_z_difference_m'],.1)

    def test_success_and_refutation_cases_are_both_required(self):
        result,_=research.scientific_results(self.lib)
        sims=result['simulations']
        self.assertLess(sims['ideal_table_world_z']['max_z_error_m'],1e-5)
        self.assertLess(sims['true_vertical_and_table']['max_z_error_m'],.01)
        self.assertGreater(sims['pressure_step_30cm']['max_z_error_m'],.3)
        self.assertGreater(sims['closed_loop_pressure_step']['max_real_z_excursion_m'],.3)
        self.assertGreater(sims['slow_baro_1mg']['max_z_error_m'],.2)
        self.assertLess(sims['slow_baro_pressure_step']['max_z_error_m'],.04)
        self.assertGreater(result['flow_edges']['mixed_depth_trusted']['max_velocity_error_m_s'],.4)

    def test_real_mahony_dynamic_acceleration_is_not_a_validated_vertical_reference(self):
        x,trace=research.dynamic_attitude(self.lib)
        self.assertGreater(x['max_false_z_m'],1.)
        self.assertEqual(x['real_vertical_motion_m'],0)
        self.assertTrue(all(row[5]==0 for row in trace))
        self.assertGreater(max(row[6] for row in trace),.02)
        y,_=research.dynamic_attitude(self.lib,pulse=True)
        self.assertLess(abs(y['final_horizontal_velocity_m_s']),.01)
        self.assertGreater(y['final_horizontal_position_m'],1.)
        self.assertGreater(y['max_false_z_m'],.01)

    def test_bounded_gyro_only_attitude_removes_specific_acceleration_confounder(self):
        x,_=research.dynamic_attitude(self.lib,gyro_only=True)
        self.assertLess(x['max_false_z_m'],1e-5)
        y,_=research.dynamic_attitude(self.lib,pulse=True,gyro_only=True,gyro_bias_deg_s=.1)
        self.assertLess(y['max_false_z_m'],.01)
        failed,_=research.dynamic_attitude(self.lib,pulse=True,gyro_only=True,gyro_bias_deg_s=1.)
        self.assertGreater(failed['max_false_z_m'],.4)

    def test_slow_continuous_budget_pressure_step_against_equations(self):
        # Ideal zero-initial observer and constant pressure Bp: analytic response.
        s=hosted.init(self.lib,sz=0,sv=0,sb=0,qa=0,qb=0)
        for _ in range(400):
            research.predict(self.lib,s,0,.01)
            research.correct(self.lib,s,.3,slow=True,sample_dt=.01)
        expected=research.slow_error_bound(4,ez=0,ev=0,ba=0,bp=.3)
        self.assertAlmostEqual(s.x[0],expected,delta=1e-5)

    def test_joseph_covariance_is_symmetric_and_positive_semidefinite(self):
        s=hosted.init(self.lib)
        for i in range(10000):
            research.predict(self.lib,s,.01*math.sin(i*.01),.01)
            if i%2==0: research.correct(self.lib,s,.1*math.sin(i*.01))
            if i%50==0:
                p=s.p
                for j in range(3):
                    self.assertGreaterEqual(p[j][j],0)
                    for k in range(3):
                        self.assertLess(abs(p[j][k]-p[k][j]),1e-6)
                        self.assertGreaterEqual(p[j][j]*p[k][k]-p[j][k]**2,-1e-8)
                det=p[0][0]*(p[1][1]*p[2][2]-p[1][2]*p[2][1])-p[0][1]*(p[1][0]*p[2][2]-p[1][2]*p[2][0])+p[0][2]*(p[1][0]*p[2][1]-p[1][1]*p[2][0])
                self.assertGreaterEqual(det,-1e-9)

    def test_retained_archive_not_estimator_state_drives_vertical_replay(self):
        x=research.archive_replay(self.lib)
        self.assertEqual(x['rows'],{'imu':15016,'barometer':7508})
        self.assertFalse(x['physical_error_bound_validated'])
        self.assertFalse(x['producer_time_validated'])
        self.assertGreater(x['windows']['3']['fused_abs_nominal_displacement_m']['maximum'],.3)
        self.assertGreater(x['windows']['6']['slow_baro_abs_nominal_displacement_m']['maximum'],.05)
        self.assertGreater(x['continuous_slow_from_50s']['max_z_m'],.5)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--firmware',type=Path,required=True)
    args,remaining=parser.parse_known_args()
    FIRMWARE=args.firmware.resolve()
    unittest.main(argv=[__file__]+remaining)
