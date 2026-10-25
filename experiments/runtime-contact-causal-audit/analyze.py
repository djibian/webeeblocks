#!/usr/bin/env python3
"""Offline archive audit; no Webots acquisition or trajectory repair claim."""
import argparse
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent / 'evidence'
EXPECTED = {
    'PASS': 'fda4b50ef668c9295b15e7cb3c916dcf29a55c2e52c8d405edb813e9097dcc47',
    'FAIL': 'c86dc896ffa8c605568b5dfac7ad86f070d4a49f44f08eef64160f93024b5178',
}
PID_BLOB = '2803b7d2f5a1189717712bf7c826b45cc171d201'

def parse(line):
    return dict(re.findall(r'(\w+)=([^ ]+)', line))

def cylinder_points(row):
    # Pure pitch specialization of R2025a collision_cylinder_plane.cpp's
    # parallel branch (sin(pitch)^2 < .001). Floor plane z=0; yaw=roll=0.
    theta = row['pitch']
    assert abs(row['roll']) < 1e-8 and math.sin(theta)**2 < .001
    x, y, z = row['x'], row['y'], row['z']
    s, c = math.sin(theta), math.cos(theta)
    center = [x-.015*s, y, z-.015*c]
    radial = [[.05*c, 0, -.05*s], [-.05*c, 0, .05*s],
              [0, .05, 0], [0, -.05, 0]]
    pts = [[center[i]+v[i] for i in range(3)] for v in radial]
    return sorted(p for p in pts if p[2] < 0)

class Actual(C.Structure):
    _fields_ = [(n, C.c_double) for n in ('roll','pitch','yaw_rate','altitude','vx','vy')]
class Desired(C.Structure):
    _fields_ = [(n, C.c_double) for n in ('roll','pitch','yaw_rate','altitude','vx','vy')]
class Gains(C.Structure):
    _fields_ = [(n, C.c_double) for n in ('kp_att_rp','kd_att_rp','kp_att_y','kd_att_y',
        'kp_vel_xy','kd_vel_xy','kp_z','kd_z','ki_z')]
class Control(C.Structure):
    _fields_ = [(n, C.c_double) for n in ('roll','pitch','yaw','altitude')]

def audit(path, label, lib):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED[label]
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        prefix = 'progression-neutral-start/'
        manifest = json.loads(z.read(prefix+'runtime-source-sha256.json'))
        for key in ('original', 'instrumented'):
            assert hashlib.sha256(z.read(prefix+f'runtime-{key}.c')).hexdigest() == manifest[key]
        log = z.read(prefix+'webots.log').decode()
    rows, native = {}, {}
    for line in log.splitlines():
        if line.startswith('WEBEEBLOCKS_SEQUENCE_CI_LAND id=12 '):
            d = {k: float(v) for k,v in parse(line).items()}
            rows[round(d['t'], 3)] = d
        elif line.startswith('WEBEEBLOCKS_SEQUENCE_CI_LAND_NATIVE id=12 '):
            d = parse(line)
            native[round(float(d['t']),3)] = d
    output = []
    g = Gains(.5,.1,1,.5,2,.5,10,5,5)
    max_residual = 0
    for t in (12.384,12.416,12.448,12.480,12.512):
        cur, prev, pp = (rows[round(t-k*.032,3)] for k in range(3))
        assert abs(cur['y']) < 1e-8 and abs(cur['vy']) < 1e-8
        # Reconstruct the two previous error states from consecutive logged
        # samples. These windows have zero yaw/roll to printed precision.
        old_des_pitch = -2*prev['vx']-.5*(prev['vx']-pp['vx'])/.032
        C.c_double.in_dll(lib,'pastVxError').value = -prev['vx']
        C.c_double.in_dll(lib,'pastVyError').value = 0
        C.c_double.in_dll(lib,'pastPitchError').value = old_des_pitch-prev['pitch']
        C.c_double.in_dll(lib,'pastRollError').value = 0
        a = Actual(cur['roll'],cur['pitch'],0,cur['z'],cur['vx'],0)
        d = Desired(0,0,0,cur['des_z'],0,0)
        lib.pid_horizontal_velocity_controller(a,C.byref(d),g,.032)
        control = Control()
        lib.pid_attitude_controller(a,C.byref(d),g,.032,C.byref(control))
        motors = [abs(cur[f'motor{i}']) for i in range(1,5)]
        assert min(motors)>0 and max(motors)<600
        observed = (motors[0]-motors[1]-motors[2]+motors[3])/4
        residual = abs(control.pitch-observed)
        max_residual = max(max_residual,residual)
        item = dict(t=t,x=cur['x'],z=cur['z'],vx=cur['vx'],pitch=cur['pitch'],
                    des_pitch_replayed=d.pitch,pitch_mix_replayed=control.pitch,
                    pitch_mix_observed=observed,residual=residual,
                    contacts=int(native[t]['contacts']))
        if abs(cur['pitch'])<.031:
            predicted = cylinder_points(cur)
            observed_pts = sorted([[float(v) for v in native[t][k].split(':')[1].split(',')]
                                   for k in native[t] if k.startswith('cp')])
            assert len(predicted)==len(observed_pts)==item['contacts']
            err=max((abs(a-b) for p,q in zip(predicted,observed_pts) for a,b in zip(p,q)),default=0)
            assert err<1e-8, err
            item.update(collider_points=predicted,collider_max_coordinate_error_m=err)
        output.append(item)
    assert max_residual < 1e-6, max_residual
    if label=='FAIL':
        r=rows[12.448].copy()
        counter=[]
        for dz in (0,.000186368,-.000046):
            r['z']=rows[12.448]['z']+dz
            counter.append(dict(dz_m=dz,contacts=len(cylinder_points(r)),points=cylinder_points(r)))
    else:
        counter=[]
    return dict(archive_sha256=EXPECTED[label],source_sha256=manifest,
                max_pid_pitch_residual=max_residual,samples=output,
                collider_counterfactuals=counter)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pass-zip',type=Path,default=EVIDENCE/'12593429251.zip')
    ap.add_argument('--fail-zip',type=Path,default=EVIDENCE/'12594851352.zip')
    ap.add_argument('--environment-pass-zip',type=Path,default=EVIDENCE/'12615475360.zip')
    ap.add_argument('--environment-fail-zip',type=Path,default=EVIDENCE/'12615774377.zip')
    args=ap.parse_args()
    source=ROOT/'controllers/crazyflie_square/pid_controller.c'
    raw=source.read_bytes()
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==PID_BLOB
    with tempfile.TemporaryDirectory() as temp:
        so=Path(temp)/'pid.so'
        subprocess.run(['gcc','-shared','-fPIC','-O0',str(source),'-lm','-o',str(so)],check=True)
        lib=C.CDLL(str(so))
        lib.pid_horizontal_velocity_controller.argtypes=[Actual,C.POINTER(Desired),Gains,C.c_double]
        lib.pid_attitude_controller.argtypes=[Actual,C.POINTER(Desired),Gains,C.c_double,C.POINTER(Control)]
        out={label:audit(path,label,lib) for label,path in [('PASS',args.pass_zip),('FAIL',args.fail_zip)]}
    out['scope']='offline geometry + compiled production PID replay; no native counterfactual trajectory'
    pair=[]
    for path,digest,status in [
        (args.environment_pass_zip,'3b9ea3bc867a1c226f80e02f4403674f391cb22ea51408c02398d4a7fd91c250','achieved'),
        (args.environment_fail_zip,'6e71e2b711c03a1f6f2851a5683c4d8ca9f8303f618869bd00b05c76d4889eb0','not-achieved')]:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            files={n:z.read('progression-neutral-start/'+n) for n in (
                'effective-runtime-environment.json','native-context.json',
                'runtime-original.c','runtime-instrumented.c','build.log')}
            log=z.read('progression-neutral-start/webots.log').decode().splitlines()
        assert f'WEBEEBLOCKS_SEQUENCE_RESULT attempt=1 status={status}' in log
        first=next(i for i,l in enumerate(log) if l.startswith('WEBEEBLOCKS_SEQUENCE_CI_LAND_NATIVE id=12 ')
                   and 'contacts=0 ' not in l)
        row={k:float(v) for k,v in parse(log[first-1]).items()}
        nat=parse(log[first])
        predicted=cylinder_points(row)
        pts=sorted([[float(v) for v in nat[k].split(':')[1].split(',')] for k in nat if k.startswith('cp')])
        assert len(predicted)==len(pts)==int(nat['contacts'])
        error=max(abs(a-b) for p,q in zip(predicted,pts) for a,b in zip(p,q))
        assert error<1e-8
        pair.append(dict(archive_sha256=digest,outcome=status,
            file_sha256={n:hashlib.sha256(v).hexdigest() for n,v in files.items()},
            environment=json.loads(files['effective-runtime-environment.json']),
            first_contact=row,predicted_contact_points=predicted,
            first_contact_count=len(pts),collider_max_coordinate_error_m=error))
    assert pair[0]['file_sha256']==pair[1]['file_sha256']
    out['environment_pair']=pair
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    main()
