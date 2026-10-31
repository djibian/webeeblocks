from controller import Supervisor
r=Supervisor();dt=int(r.getBasicTimeStep())
print("H6_EXT_CONTROLLER_STARTED",flush=True)
for i in range(15):
    if r.step(dt)==-1: raise SystemExit("H6_EXT_REFUSED_EARLY")
print("H6_EXT_CONTROLLER_COMPLETE",flush=True)
r.simulationQuit(0)
