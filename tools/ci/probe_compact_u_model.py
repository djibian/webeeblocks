#!/usr/bin/env python3
"""Independent unchanged world oracle applied to explicitly ideal motion.

No Webots, PID, ACK convergence, attitude, noise or real deadline claim.
The program builder never receives a layout; only the simulated sensor does.
"""
import collections
import dataclasses
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.grand_prix.layout_u import generate
from tools.grand_prix.oracle_u import Attempt


def probe():
    layouts={}
    # All 99 combinations allowed by the generator's public discrete positions.
    for seed in range(65536):
        layout=generate(seed)
        key=tuple((g.side,g.distance) for g in layout.gates)
        layouts.setdefault(key,layout)
        if len(layouts)==99:break
    if len(layouts)!=99:raise RuntimeError('incomplete geometry enumeration')
    cases=[{'layout':dataclasses.asdict(layout),'options':{}} for layout in layouts.values()]
    # Sensitivity experiments, not calibrated error bounds or random trials.
    for scale,yaw in [(.98,0),(1.02,0),(1,-1),(1,1)]:
        cases += [{'layout':dataclasses.asdict(layout),'options':{'scale':scale,'yawError':yaw}}
                  for layout in layouts.values()]
    p=subprocess.Popen(['node','tools/grand_prix/compact_u_model.js'],cwd=ROOT,
                       stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    # Output starts only after this small complete input is read.
    p.stdin.write(json.dumps(cases));p.stdin.close()
    counts=collections.defaultdict(collections.Counter)
    first={}
    for line in p.stdout:
        evidence=json.loads(line);layout=generate(evidence['seed'])
        attempt=Attempt(layout,1,.015);attempt.start(1,0)
        for row in evidence['trace']:
            attempt.sample(row['time'],row['position'],row['velocity'],completed=row['completed'])
        verdict=attempt.result
        reason=(verdict.reason or verdict.status) if verdict else 'no-result'
        if evidence['error']:reason='runtime-error:'+str(evidence['error'])
        key=f"scale={evidence['scale']},yaw={evidence['yawError']}"
        counts[key][reason]+=1
        if reason!='achieved':first.setdefault(key,{'seed':layout.seed,'reason':reason,'variables':evidence['variables']})
    if p.wait():raise RuntimeError('model failed')
    if sum(sum(v.values()) for v in counts.values())!=len(cases):raise RuntimeError('incomplete model output')
    return {'claim':'ideal-kinematic falsification only; no native or timing qualification',
            'distinct_layouts':len(layouts),'results':dict(counts),'first_counterexamples':first}


if __name__=='__main__':print(json.dumps(probe(),indent=2,ensure_ascii=False))
