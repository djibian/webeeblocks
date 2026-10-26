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
        # First preserve discrimination of the actual open-H upper beam and
        # flanking posts, plus a clear low passage. This is native range data.
        assert .15 < high['front'] < .23, high
        assert .50 < high['left']+high['right'] < .62, high
        assert math.isfinite(low['front']) and low['front'] > high['front']+.3, (high, low)
        assert math.isfinite(active['front']) and active['front'] > high['front']+.3, (high, active)
        # The old <1.99 upper bound required an echo from the REMOVED
        # continuous lateral walls. Without those walls, the outward 20-degree
        # low ray must saturate on sides 0/1; on side 2 the retained closed H
        # must still produce a finite downstream echo. Requiring the opposite
        # physical signatures is stronger than simply allowing any range.
        if gate.side in (0, 1):
            assert 1.99 <= active['front'] <= 2.001, (gate.side, high, active)
        else:
            assert active['front'] < 1.99, (gate.side, high, active)
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
