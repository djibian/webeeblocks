from controller import Supervisor
r=Supervisor()
target=r.getFromDef("TARGET")
if target is None: raise SystemExit("H6_D3_REFUSED_TARGET")
step=int(r.getBasicTimeStep())
print("H6_D3_TRUE_CONTROLLER_BEGIN",flush=True)
for i in range(36):
    if r.step(step)==-1: raise SystemExit("H6_D3_REFUSED_EARLY")
print("H6_D3_TRUE_BEFORE_SAVE t=%.6f"%r.getTime(),flush=True)
target.saveState("checkpoint")
for i in range(2):
    if r.step(step)==-1: raise SystemExit("H6_D3_REFUSED_EARLY_SAVED")
print("H6_D3_TRUE_REQUEST_LOAD t=%.6f"%r.getTime(),flush=True)
target.loadState("checkpoint")
for i in range(5):
    if r.step(step)==-1: raise SystemExit("H6_D3_REFUSED_EARLY_LOADED")
print("H6_D3_TRUE_CONTROLLER_COMPLETE t=%.6f"%r.getTime(),flush=True)
r.simulationQuit(0)
