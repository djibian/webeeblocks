"""Two short known-mechanism controls. All effects belong to this fixture,
never to the observation-only physics plugin or to WebeeBlocks production.
"""
from controller import Supervisor

s = Supervisor()
body = s.getFromDef("WRENCH_BODY")
if body is None:
    raise RuntimeError("missing fixture body")
translation = body.getField("translation")
rotation = body.getField("rotation")
for tick in range(55):
    if tick == 3:
        # Free rigid body: known nonzero applied torque, no floor contact.
        body.addTorque([0, 0.01, 0], False)
        print("WRENCH_CONTROL free_torque tick=3", flush=True)
    if tick == 17:
        # Real Supervisor teleport/resetPhysics, with an off-center floor
        # penetration after tilt: intentionally creates a contact mechanism.
        translation.setSFVec3f([0.0, 0.0, 0.045])
        rotation.setSFRotation([0.0, 1.0, 0.0, 0.35])
        body.resetPhysics()
        print("WRENCH_CONTROL reset_into_contact tick=17", flush=True)
    if tick == 31:
        translation.setSFVec3f([0.0, 0.0, 0.75])
        rotation.setSFRotation([0.0, 1.0, 0.0, 0.0])
        body.resetPhysics()
        print("WRENCH_CONTROL reset_out_of_contact tick=31", flush=True)
    if s.step(32) == -1:
        break
s.simulationQuit(0)
