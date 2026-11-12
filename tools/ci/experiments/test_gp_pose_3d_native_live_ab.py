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
            p.write_text(json.dumps({'status':'REAL_WEBGL_READY', 'box_count':21, 'renderer':'SwiftShader'}))
            class Running:
                def poll(self):return None
            self.assertEqual(live._wait_ready(Running(),p,seconds=.1)['status'],
                             'REAL_WEBGL_READY')
            p.unlink()
            class Failed:
                def poll(self):return 1
            with self.assertRaisesRegex(RuntimeError, 'exited'):
                live._wait_ready(Failed(),p,seconds=.1)

    def test_false_stopped_arm_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'did not actually close'):
            live._require_reader_proof('viewer_stopped', False, 0)
        # A closed reader must still supply an observed first-active timestamp.
        live._require_reader_proof('viewer_stopped', True, 0, 5000)
        live._require_reader_proof('viewer_fast', False, 0)

    def test_stop_requires_first_active_native_timestamp(self):
        # A close after the second flight cannot establish post-close continuity.
        for invalid in (None, True, 0, 4000, 4009, 7008, 14008, 17000):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(RuntimeError, 'first-active-flight close'):
                    live._require_reader_proof('viewer_stopped', True, 0, invalid)
        for valid in (4008, 5000, 7000):
            live._require_reader_proof('viewer_stopped', True, 0, valid)
        with self.assertRaisesRegex(RuntimeError, 'did not actually close'):
            live._require_reader_proof('viewer_stopped', False, 0, 5000)

    def test_slow_arm_must_intercept_five_real_requests(self):
        for count in (0, 1, 4):
            with self.assertRaisesRegex(RuntimeError, 'five delayed real pose GETs'):
                live._require_reader_proof('viewer_slow', False, count)
        live._require_reader_proof('viewer_slow', False, 5)

    def test_untrusted_webgl_ready_markers_fail_closed(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / 'browser-ready.json'
            class Running:
                def poll(self): return None
            for proof in ({}, {'status':'REAL_WEBGL_READY'},
                          {'status':'UNPROVEN','box_count':21,'renderer':'SwiftShader'},
                          {'status':'REAL_WEBGL_READY','box_count':0,'renderer':'SwiftShader'},
                          {'status':'REAL_WEBGL_READY','box_count':21,'renderer':''}):
                marker.write_text(json.dumps(proof))
                with self.assertRaisesRegex(RuntimeError, 'invalid real WebGL readiness'):
                    live._wait_ready(Running(), marker, seconds=.1)


if __name__ == '__main__':
    unittest.main()
