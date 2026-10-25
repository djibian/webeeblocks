#!/usr/bin/env python3
"""Compare a fixed-force native intervention with untouched historical traces."""
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'native-contact-intervention'))
import analyze as base

PROTOCOL_SHA='f93a18c9144713597f8d431745d6a9c46663c89abeb62ed1b5603c13f2195ebe'

def validate_no_floor(p, row):
    dt=p['step_ms']/1000
    s,c=math.sin(p['pitch_rad']),math.cos(p['pitch_rad'])
    F=p['force_body_N'][2]
    world_force=[s*F,0,c*F]
    free=row['after']['velocity_6d']
    expected=list(p['velocity_6d'])
    for i in range(3):
        expected[i]+=world_force[i]*dt/p['mass_kg']
    expected[2]-=p['gravity_m_s2']*dt
    expected[4]+=p['torque_body_N_m'][1]*dt/p['inertia_diagonal_kg_m2'][1]
    base.require(base.close(free,expected,1e-10),'no-floor force/torque balance refutes intended protocol')
    return free,expected,world_force

def analyze(directory):
    old_sha=base.PROTOCOL_SHA
    try:
        base.PROTOCOL_SHA=PROTOCOL_SHA
        summary=base.analyze(directory)
    finally:
        base.PROTOCOL_SHA=old_sha
    p=base.load(directory/'protocol.json')
    rows=base.load(directory/'results.json')
    by_id={r['case']['id']:r for r in rows}
    dt=p['step_ms']/1000
    # Independent no-floor mechanics test: a wrapper accidentally applying a
    # torque vector as force must NOT qualify this acquisition.
    F=p['force_body_N'][2]
    free,expected,world_force=validate_no_floor(p,by_id['no-floor-control'])
    for row,item in zip(rows,summary['cases']):
        base.require(row.get('force_body_N')==p['force_body_N'] and
                     row.get('torque_body_N_m')==p['torque_body_N_m'],'fixed force/torque binding differs')
        item['inferred_net_contact_impulse_N_s']=[v-f*dt for v,f in
            zip(item['inferred_net_contact_impulse_N_s'],world_force)]
        item['inferred_net_angular_impulse_y_N_m_s']-=p['torque_body_N_m'][1]*dt
        item['inference_scope']='momentum balance after subtracting gravity and specified applied body force/torque'
    archive=HERE/'evidence/historical-fail.zip'
    base.require(hashlib.sha256(archive.read_bytes()).hexdigest()==p['historical_fail_zip_sha256'],
                 'historical archive SHA mismatch')
    with zipfile.ZipFile(archive) as z:
        base.require(z.testzip() is None,'historical ZIP CRC error')
        log=z.read('progression-neutral-start/webots.log').decode()
    history={};native={}
    for line in log.splitlines():
        if line.startswith('WEBEEBLOCKS_SEQUENCE_CI_LAND id=12 '):
            r={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
            history[round(r['t'],3)]=r
        if line.startswith('WEBEEBLOCKS_SEQUENCE_CI_LAND_NATIVE id=12 '):
            d=dict(re.findall(r'(\w+)=([^ ]+)',line))
            native[round(float(d['t']),3)]=[float(v) for v in d['velocity'].split(',')]
    checks=[]
    for t in (12.384,12.416):
        h,n=history[t],history[round(t+dt,3)]
        thrust=sum(4e-5*h['motor'+str(i)]**2 for i in range(1,5))
        inferred=p['mass_kg']*((n['vz']-h['vz'])/dt+p['gravity_m_s2'])
        predicted_z=thrust*math.cos(h['pitch'])
        checks.append(dict(time_s=t,predicted_force_z_N=predicted_z,
                           force_z_inferred_from_next_contact_free_velocity_N=inferred,
                           residual_N=predicted_z-inferred))
    h=history[12.448]
    base.require([h['motor'+str(i)] for i in range(1,5)]==p['motor_targets_rad_s'], 'targets differ from archive')
    forces=[4e-5*w*w for w in p['motor_targets_rad_s']]
    base.require(sum(forces)==F,'force not calculated from targets')
    actual=by_id['one-contact']['after']
    target=history[12.480]
    residuals=dict(position_m=[a-target[k] for a,k in zip(actual['position_m'],('x','y','z'))],
        velocity_6d=[a-b for a,b in zip(actual['velocity_6d'],native[12.480])],
        pitch_rad=math.atan2(actual['orientation'][2],actual['orientation'][8])-target['pitch'])
    summary.update(no_floor_mechanics=dict(observed_velocity_6d=free,expected_velocity_6d=expected),
                   contact_free_historical_force_checks=checks,
                   historical_next_step_residuals=residuals,
                   historical_archive_sha256=p['historical_fail_zip_sha256'],
                   scope='native first-contact command-force hypothesis; no PID feedback, continuation or product qualification')
    return summary

if __name__=='__main__':
    target=Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'evidence/acquisition-03'
    print(json.dumps(analyze(target),indent=2,allow_nan=False))
