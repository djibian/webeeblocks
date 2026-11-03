"""Two short known-mechanism controls; never part of the observation plugin."""
import os
from controller import Supervisor

mode = os.environ.get("WRENCH_FIXTURE_MODE", "free")
if mode not in ("free", "reset_contact"):
    raise RuntimeError("invalid lab fixture mode")
s = Supervisor()
body = s.getFromDef("WRENCH_BODY")
if body is None:
    raise RuntimeError("missing fixture body")
translation = body.getField("translation")
rotation = body.getField("rotation")
for tick in range(14 if mode == "free" else 55):
    if mode == "free" and tick == 3:
        body.addTorque([0, 0.01, 0], False)
        print("WRENCH_CONTROL free_torque tick=3", flush=True)
    if mode == "reset_contact" and tick == 17:
        # Real Supervisor teleport/resetPhysics into off-center contact.
        translation.setSFVec3f([0.0, 0.0, 0.045])
        rotation.setSFRotation([0.0, 1.0, 0.0, 0.35])
        body.resetPhysics()
        print("WRENCH_CONTROL reset_into_contact tick=17", flush=True)
    if mode == "reset_contact" and tick == 31:
        translation.setSFVec3f([0.0, 0.0, 0.75])
        rotation.setSFRotation([0.0, 1.0, 0.0, 0.0])
        body.resetPhysics()
        print("WRENCH_CONTROL reset_out_of_contact tick=31", flush=True)
    if s.step(32) == -1:
        break
    print("WRENCH_WITNESS tick=%d time_ms=%.0f translation=%s rotation=%s velocity=%s" %
          (tick, s.getTime() * 1000, translation.getSFVec3f(),
           rotation.getSFRotation(), body.getVelocity()), flush=True)
s.simulationQuit(0)
