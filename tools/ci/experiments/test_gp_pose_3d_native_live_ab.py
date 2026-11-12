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

    def test_duplicate_native_observation_fails(self):
        duplicate = witness_rows()
        duplicate.insert(20, dict(duplicate[20]))
        with self.assertRaisesRegex(RuntimeError, 'duplicate/missing tick'):
            live._compare({'publish_only':trial(witness_rows()),
                'viewer_fast':trial(duplicate)})
        # Duplicate in the baseline must fail too, not get hidden in a dict.
        with self.assertRaisesRegex(RuntimeError, 'duplicate/missing tick'):
            live._compare({'publish_only':trial(duplicate),
                'viewer_fast':trial(witness_rows())})

    def test_browser_success_waits_for_evidence_and_close(self):
        events = []
        report = {'status': 'UNPROVEN'}
        live._finish_browser_report(report,
            lambda: events.append('screenshot'),
            lambda: events.append('close'))
        self.assertEqual(events, ['screenshot', 'close'])
        live._require_browser_result(report)

    def test_browser_screenshot_exception_never_sets_success(self):
        def fail_screenshot():
            raise OSError('screenshot unavailable')
        report = {'status': 'UNPROVEN'}
        with self.assertRaisesRegex(OSError, 'screenshot unavailable'):
            live._finish_browser_report(report, fail_screenshot, lambda: None)
        self.assertEqual(report['status'], 'UNPROVEN')
        with self.assertRaisesRegex(RuntimeError, 'real WebGL evidence'):
            live._require_browser_result(report)

    def test_browser_close_exception_never_sets_success(self):
        def fail_close():
            raise RuntimeError('browser process hung')
        report = {'status': 'UNPROVEN'}
        with self.assertRaisesRegex(RuntimeError, 'browser process hung'):
            live._finish_browser_report(report, None, fail_close)
        self.assertEqual(report['status'], 'UNPROVEN')

    def test_browser_report_success_with_error_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'real WebGL evidence'):
            live._require_browser_result({
                'status': 'WEBGL_DRAW_MEASURED_ONLY',
                'error': 'ScreenshotError: path unavailable'})
        with self.assertRaisesRegex(RuntimeError, 'real WebGL evidence'):
            live._require_browser_result({
                'status': 'WEBGL_FAILURE', 'error': 'browser closed early'})

    def test_world_mismatch_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'worlds differ'):
            live._compare({'publish_only':trial(witness_rows()),
                'viewer_fast':trial(witness_rows(), 'other-world')})

    def test_dynamic_native_canvas_height_matches_full_viewport(self):
        def geometry(header_height):
            canvas_height = 620 - header_height
            return (dict(viewport=[960, 620], dpr=1,
                framebuffer=[960, canvas_height], client=[960, canvas_height],
                bounds=[0, header_height, 960, 620],
                header_bottom=header_height, document_scroll=[960, 620]),
                [960, canvas_height])
        # Browser in the prior replay had a 66px header. Real Linux Chrome
        # produced a 60px header and was falsely rejected despite full area.
        for header_height in (66, 60):
            with self.subTest(header_height=header_height):
                geometry_result, resolution = geometry(header_height)
                live._require_native_canvas_layout(geometry_result, resolution)

    def test_native_canvas_refuses_clipping_scroll_and_downscaling(self):
        valid = dict(viewport=[960, 620], dpr=1,
            framebuffer=[960, 560], client=[960, 560],
            bounds=[0, 60, 960, 620], header_bottom=60,
            document_scroll=[960, 620])
        invalid = [
            dict(valid, viewport=[960, 600]),
            dict(valid, framebuffer=[945, 560]),
            dict(valid, bounds=[0, 60, 960, 606]),
            dict(valid, dpr=2),
            dict(valid, document_scroll=[960, 630]),
            dict(valid, header_bottom=200),
            dict(valid, client=[480, 280]),
        ]
        for broken in invalid:
            with self.subTest(broken=broken):
                with self.assertRaisesRegex(RuntimeError, 'full-viewport framebuffer'):
                    live._require_native_canvas_layout(broken, [960, 560])


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

    def test_stop_rejects_stale_display_after_native_publisher_advances(self):
        displayed = dict(poseValid=True, poseTimeMs=5000, poseSeq=150,
                         incarnation='incarnation-a')
        current = dict(valid=True, time_ms=17000, sequence=1800,
                       incarnation='incarnation-a')
        # The old check accepted the 5000-ms displayed pose as a valid stop.
        with self.assertRaisesRegex(RuntimeError, 'fresh first-flight native'):
            live._require_live_stop_pose(displayed, current)

    def test_stop_requires_current_pub_and_same_incarnation(self):
        displayed = dict(poseValid=True, poseTimeMs=5000, poseSeq=150,
                         incarnation='incarnation-a')
        current = dict(valid=True, time_ms=5072, sequence=160,
                       incarnation='incarnation-a')
        self.assertEqual(live._require_live_stop_pose(displayed, current), 5072)
        changed = dict(current, incarnation='incarnation-b')
        with self.assertRaisesRegex(RuntimeError, 'fresh first-flight native'):
            live._require_live_stop_pose(displayed, changed)
        invalid = dict(current, sequence=149)
        with self.assertRaisesRegex(RuntimeError, 'fresh first-flight native'):
            live._require_live_stop_pose(displayed, invalid)
        delayed = dict(current, time_ms=6008)
        with self.assertRaisesRegex(RuntimeError, 'fresh first-flight native'):
            live._require_live_stop_pose(displayed, delayed)
        unaligned = dict(current, time_ms=5073)
        with self.assertRaisesRegex(RuntimeError, 'fresh first-flight native'):
            live._require_live_stop_pose(displayed, unaligned)
        not_valid = dict(current, valid=False)
        with self.assertRaisesRegex(RuntimeError, 'fresh first-flight native'):
            live._require_live_stop_pose(displayed, not_valid)

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
