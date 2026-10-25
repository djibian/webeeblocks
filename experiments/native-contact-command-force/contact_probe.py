#!/usr/bin/env python3
"""One physics step with fixed forces, never PID or invented motor feedback."""
import hashlib
import json
import os
from pathlib import Path
import sys
import ctypes
from controller import Supervisor
from controller.wb import wb

protocol_path, case_id, result_path = sys.argv[1:]
raw = Path(protocol_path).read_bytes()
p = json.loads(raw)
case = next(c for c in p['cases'] if c['id']==case_id)
robot = Supervisor()
body = robot.getFromDef('BODY')
assert robot.getBasicTimeStep()==p['step_ms'] and robot.getTime()==0
body.setVelocity(p['velocity_6d'])

def snapshot():
    return dict(time_s=robot.getTime(),position_m=body.getPosition(),
                orientation=body.getOrientation(),velocity_6d=body.getVelocity(),
                contacts=[dict(point=list(c.point),node_id=c.node_id)
                          for c in body.getContactPoints(False)])

before=snapshot()
# Supervisor relative=True means the body's local coordinate frame. The force
# acts at the centre of mass; summed lever-arm/reaction torque is separate.
body.addForce(p['force_body_N'],True)
# The official R2025a Node.addTorque wrapper incorrectly calls add_force.
# Call the documented C torque API directly; do not modify the installation.
wb.wb_supervisor_node_add_torque.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double), ctypes.c_bool]
wb.wb_supervisor_node_add_torque.restype = None
wb.wb_supervisor_node_add_torque(body._ref,(ctypes.c_double*3)(*p['torque_body_N_m']),True)
assert robot.step(p['step_ms'])!=-1
after=snapshot()
result=dict(case=case,protocol_sha256=hashlib.sha256(raw).hexdigest(),
            before=before,after=after,steps_executed=1,
            force_body_N=p['force_body_N'],torque_body_N_m=p['torque_body_N_m'],
            claim='fixed-force tracking hypothesis; no direct actuator measurement or product qualification')
with Path(result_path).open('x') as stream:
    json.dump(result,stream,indent=2,allow_nan=False)
    stream.write('\n');stream.flush();os.fsync(stream.fileno())
print('NATIVE_CONTACT_ONE_STEP '+json.dumps(result,allow_nan=False),flush=True)
robot.simulationQuit(0)
