from controller import Supervisor
r=Supervisor()
b=r.getFromDef("B")
a=r.getFromDef("A")
c=r.getFromDef("C")
if not a or not b or not c: raise SystemExit("H6_D1_CONTROLLER_REFUSED_DEF")
dt=int(r.getBasicTimeStep())
print("H6_D1_CONTROLLER_READY",flush=True)
for _ in range(3):
    if r.step(dt)==-1: raise SystemExit("H6_D1_CONTROLLER_REFUSED_PRE")
print("H6_D1_CONTROLLER_REMOVE_B",flush=True)
b.remove()
for _ in range(5):
    if r.step(dt)==-1: raise SystemExit("H6_D1_CONTROLLER_REFUSED_POST")
if r.getFromDef("A") is None or r.getFromDef("C") is None:
    raise SystemExit("H6_D1_CONTROLLER_REFUSED_SURVIVOR")
print("H6_D1_CONTROLLER_COMPLETE",flush=True)
r.simulationQuit(0)
