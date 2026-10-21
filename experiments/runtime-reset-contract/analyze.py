"""Report preserved original predicates and events; never relabel a refusal."""
import json
import math
from pathlib import Path
import sys

def analyze(text,mode,journal=None):
    rows=[json.loads(line[3:]) for line in text.splitlines() if line.startswith('FX ')]
    if journal is not None:
        # Samples remain the original stdout observations. Only control events
        # come from the separately persisted journal, including exit witnesses.
        rows=[r for r in rows if r['event'] in ('sample','target')]+journal
    samples=[r for r in rows if r['event']=='sample']
    if not samples or any(not math.isfinite(x) for r in samples for key in ('gps','rpy','gyro','native_velocity') for x in r[key]):
        raise ValueError('missing/nonfinite physical data')
    if any(b['time']<=a['time'] for a,b in zip(samples,samples[1:])):raise ValueError('nonmonotonic samples')
    def one(name):
        a=[r for r in rows if r['event']==name]
        if len(a)!=1:raise ValueError('missing/duplicate '+name)
        return a[0]
    begin=one('REQUEST_RESET')['time'];ack=one('ACK_RESET')['time']
    if not 0.25<=ack-begin<=5.0:raise ValueError('RESET latency outside original bounds')
    origin=samples[0]
    checked=[]
    for previous,r in zip(samples,samples[1:]):
        if not ack<r['time']:continue
        dt=r['time']-previous['time'];v=[(a-b)/dt for a,b in zip(r['gps'],previous['gps'])]
        pose=all(abs(a-b)<limit for a,b,limit in zip(r['gps'],origin['gps'],(.03,.03,.05))) and all(abs(a-b)<2*math.pi/180 for a,b in zip(r['rpy'],origin['rpy']))
        motion=math.hypot(*v[:2])<.12 and abs(v[2])<.15 and abs(r['gyro'][2])<.10
        checked.append({'time':r['time'],'pose_ready':pose,'motion_ready':motion})
    completed=len([r for r in rows if r['event']=='COMPLETE'])==1 and not any(r['event'] in ('FAILED','FIXTURE_DEADLINE') for r in rows) and not any(' ERR ' in r.get('message','') for r in rows)
    result={'completed':completed,'reset_latency':round(ack-begin,9),'post_ack_samples':len(checked),'scope':'bounded fixture, not #637 resolution'}
    if mode=='idle':
        if not checked or checked[-1]['time']-ack<1.6:raise ValueError('coast observation truncated')
        result['post_ack_predicate_violations']=[r for r in checked if not r['pose_ready'] or not r['motion_ready']]
    else:
        start=one('REQUEST_TAKEOFF')['time'];end=one('ACK_TAKEOFF')['time'];land=one('ACK_LAND')['time']
        if abs(start-ack-.032)>1e-8:raise ValueError('not first-step TAKEOFF')
        result.update(takeoff_latency=round(end-start,9),land_ack=land,first_step_takeoff=True,
                      max_horizontal_excursion=max(math.hypot(r['gps'][0]-origin['gps'][0],r['gps'][1]-origin['gps'][1]) for r in samples if r['time']>=ack))
    return result

if __name__=='__main__':
    journal=[json.loads(l) for l in Path(sys.argv[3]).read_text().splitlines()] if len(sys.argv)>3 else None
    print(json.dumps(analyze(Path(sys.argv[1]).read_text(),sys.argv[2],journal),indent=2))
