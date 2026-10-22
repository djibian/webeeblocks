"""Simulation-only interventions, kept separate from #649's passive observer."""
import json
import os
from pathlib import Path


def record(supervisor, directory):
    vehicle = supervisor.getFromDef('CI_AUTONOMOUS_CRAZYFLIE')
    if vehicle is None:
        raise RuntimeError('diagnostic vehicle unavailable')
    last = None
    due = None
    with (directory / 'native-reset-state.jsonl').open('w', buffering=1) as stream:
        stream.write(json.dumps({'type': 'header', 'scope': 'synthetic-state-intervention-not-historical-replay',
                                 'step_ms': 32}) + '\n')
        while supervisor.step(32) != -1:
            config = directory / 'inject.json'
            if config.exists():
                case = json.loads(config.read_text())
                if case['id'] != last:
                    last = case['id']
                    vehicle.getField('translation').setSFVec3f(case['position'])
                    vehicle.getField('rotation').setSFRotation(case['rotation'])
                    vehicle.resetPhysics()
                    vehicle.setVelocity(case['velocity'])
                    due = supervisor.getTime() + case['steps'] * .032
                    stream.write(json.dumps({'type': 'injection', 'time': supervisor.getTime(), 'case': case}) + '\n')
            sample = {'type': 'sample', 'time': supervisor.getTime(), 'case': last,
                      'position': vehicle.getPosition(), 'orientation': vehicle.getOrientation(),
                      'velocity': vehicle.getVelocity(),
                      'contacts': [{'point': c.point, 'node_id': c.node_id}
                                   for c in vehicle.getContactPoints(True)]}
            stream.write(json.dumps(sample, allow_nan=False) + '\n')
            if due is not None and supervisor.getTime() >= due:
                (directory / 'ready.tmp').write_text(json.dumps({
                    'id': last, 'time': sample['time'], 'position': sample['position'],
                    'velocity': sample['velocity']}))
                (directory / 'ready.tmp').replace(directory / 'ready.json')
                due = None


if __name__ == '__main__':
    from controller import Supervisor
    record(Supervisor(), Path(os.environ['WEBEEBLOCKS_CI_ARTIFACT_DIR']))
