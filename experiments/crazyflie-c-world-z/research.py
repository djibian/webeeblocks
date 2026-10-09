#!/usr/bin/env python3
"""Reproducible Lab-only experiment; calculations never grant physical authority."""
from __future__ import annotations
import argparse
import bisect
import csv
import ctypes as ct
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import tempfile
from hosted import HERE, LOCK, WorldZ, attitude, build, flow, init, project

REPO = HERE.parents[1]
ARCHIVE = REPO/'experiments/crazyflie-ukf-surface-range/evidence/checkpoint-561-4ca2d1e3b355'
G = 9.81
# Research comparison profile declared in code, NOT fitted on archive windows.
# These are design assumptions; covariance is not a deterministic error bound.
PROFILE = dict(sz=0.005, sv=0.02, sb=0.00981, qa=0.0009, qb=0.000001)
BARO_R = 0.25
SLOW_OMEGA = 0.01 # 100 s pole time, deliberate low authority over <=6 s

def predict(lib, s, a, dt):
    if not lib.world_z_predict(ct.byref(s), a, dt):
        raise ValueError('observer prediction failed closed')

def correct(lib, s, baro, r=BARO_R, *, slow=False, sample_dt=.02):
    ok=lib.world_z_slow_baro(ct.byref(s),baro,r,sample_dt,SLOW_OMEGA) if slow else lib.world_z_baro(ct.byref(s),baro,r)
    if not ok:
        raise ValueError('observer barometer failed closed')

def percentile(values, q):
    x=sorted(values)
    return x[max(0,math.ceil(q*len(x))-1)]

def metrics(values):
    return dict(count=len(values), median=st.median(values), p95=percentile(values,.95), maximum=max(values))

def slow_error_bound(t, *, ez=.005, ev=.02, ba=.00981, bp=.3, omega=SLOW_OMEGA):
    """Continuous observer L-infinity bound for 0<=omega*T<=1.

    ba includes all world-acceleration projection/model error; bp includes datum,
    dynamics, lag and pressure error. Sample-time/numerical/control terms are
    separate, so this is not a firmware or physical clearance certificate.
    """
    u=omega*t
    if not 0<=u<=1: raise ValueError('bound restricted to omega*T<=1')
    e=math.exp(-u)
    return e*((1-u)*ez+t*ev)+ba*(1-(1+u)*e)/omega**2+bp*(1+(u-1)*e)

def read_rows(path):
    with path.open(newline='') as f:
        rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
    if not rows or any(not math.isfinite(v) for r in rows for v in r.values()):
        raise ValueError('empty/non-finite archived input')
    t=[r['cf_timestamp_ms'] for r in rows]
    if any(b<=a for a,b in zip(t,t[1:])):
        raise ValueError('non-increasing device log time')
    return rows

def verify_archive(root=ARCHIVE):
    manifest=(root/'MANIFEST.sha256').read_text().splitlines()
    for entry in manifest:
        digest, relative=entry.split('  ',1)
        if hashlib.sha256((root/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'archive mismatch: {relative}')
    return len(manifest)

def archive_replay(lib):
    count=verify_archive()
    raw=ARCHIVE/'raw/captures/cycle1-stationary-01/raw'
    imu=read_rows(raw/'imu.csv'); baro=read_rows(raw/'barometer.csv')
    t0=imu[0]['cf_timestamp_ms']
    def elapsed(r): return (r['cf_timestamp_ms']-t0)/1000
    # Reuse real Mahony algorithm on the recorded 100 Hz samples. This is NOT
    # the 250 Hz complementary firmware loop or a producer-time reconstruction.
    lib.lab_attitude_reset()
    projected=[]
    last=None
    for row in imu:
        t=elapsed(row); dt=.01 if last is None else t-last
        q=attitude(lib,[row[f'acc.{a}'] for a in 'xyz'],[row[f'gyro.{a}'] for a in 'xyz'],dt)
        projected.append(project(lib,q,[row[f'acc.{a}'] for a in 'xyz']))
        last=t
    times=[elapsed(r) for r in imu]
    bt=[elapsed(r) for r in baro]
    calibration=[a for t,a in zip(times,projected) if 20<=t<50]
    bcal=[r['baro.asl'] for t,r in zip(bt,baro) if 20<=t<50]
    bias=st.median(calibration); origin=st.median(bcal)
    # Every integer-tenth anchor in the declared 51..117-T domain is retained.
    windows={}
    for horizon in [0.5,1,2,3,4,5,6]:
        dz_inertial=[]; dz_fused=[]; dz_slow=[]; dz_pressure=[]; uncertainty=[]
        for tick in range(510, int(round((117-horizon)*10))+1):
            start=tick/10; end=start+horizon
            inertial=init(lib,bias=bias,**PROFILE); fused=init(lib,bias=bias,**PROFILE)
            slow=init(lib,bias=bias,**PROFILE)
            lo=bisect.bisect_left(times,start); hi=bisect.bisect_right(times,end)
            # Integer timestamp grid; no hidden interpolation or fitted attitude.
            if abs(times[lo]-start)>1e-8 or abs(times[hi-1]-end)>1e-8:
                raise ValueError('unexpected archive anchor grid')
            pre=[r['baro.asl'] for r in baro[bisect.bisect_left(bt,start-.5):bisect.bisect_left(bt,start)]]
            post=[r['baro.asl'] for r in baro[bisect.bisect_left(bt,end):bisect.bisect_left(bt,end+.5)]]
            anchor_b=st.median(pre)
            # Strictly later samples: never give a start-time sample an extra
            # full correction period. Slow gains use observed log cadence.
            bi=bisect.bisect_right(bt,start)
            for k in range(lo+1,hi):
                dt=times[k]-times[k-1]
                a=(projected[k-1]+projected[k])/2
                predict(lib,inertial,a,dt)
                predict(lib,fused,a,dt)
                predict(lib,slow,a,dt)
                # Causal event processing with stale (<=10 ms) barometer samples;
                # logs have no verified producer timestamps. No future sample used.
                while bi<len(bt) and bt[bi]<=times[k]:
                    correct(lib,fused,baro[bi]['baro.asl']-anchor_b)
                    sample_dt=bt[bi]-bt[bi-1]
                    correct(lib,slow,baro[bi]['baro.asl']-anchor_b,slow=True,sample_dt=sample_dt)
                    bi+=1
            dz_inertial.append(abs(inertial.x[0]))
            dz_fused.append(abs(fused.x[0]))
            dz_slow.append(abs(slow.x[0]))
            dz_pressure.append(abs(st.median(post)-anchor_b))
            uncertainty.append(math.sqrt(fused.p[0][0]))
        windows[str(horizon)]={
            'inertial_abs_nominal_displacement_m':metrics(dz_inertial),
            'fused_abs_nominal_displacement_m':metrics(dz_fused),
            'slow_baro_abs_nominal_displacement_m':metrics(dz_slow),
            'baro_abs_plateau_change_m':metrics(dz_pressure),
            'fused_sigma_z_m':metrics(uncertainty),
        }
    # One continuous replay, no rolling reset: checks pressure long-horizon cost.
    s=init(lib,bias=bias,**PROFILE); slow=init(lib,bias=bias,**PROFILE)
    bi=bisect.bisect_right(bt,50)
    full=[]; full_slow=[]; prior=50.0
    for k in range(bisect.bisect_right(times,50),len(times)):
        dt=times[k]-prior; prior=times[k]
        predict(lib,s,(projected[k-1]+projected[k])/2,dt)
        predict(lib,slow,(projected[k-1]+projected[k])/2,dt)
        while bi<len(bt) and bt[bi]<=times[k]:
            correct(lib,s,baro[bi]['baro.asl']-origin)
            correct(lib,slow,baro[bi]['baro.asl']-origin,slow=True,sample_dt=bt[bi]-bt[bi-1])
            bi+=1
        full.append(s.x[0])
        full_slow.append(slow.x[0])
    return dict(manifest_files_verified=count,rows={'imu':len(imu),'barometer':len(baro)},
        calibration_log_seconds=[20,50],evaluation_log_seconds=[51,117],
        projected_calibration_median_m_s2=bias,
        baro_calibration_origin_m=origin,
        baro_span_m=max(r['baro.asl'] for r in baro)-min(r['baro.asl'] for r in baro),
        windows=windows,continuous_from_50s={'min_z_m':min(full),'max_z_m':max(full),'final_z_m':full[-1]},
        continuous_slow_from_50s={'min_z_m':min(full_slow),'max_z_m':max(full_slow),'final_z_m':full_slow[-1]},
        scope='DESCRIPTIVE_PROPS_OFF_REPLAY; initial v=0 and stationary holds assumed, not measured per window',
        producer_time_validated=False,physical_error_bound_validated=False,
        source_sha256={name:hashlib.sha256((raw/name).read_bytes()).hexdigest()
                       for name in ['imu.csv','barometer.csv']})

def vertical_motion(t):
    # 20 cm true vertical out-and-back with zero initial/final velocity.
    if not 1<=t<=5: return 0.,0.,0.
    w=math.pi/4; u=w*(t-1)
    return .2*math.sin(u)**2,.2*w*math.sin(2*u),.4*w*w*math.cos(2*u)

def synth(lib, *, mixed=False, pressure_step=0., pressure_ramp=0., accel_bias=0.,
          dropout=False, initial_velocity=0., use_baro=True, closed_loop=False, slow=False):
    dt=.01; s=init(lib,z=1.1,**PROFILE)
    max_error=0; z=1.1; v=initial_velocity; baro=1.1
    trace=[]
    for i in range(1,801):
        t=i*dt
        if closed_loop:
            # Explicit ideal double-integrator, bounded PD, NOT a Crazyflie PID,
            # power distribution, rotor/airframe or full firmware simulation.
            a=max(-2,min(2,4*(1.1-s.x[0])-3*s.x[1]))
            z+=v*dt+.5*a*dt*dt; v+=a*dt
        else:
            dz,v,a=vertical_motion(t) if mixed else (0.,initial_velocity,0.)
            z=1.1+dz+initial_velocity*t
        measured_a=a+accel_bias
        predict(lib,s,measured_a,dt)
        pressure=z+pressure_step*(t>=2)+pressure_ramp*t
        baro+=(1-math.exp(-dt/.06))*(pressure-baro) # assumed 60 ms sensor lag
        if use_baro and i%2==0 and not (dropout and 2<=t<=5):
            correct(lib,s,baro,slow=slow)
        max_error=max(max_error,abs(s.x[0]-z))
        local=z-(.75 if 2<=t<6 else 0)
        trace.append([t,z,s.x[0],s.x[1],local,a,measured_a])
    return dict(max_z_error_m=max_error,final_z_error_m=s.x[0]-z,
                max_real_z_excursion_m=max(abs(r[1]-1.1) for r in trace),
                healthy=s.healthy,trace=trace)

def flow_edges(lib):
    dt=.01; vx=.4; floor=1.1; table=.35
    results={}
    for case in ['single_plane','mixed_depth_trusted','mixed_depth_rejected','stale_range']:
        drift=0.; max_v_error=0.; coast_time=0.
        for i in range(800):
            t=i*dt
            range_m=table if 2<=t<6 else floor
            alpha=1. if 2.6<=t<=5.4 else 0.
            if 1.4<=t<2.6: alpha=(t-1.4)/1.2
            if 5.4<t<=6.6: alpha=(6.6-t)/1.2
            ambiguous=0<alpha<1
            phi=vx/range_m if case=='single_plane' else vx*((1-alpha)/floor+alpha/table)
            raw=phi*dt*35/.71674/.1
            plane=not (case=='mixed_depth_rejected' and ambiguous)
            age=.04 if case=='stale_range' and ambiguous else 0
            result=flow(lib,raw,0,dt,range_m,age=age,plane=plane)
            if result is None:
                # An ideal coast proxy with explicit residual 5 mg; NOT hardware.
                coast_time+=dt; measured=vx+.005*G*coast_time
            else:
                coast_time=0; measured=result[0]
            drift+=(measured-vx)*dt; max_v_error=max(max_v_error,abs(measured-vx))
        results[case]=dict(net_odometry_error_m=drift,max_velocity_error_m_s=max_v_error,
                           scene_validity_known=case=='mixed_depth_rejected')
    return results

def dynamic_attitude(lib, *, pulse=False, gyro_only=False, gyro_bias_deg_s=0):
    """Real Mahony algorithm + C2 on declared accelerometer dynamics.

    Continuous external horizontal force at level is a counter-model, not
    representative quadrotor flight. Pulse case models tilted thrust, vertical
    force compensated, accelerating then braking with an intervening cruise.
    """
    lib.lab_attitude_reset()
    for _ in range(2000): attitude(lib,[0,0,1],[0,0,0],.01)
    if gyro_only: lib.lab_attitude_gyro_only()
    s=init(lib,**PROFILE); max_z=0; theta_prev=0; trace=[]; vx=0; x=0
    target=math.atan(1/9.81)
    for i in range(1,801):
        t=i*.01
        if pulse:
            theta=0.
            for start,sign in [(.2,1),(3.2,-1)]:
                u=t-start
                if 0<=u<.2: theta=sign*target*u/.2
                elif .2<=u<.4: theta=sign*target
                elif .4<=u<.6: theta=sign*target*(.6-u)/.2
            acc=[0,0,1/math.cos(theta)]
            gyro=[0,(theta-theta_prev)/.01*180/math.pi,0]
            horizontal_acc=9.81*math.tan(theta)
            theta_prev=theta
        else:
            acc=[1/9.81,0,1]; gyro=[0,0,0]; horizontal_acc=1
        gyro[1]+=gyro_bias_deg_s
        q=attitude(lib,acc,gyro,.01); a=project(lib,q,acc)
        predict(lib,s,a,.01)
        if i%2==0: correct(lib,s,0,slow=True)
        max_z=max(max_z,abs(s.x[0]))
        x+=vx*.01+.5*horizontal_acc*.01**2; vx+=horizontal_acc*.01
        trace.append([t,1.1,1.1+s.x[0],s.x[1],1.1,0.,a])
    return dict(max_false_z_m=max_z,final_false_z_m=s.x[0],
                final_horizontal_velocity_m_s=vx,final_horizontal_position_m=x,
                real_vertical_motion_m=0,gyro_only=gyro_only,gyro_bias_deg_s=gyro_bias_deg_s,
                scope='TILTED_THRUST_PULSE_MODEL' if pulse else 'EXTERNAL_FORCE_AT_LEVEL_COUNTERMODEL'),trace

def scientific_results(lib):
    cases={
       'ideal_table_world_z':{},
       'true_vertical_and_table':{'mixed':True},
       'residual_1mg_baro':{'accel_bias':.001*G},
       'residual_5mg_imu_only':{'accel_bias':.005*G,'use_baro':False},
       'baro_dropout_3s_5mg':{'dropout':True,'accel_bias':.005*G},
       'pressure_step_30cm':{'pressure_step':.3},
       'pressure_ramp_1cm_s':{'pressure_ramp':.01},
       'initial_v_error_2cm_s':{'initial_velocity':.02},
       'closed_loop_ideal':{'closed_loop':True},
       'closed_loop_pressure_step':{'closed_loop':True,'pressure_step':.3},
       'slow_baro_pressure_step':{'slow':True,'pressure_step':.3},
       'slow_baro_true_vertical':{'slow':True,'mixed':True},
       'slow_baro_1mg':{'slow':True,'accel_bias':.001*G},
       'slow_baro_closed_loop_pressure':{'slow':True,'closed_loop':True,'pressure_step':.3},
    }
    sims={}; traces={}
    for name,params in cases.items():
        result=synth(lib,**params); traces[name]=result.pop('trace'); sims[name]=result
    attitude_cases={}
    for name,pulse in [('external_horizontal_force',False),('tilted_accel_cruise_brake',True)]:
        result,trace=dynamic_attitude(lib,pulse=pulse)
        attitude_cases[name]=result; traces[name]=trace
    for name,pulse,bias in [('gyro_only_external_force',False,0),
                            ('gyro_only_tilted_pulse',True,0),
                            ('gyro_only_pulse_bias_0p1deg_s',True,.1),
                            ('gyro_only_pulse_bias_1deg_s',True,1.)]:
        result,trace=dynamic_attitude(lib,pulse=pulse,gyro_only=True,gyro_bias_deg_s=bias)
        attitude_cases[name]=result; traces[name]=trace
    # Construct exact sensor-identical worlds, independent of the implementation.
    # delta=.1*(1-cos(pi*t/4)) => 20 cm at 4 s, initial delta=delta'=0.
    # z'=z+delta, ba'=ba-delta'', bp'=bp-delta, h'=h+delta.
    residuals=[]
    for i in range(401):
        t=i*.01; w=math.pi/4; d=.1*(1-math.cos(w*t)); dd=.1*w*w*math.cos(w*t)
        z=1.1; h=.75 if 1<=t<=3 else 0
        first=(0.,z,z-h); second=(dd-dd,z+d-d,z+d-(h+d))
        residuals.extend(abs(a-b) for a,b in zip(first,second))
    indistinguishable=dict(max_sensor_difference=max(residuals),world_z_difference_m=.2,
        allowed_accel_bias_amplitude_m_s2=.1*(math.pi/4)**2,
        allowed_pressure_altitude_bias_amplitude_m=.2,
        assumption='unbounded/unvalidated pressure and time-varying accelerometer biases; unknown terrain')
    budget=[]
    for t in [1,2,3,4,5,6]:
        for mg in [1,5,10]:
            budget.append(dict(duration_s=t,bias_mg=mg,
              conditional_z_bound_m=.005+.02*t+.5*mg*.001*G*t*t,
              bounds_physically_validated=False))
    slow_budget=[dict(duration_s=t,conditional_z_bound_m=slow_error_bound(t),
                     residual_acceleration_m_s2=.00981,pressure_altitude_error_m=.3,
                     bounds_physically_validated=False) for t in [1,2,3,4,5,6]]
    return dict(profile=PROFILE,baro_variance_m2=BARO_R,slow_omega_rad_s=SLOW_OMEGA,
                firmware_measurement_refutations={
                  'stock_tof_world_z_after_75cm_step_m':lib.lab_stock_tof(1.1,.35),
                  'stock_flow_world_z_after_depth_step_m':lib.lab_stock_flow_z(1.1,.4,.35,0),
                  'zero_direct_hz_covariance_z_step_m':lib.lab_zero_hz_coupling()},
                simulations=sims,flow_edges=flow_edges(lib),dynamic_attitude=attitude_cases,
                sensor_indistinguishability=indistinguishable,conditional_inertial_budget=budget,
                conditional_slow_observer_budget=slow_budget,
                flight_qualified=False),traces

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c-world-z-') as tmp:
        lib=build(Path(tmp),args.firmware.resolve())
        results,traces=scientific_results(lib)
        results.update(schema='webeeblocks.c-world-z.research.v1',upstream=LOCK['commit'],archive=archive_replay(lib))
    (args.output/'results.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
    with (args.output/'simulations.csv').open('w',newline='') as out:
        writer=csv.writer(out); writer.writerow(['case','time_s','truth_z_m','estimate_z_m','estimate_vz_m_s','local_depth_m','truth_acc_m_s2','measured_world_acc_m_s2'])
        for name,rows in traces.items():
            for row in rows: writer.writerow([name]+row)
    print(json.dumps({'result':'COMPUTED_LAB_EVIDENCE','output':str(args.output),'flight_qualified':False}))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
