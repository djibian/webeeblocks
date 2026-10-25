#!/usr/bin/env python3
"""Exactly one native physics step, no actuator or product controller."""
import hashlib
import json
import os
from pathlib import Path
import sys
from controller import Supervisor

protocol_path, case_id, result_path = sys.argv[1:]
raw = Path(protocol_path).read_bytes()
p = json.loads(raw)
case = next(c for c in p['cases'] if c['id'] == case_id)
robot = Supervisor()
body = robot.getFromDef('BODY')
assert robot.getBasicTimeStep() == p['step_ms']
assert robot.getTime() == 0
body.setVelocity(p['velocity_6d'])

def snapshot():
    return dict(time_s=robot.getTime(), position_m=body.getPosition(),
                orientation=body.getOrientation(), velocity_6d=body.getVelocity(),
                contacts=[dict(point=list(c.point), node_id=c.node_id)
                          for c in body.getContactPoints(False)])

before = snapshot()
assert robot.step(p['step_ms']) != -1
after = snapshot()
result = dict(case=case, protocol_sha256=hashlib.sha256(raw).hexdigest(),
              before=before, after=after, steps_executed=1,
              claim='reduced fixture only; no historical replay or product qualification')
with Path(result_path).open('x') as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
    stream.write('\n')
    stream.flush()
    os.fsync(stream.fileno())
print('NATIVE_CONTACT_ONE_STEP ' + json.dumps(result, allow_nan=False), flush=True)
robot.simulationQuit(0)
