"""Offline integrity and bounded-observation verification; never launches Webots."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import zipfile
import analyze

HERE=Path(__file__).resolve().parent
def digest(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def archive(name,size,sha):
    raw=(HERE/'evidence'/name).read_bytes()
    require(len(raw)==size and digest(raw)==sha,'wrong original ZIP '+name)
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(z.testzip() is None,'bad CRC')
        manifest=json.loads(z.read('manifest.json'))
        require(len(manifest)==8 and set(z.namelist())==set(manifest)|{'manifest.json'},'wrong ZIP membership')
        for key,value in manifest.items():require(digest(z.read(key))==value,'wrong manifested bytes '+key)
        return {key:z.read(key) for key in z.namelist()}

def idle(data,case,journal=None):
    text=data[case+'.log'].decode()
    raw=[json.loads(l[3:]) for l in text.splitlines() if l.startswith('FX ')]
    events=journal if journal is not None else raw
    acks=[r for r in events if r['event']=='ACK_RESET']
    require(len(acks)==1,'ambiguous RESET acknowledgement')
    ack=acks[0]['time'];samples=[r for r in raw if r['event']=='sample']
    require(all(b['time']>a['time'] for a,b in zip(samples,samples[1:])),'nonmonotonic')
    origin=samples[0];checked=[]
    for prev,r in zip(samples,samples[1:]):
        if r['time']<=ack:continue
        for key in ('gps','rpy','gyro','native_velocity'):require(all(math.isfinite(v) for v in r[key]),'nonfinite data')
        dt=r['time']-prev['time'];vel=[(a-b)/dt for a,b in zip(r['gps'],prev['gps'])]
        pose=all(abs(a-b)<lim for a,b,lim in zip(r['gps'],origin['gps'],(.03,.03,.05)))
        pose=pose and all(abs(a-b)<2*math.pi/180 for a,b in zip(r['rpy'],origin['rpy']))
        motion=math.hypot(*vel[:2])<.12 and abs(vel[2])<.15 and abs(r['gyro'][2])<.10
        checked.append({'time':r['time'],'pose_ready':pose,'motion_ready':motion})
    require(data[case+'.exit']==b'0\n','native process refused')
    return {'ack':ack,'retained_post_ack_samples':len(checked),
            'retained_duration':round(samples[-1]['time']-ack,9),
            'predicate_violations':sum(not r['pose_ready'] or not r['motion_ready'] for r in checked)}

def main():
    a=archive('A-idle-original.zip',16459,'759cd7b53ad89b7ac5af7c092576f610cb5d1aae1bd6ce10a567bb7cd221ce29')
    b=archive('B-idle-original.zip',14838,'1fa91ff1aac6b999d9a28656766f90b5513e8104dcb8bbfcc3fcb83a95f26d88')
    journal=[json.loads(l) for l in b['B-idle.events.jsonl'].decode().splitlines()]
    # Preserve both original refusals instead of repairing data into a PASS.
    first=analyze.analyze(a['A-idle.log'].decode(),'idle')
    require(first==json.loads(a['A-idle.json']) and not first['completed'],'first refusal lost')
    try:analyze.analyze(b['B-idle.log'].decode(),'idle',journal)
    except ValueError as error:require(str(error)=='coast observation truncated','different second refusal')
    else:raise ValueError('second refusal incorrectly accepted')
    aa=idle(a,'A-idle');bb=idle(b,'B-idle',journal)
    require(aa=={'ack':4.512,'retained_post_ack_samples':50,'retained_duration':1.6,'predicate_violations':0},'A observations changed')
    require(bb=={'ack':4.704,'retained_post_ack_samples':49,'retained_duration':1.568,'predicate_violations':0},'B observations changed')
    require([r['time'] for r in journal if r['event']=='COMPLETE']==[6.304],'B final journal witness changed')
    for data in (a,b):
        require(json.loads(data['provenance.json'])['production_unchanged'],'production changed')
        require(not any('takeoff' in key for key in data),'unexpected native case')

    meta=json.loads((HERE/'evidence/SUBSETS.json').read_text())
    for name,spec in meta['files'].items():
        data=(HERE/'evidence'/name).read_bytes()
        require(len(data)==spec['bytes'] and digest(data)==spec['sha256'],'wrong subset bytes '+name)
    def rows(name):return [json.loads(l) for l in gzip.decompress((HERE/'evidence'/name).read_bytes()).splitlines()]
    native=[r for r in rows('prior-physics-state.jsonl.gz') if r.get('type')=='sample']
    consumed=[r for r in rows('prior-consumed-state.jsonl.gz') if r.get('type')=='sample']
    index={round(r['time'],9):r for r in native}
    prior=json.loads((HERE/'PRIOR_POST_ACK.json').read_text())
    require(len(prior['resets'])==14,'wrong RESET count')
    for r in prior['resets']:
        at=index[round(r['ack'],9)]
        require(at['motor_current']==r['current_at_ack'],'ACK current changed')
        require(sum(at['propeller_thrust'])==r['total_thrust_at_ack'],'ACK thrust changed')
        selected=[n for n in native if n['time']>=r['ack']-1e-9 and n['time']<=(r['next_nonzero_target'] or r['ack']+1.6)+1e-9]
        require(all(abs(b['time']-a['time']-.032)<1e-8 for a,b in zip(selected,selected[1:])),'native subset has a gap')
        zero=next(n['time'] for n in selected if all(v==0 for v in n['motor_current']))
        require(zero==r['extinction'],'extinction changed')
        selected=[n for n in consumed if n['time']>r['ack'] and n['time']<=(r['next_nonzero_target'] or r['ack']+1.6)+1e-9]
        require(all(abs(b['time']-a['time']-.032)<1e-8 for a,b in zip(selected,selected[1:])),'target subset has a gap')
        next_target=next((n['time'] for n in selected if any(n['motor_targets'])),None)
        require(next_target==r['next_nonzero_target'],'next target changed')
        require(next_target is None or zero<next_target,'activation did not follow extinction')
    print(json.dumps({'integrity':'verified','A_retained':aa,'B_retained':bb,
                      'original_experimental_workflows':'both remain failure',
                      'takeoff_cases':'NOT EXECUTED','historical_637':'UNRESOLVED',
                      'prior_intervals_recalculated':14},indent=2))

if __name__=='__main__':main()
