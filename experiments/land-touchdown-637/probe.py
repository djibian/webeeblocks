"""Reduced native cylinder/plane intervention, not a flight-controller proof."""
import json,sys
from pathlib import Path
from controller import Supervisor
protocol,case,out=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3])
p=json.loads(protocol.read_text()); robot=Supervisor(); body=robot.getSelf()
assert robot.getBasicTimeStep()==8 and robot.getTime()==0
body.setVelocity(p['velocity_6d']); cut=False; rows=[]
for i in range(251):
 contacts=[list(c.point) for c in body.getContactPoints(False)]
 if contacts and case.startswith('cut') and (round(robot.getTime()*1000)-int(case[3:]))%32==0:cut=True
 row={'time':robot.getTime(),'position':body.getPosition(),'velocity':body.getVelocity(),
      'rotation':body.getOrientation(),'contacts':contacts,'cut':cut}
 rows.append(row)
 if i==250:break
 body.addForce([0,0,0 if cut else .05*9.81],True)
 assert robot.step(8)!=-1
(out/'observations.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
print('REDUCED_CONTACT_END '+json.dumps(rows[-1],allow_nan=False),flush=True)
robot.simulationQuit(0)
