"""Native observable-world evaluator, independent of Blockly."""
import csv
import dataclasses
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from controller import Supervisor
from tools.grand_prix.layout_u import generate
from tools.grand_prix.oracle_u import Attempt, ORACLE
robot=Supervisor();step=int(robot.getBasicTimeStep())
layout=generate(int(sys.argv[1]),float(sys.argv[2]))
root=robot.getRoot().getField('children')
vehicle=next(root.getMFNode(i) for i in range(root.getCount())
             if root.getMFNode(i).getField('name') and root.getMFNode(i).getField('name').getSFString()=='Crazyflie WebeeBlocks')
channel=vehicle.getField('customData');control=robot.getSelf().getField('customData')
for i,box in enumerate(layout.boxes):
    node=robot.getFromDef(f'GP_U_BOX_{i}')
    if node is None:raise RuntimeError('native collider missing')
    if __import__('math').dist(node.getPosition(),(box.x,box.y,box.z))>1e-9:raise RuntimeError('native collider pose mismatch')
    size=node.getField('boundingObject').getSFNode().getField('size').getSFVec3f()
    if __import__('math').dist(size,(box.sx,box.sy,box.sz))>1e-9:raise RuntimeError('native collider dimensions mismatch')
origin=vehicle.getPosition()[2];active=None;printed=False
trace_path=os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR')
trace_file=(Path(trace_path)/'native_trace.csv').open('w',buffering=1) if trace_path else None
trace=csv.writer(trace_file) if trace_file else None
if trace:trace.writerow(['time','attempt','x','y','z','vx','vy','vz',*[f'r{i}' for i in range(9)]])
robot.setLabel(0,f'{layout.identifier} — prêt',.02,.03,.065,0xFFFFFF,0,'Arial')
while robot.step(step)!=-1:
    now=robot.getTime();data=channel.getSFString()
    reset=re.fullmatch(r'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 (\d+)',data)
    if reset and (active is None or active.attempt!=int(reset[1])):
        active=Attempt(layout,int(reset[1]),origin);printed=False
    if trace:trace.writerow([now,active.attempt if active else 0,*vehicle.getPosition(),*vehicle.getVelocity()[:3],*vehicle.getOrientation()])
    if active is None:continue
    marker=re.fullmatch(r'GP_U_START attempt=(\d+) start_ms=(\d+) state=(admitted|deadline|failed)',control.getSFString())
    if marker and int(marker[1])==active.attempt:
        active.start(active.attempt,int(marker[2])/1000)
        if marker[3]=='deadline':active.fail(now,'time-limit')
        if marker[3]=='failed':active.fail(now,'runtime')
    complete=data==f'WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt={active.attempt} oracle={ORACLE}'
    result=active.sample(now,vehicle.getPosition(),vehicle.getVelocity()[:3],
                         [c.point for c in vehicle.getContactPoints(True)],completed=complete)
    if result is not None:
        expected=f'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt={active.attempt} oracle={ORACLE} status={result.status}'
        if data!=expected:channel.setSFString(expected)
        if not printed:
            record=dataclasses.asdict(result)
            if trace_file:trace_file.flush()
            if trace_path:
                diagnostic=dict(time=now,position=vehicle.getPosition(),velocity=vehicle.getVelocity()[:3],
                    side=active.side,crossings=active.crossings,origin_z=origin,start_ms=active.start_ms,
                    completion_ms=active.completion_ms,stationary_ms=active.stationary_ms,
                    landing_target=layout.landing_target(len(layout.gates)))
                (Path(trace_path)/f'native-diagnostic-{active.attempt}.json').write_text(json.dumps(diagnostic,allow_nan=False)+'\n')
            if trace_path:(Path(trace_path)/f'native-result-{active.attempt}.json').write_text(json.dumps(record,allow_nan=False)+'\n')
            print('GP_U_RESULT '+json.dumps(record,sort_keys=True),flush=True);printed=True
        reason={'time-limit':'temps écoulé','low-outside-zone':'altitude hors zone',
                'wrong-landing':'mauvaise zone de pose','envelope-contact':'collision de gabarit',
                'device-contact':'collision','route-shortcut':'parcours incomplet',
                'missed-gate':'portique non franchi','reverse-crossing':'franchissement inverse',
                'gate-envelope':'franchissement invalide'}.get(result.reason,'essai invalide')
        label=f'{layout.identifier} — '+('réussie' if result.status=='achieved' else 'échouée — '+reason)+f' — {result.seconds:.3f} s'
    elif active.start_ms is not None:
        label=f'{layout.identifier} — {(round(now*1000)-active.start_ms)/1000:.3f} s — {active.crossings} passages'
    else:label=f'{layout.identifier} — prêt'
    robot.setLabel(0,label,.02,.03,.065,0xFFFFFF,0,'Arial')
