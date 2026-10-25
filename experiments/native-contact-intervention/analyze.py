#!/usr/bin/env python3
"""Validate native evidence and report observations; never produces product GO."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from run import world

PROTOCOL_SHA = '4a626ae5acb99d3a4b81c2ce83c75f38b195849580ec1894b09f103a78cf76c0'

def require(condition, message):
    if not condition:
        raise ValueError(message)

def load(path):
    def reject(value):
        raise ValueError('nonfinite JSON token: '+value)
    return json.loads(path.read_text(), parse_constant=reject)

def finite_vector(value, size):
    require(isinstance(value, list) and len(value)==size and
            all(type(v) in (int,float) and math.isfinite(v) for v in value), 'invalid numeric vector')

def close(a, b, tol=1e-12):
    return len(a)==len(b) and all(abs(x-y)<=tol for x,y in zip(a,b))

def predicted_contacts(p, case):
    if not case['floor']:
        return []
    x,y,z = p['position_m']
    z += case['dz_m']
    s,c = math.sin(p['pitch_rad']),math.cos(p['pitch_rad'])
    h,r = p['height_m']/2,p['radius_m']
    center = [x-h*s,y,z-h*c]
    points = [[center[i]+v[i] for i in range(3)] for v in
              ([r*c,0,-r*s],[-r*c,0,r*s],[0,r,0],[0,-r,0])]
    return sorted(pt for pt in points if pt[2]<0)

def analyze(directory):
    raw = (directory/'protocol.json').read_bytes()
    protocol_sha = hashlib.sha256(raw).hexdigest()
    require(protocol_sha==PROTOCOL_SHA, 'protocol differs from the preregistered acquisition')
    p = load(directory/'protocol.json')
    manifest = load(directory/'sha256.json')
    actual = {str(f.relative_to(directory)):hashlib.sha256(f.read_bytes()).hexdigest()
              for f in directory.rglob('*') if f.is_file() and f.name!='sha256.json'}
    require(actual==manifest, 'incomplete or modified archive inventory')
    provenance = load(directory/'provenance.json')
    require(provenance['protocol_sha256']==protocol_sha, 'provenance protocol mismatch')
    require(provenance['webots_bin_sha256']==p['webots_bin_sha256'], 'native binary mismatch')
    rows = load(directory/'results.json')
    require([r['case'] for r in rows]==p['cases'], 'missing, duplicate or reordered cases')
    summaries = []
    for row,case in zip(rows,p['cases']):
        d = directory/case['id']
        require(load(d/'result.json')==row, 'aggregate/raw result mismatch')
        require(row['protocol_sha256']==protocol_sha and row['steps_executed']==1, 'wrong acquisition binding')
        target = directory/'worlds'/f"{case['id']}.wbt"
        require(target.read_text()==world(p,case), 'native world differs from fixed fixture')
        markers = [json.loads(s.split(' ',1)[1]) for s in (d/'controller.log').read_text().splitlines()
                   if s.startswith('NATIVE_CONTACT_ONE_STEP ')]
        require(markers==[row], 'native controller observation absent or ambiguous')
        b,a = row['before'],row['after']
        require(b['time_s']==0 and a['time_s']==p['step_ms']/1000, 'not one physical step from t=0')
        for state in (b,a):
            for field,size in [('position_m',3),('velocity_6d',6),('orientation',9)]:
                finite_vector(state[field],size)
            for contact in state['contacts']:
                finite_vector(contact['point'],3)
        pos = list(p['position_m']); pos[2] += case['dz_m']
        require(close(b['position_m'],pos) and close(b['velocity_6d'],p['velocity_6d']), 'initial state mismatch')
        s,c = math.sin(p['pitch_rad']),math.cos(p['pitch_rad'])
        require(close(b['orientation'],[c,0,s,0,1,0,-s,0,c]), 'initial orientation mismatch')
        predicted = predicted_contacts(p,case)
        observed = sorted(contact['point'] for contact in b['contacts'])
        require(len(observed)==case['predicted_contacts']==len(predicted), 'input manifold count mismatch')
        require(all(close(x,y) for x,y in zip(predicted,observed)), 'input contact geometry mismatch')
        dt = p['step_ms']/1000
        free = [0,0,-p['gravity_m_s2']*dt]
        impulse = [p['mass_kg']*(a['velocity_6d'][i]-b['velocity_6d'][i]-free[i]) for i in range(3)]
        angular_impulse_y = p['inertia_diagonal_kg_m2'][1]*(a['velocity_6d'][4]-b['velocity_6d'][4])
        # Pure pitch keeps world Y a principal axis. This is an inference from
        # momentum balance, not direct force, joint-feedback or solver telemetry.
        summaries.append(dict(id=case['id'], dz_m=case['dz_m'],
            contacts_before=len(observed),contacts_after=len(a['contacts']),
            vx_after_m_s=a['velocity_6d'][0],vz_after_m_s=a['velocity_6d'][2],
            omega_y_after_rad_s=a['velocity_6d'][4],
            pitch_after_rad=math.atan2(a['orientation'][2],a['orientation'][8]),
            inferred_net_contact_impulse_N_s=impulse,
            inferred_net_angular_impulse_y_N_m_s=angular_impulse_y,
            inference_scope='momentum balance with specified mass/inertia, gravity and no actuation'))
    return dict(protocol_sha256=protocol_sha, cases=summaries,
                scope='native reduced-fixture observations only; not a historical replay or product verdict')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    try:
        print(json.dumps(analyze(args.directory),indent=2,allow_nan=False))
    except (ValueError,KeyError,OSError) as exc:
        sys.exit('EVIDENCE REFUSED: '+str(exc))
