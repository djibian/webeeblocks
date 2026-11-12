"""Non-native, fail-closed checks of the experimental paired evidence logic."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.ci.experiments import gp_pose_3d_native_live_ab as live


def witness_rows():
    rows = []
    for begin, end in live.ipc.PHASES.values():
        for tick in range(begin, end + 1, 8):
            rows.append(dict(time_ms=tick, attempt=1, phase='active',
                error=None, contact_count=0, position=[float(tick),0.,.4],
                orientation=[1.] * 9, velocity=[0.] * 3,
                ranges_m=[1.] * 5))
    return rows


def trial(rows, world='wbt-digest'):
    return (dict(sections={phase:dict(count=375)
        for phase in live.ipc.PHASES}), rows, world)


class LiveExperimentLogic(unittest.TestCase):
    def test_exact_native_observations_pass(self):
        baseline = trial(witness_rows())
        active = trial(witness_rows())
        result = live._compare({'publish_only':baseline, 'viewer_fast':active})
        self.assertTrue(result['viewer_fast']['equivalent'])

    def test_changed_physical_observation_fails(self):
        old = witness_rows()
        new = witness_rows()
        new[20]['position'][0] = -100.0
        with self.assertRaisesRegex(RuntimeError, 'dynamic trace refutation'):
            live._compare({'publish_only':trial(old), 'viewer_fast':trial(new)})

    def test_missing_native_tick_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'not aligned'):
            live._compare({'publish_only':trial(witness_rows()),
                'viewer_fast':trial(witness_rows()[1:])})

    def test_world_mismatch_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'worlds differ'):
            live._compare({'publish_only':trial(witness_rows()),
                'viewer_fast':trial(witness_rows(), 'other-world')})

    def test_bounded_browser_ready_marker(self):
        with TemporaryDirectory() as directory:
            p=Path(directory)/'ready.json'
            p.write_text(json.dumps({'status':'REAL_WEBGL_READY'}))
            class Running:
                def poll(self):return None
            self.assertEqual(live._wait_ready(Running(),p,seconds=.1)['status'],
                             'REAL_WEBGL_READY')
            p.unlink()
            class Failed:
                def poll(self):return 1
            with self.assertRaisesRegex(RuntimeError, 'exited'):
                live._wait_ready(Failed(),p,seconds=.1)


if __name__ == '__main__':
    unittest.main()
