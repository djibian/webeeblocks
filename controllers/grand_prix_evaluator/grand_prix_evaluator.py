"""Simulation-only supervisor. Never sends a navigation/turn/gate value to AST."""
import dataclasses
import json
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from controller import Supervisor
from tools.grand_prix.layout import generate
from tools.grand_prix.oracle import Attempt, ORACLE
from tools.grand_prix.simulation_time import elapsed_seconds
from tools.grand_prix.lap_progress import candidate_score

robot=Supervisor();step=int(robot.getBasicTimeStep());layout=generate(int(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else 'gp-v2')
root=robot.getRoot().getField('children')
vehicle=next(root.getMFNode(i) for i in range(root.getCount()) if root.getMFNode(i).getField('name') and root.getMFNode(i).getField('name').getSFString()=='Crazyflie WebeeBlocks')
channel=vehicle.getField('customData');control=robot.getSelf().getField('customData')
origin=vehicle.getPosition()[2]
active=None;clock_boundaries=set()
robot.setLabel(0,f'{layout.identifier} — prêt',.02,.03,.065,0xFFFFFF,0,'Arial')
while robot.step(step)!=-1:
    data=channel.getSFString()
    reset=re.fullmatch(r'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 (\d+)',data)
    if reset and (active is None or active.attempt!=int(reset[1])):
        active=Attempt(layout,int(reset[1]),origin);clock_boundaries.clear()
        robot.setLabel(0,f'{layout.identifier} — prêt',.02,.03,.065,0xFFFFFF,0,'Arial')
    if active is None:continue
    marker=re.fullmatch(r'GP_START attempt=(\d+) time=([0-9.]+) debug=([01]) state=(pending|accepted|failed)',control.getSFString())
    if marker and int(marker[1])==active.attempt:
        if marker[4]=='failed':active.fail()
        elif marker[4] in ('pending','accepted'):active.start(active.attempt,float(marker[2]),marker[3]=='1')
    if active.start_time is not None and active.result is None:
        try:duration=elapsed_seconds(active.start_time,robot.getTime())
        except ValueError:active.fail('invalid-clock');duration=None
        if duration in (119.968,120.0,120.032) and duration not in clock_boundaries:
            clock_boundaries.add(duration)
            penalty=-candidate_score(0,duration)
            expected=1 if duration>120 else 0
            if penalty!=expected:raise RuntimeError('wrong native boundary penalty')
            print('WEBEEBLOCKS_GP_CLOCK_BOUNDARY '+json.dumps(dict(attempt=active.attempt,seconds=duration,penalty=penalty)),flush=True)
    complete=data==f'WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt={active.attempt} oracle={ORACLE}'
    result=active.sample(robot.getTime(),vehicle.getPosition(),vehicle.getVelocity()[:3],
                         [c.point for c in vehicle.getContactPoints(True)],completed=complete)
    if result is not None and result.status=='achieved' and (not marker or marker[4]!='accepted'):
        result=dataclasses.replace(result,status='not-achieved',seconds=None,candidate_points=None)
        active.result=result
    if result is not None:
        expected=f'WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt={active.attempt} oracle={ORACLE} status={result.status}'
        if data!=expected:
            channel.setSFString(expected)
            print('WEBEEBLOCKS_GP_RESULT '+json.dumps(dataclasses.asdict(result),sort_keys=True),flush=True)
            if result.status=='not-achieved':
                print('WEBEEBLOCKS_GP_REJECTION '+json.dumps(dict(time=robot.getTime(),position=vehicle.getPosition(),velocity=vehicle.getVelocity()[:3],cursor=active.cursor,reason=active.failure_reason),sort_keys=True),flush=True)
        label=(f'{layout.identifier} / essai {result.attempt} — {result.seconds:.3f} s — {result.laps} tours — {result.crossings} passages — {result.candidate_points} points (expérimental)' if result.seconds is not None else
               f'{layout.identifier} — '+('réussi, mode observation' if result.status=='achieved' else 'essai invalide'))
    elif active.start_time is not None:
        label=f'{layout.identifier} / essai {active.attempt} — {robot.getTime()-active.start_time:.3f} s — {active.progress.laps} tours — {active.progress.crossings} passages validés (provisoire)'
    else:label=f'{layout.identifier} — prêt'
    robot.setLabel(0,label,.02,.03,.065,0xFFFFFF,0,'Arial')
