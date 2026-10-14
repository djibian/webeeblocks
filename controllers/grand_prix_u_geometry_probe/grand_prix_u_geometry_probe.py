"""Native R2025a static perception falsifier; teleports are NOT flight proof."""
import json
import math
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from controller import Supervisor
from tools.grand_prix.layout_u import generate

robot = Supervisor()
layout = generate(int(sys.argv[1]), float(sys.argv[2]))
step = int(robot.getBasicTimeStep())
self_node = robot.getSelf()
translation = self_node.getField('translation')
rotation = self_node.getField('rotation')
sensors = {name: robot.getDevice('range_' + name) for name in ('front', 'left', 'right')}
for sensor in sensors.values():
    sensor.enable(step)


def observe(x, y, z, yaw):
    for _ in range(3):
        translation.setSFVec3f([x, y, z])
        rotation.setSFRotation([0, 0, 1, yaw])
        self_node.resetPhysics()
        if robot.step(step) == -1:
            raise RuntimeError('simulation terminated before observation')
    return {name: sensor.getValue()/1000 for name, sensor in sensors.items()}


try:
    observations = []
    for gate in layout.gates:
        x = gate.x - .20 * math.cos(gate.heading)
        y = gate.y - .20 * math.sin(gate.heading)
        high = observe(x, y, .8, gate.heading)
        low = observe(x, y, .4, gate.heading)
        # Gate vs wall at high z; at low z an active oblique ray must reach
        # a finite farther wall. Saturation alone cannot certify an opening.
        active = observe(x, y, .4, gate.heading-math.radians(20))
        assert .15 < high['front'] < .23, high
        assert .50 < high['left']+high['right'] < .62, high
        assert high['front']+.3 < active['front'] < 1.99, (high, active)
        observations.append(dict(side=gate.side, high=high, low=low, active=active))
    terminal = []
    for count in (1, 2, 3):
        x, y = layout.landing_target(count)
        value = observe(x, y, .4, math.pi)
        assert .65 < value['front'] < .72, value
        terminal.append(value)
    # Rendered collider data must match the independent versioned layout.
    for i, box in enumerate(layout.boxes):
        node = robot.getFromDef(f'GP_U_BOX_{i}')
        assert node is not None, i
        assert math.dist(node.getPosition(), (box.x, box.y, box.z)) < 1e-9
        dims = node.getField('boundingObject').getSFNode().getField('size').getSFVec3f()
        assert math.dist(dims, (box.sx, box.sy, box.sz)) < 1e-9
    result=dict(configuration=layout.identifier,
          claim='static-native-perception-only', gates=observations,
          terminal=terminal, timestep_ms=step)
    # simulationQuit can terminate Webots before it drains the child's stdout.
    # Keep exact native data durably before requesting that shutdown.
    output=os.environ.get('GP_U_GEOMETRY_OUT')
    if output:Path(output).write_text(json.dumps(result,allow_nan=False)+'\n')
    print('GP_U_GEOMETRY '+json.dumps(result), flush=True)
    robot.step(step)
    robot.simulationQuit(0)
except Exception:
    import traceback
    traceback.print_exc()
    robot.simulationQuit(1)
