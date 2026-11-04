"""Pure negative/preparation tests, NOT a substitute for Webots R2025a."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from tools.ci import run_grand_prix_v2_l_native as runner
from tools.grand_prix.route_courses_v2 import reference_course
from tools.ci.run_grand_prix_v2_l_native import (
    DEFAULT_INDICES, probe_scene, check_native,
)


class NativeLProbePreparationTests(unittest.TestCase):
    def test_four_turn_directions_prepared_without_mission(self):
        self.assertEqual(
            [reference_course(i).route.turns for i in DEFAULT_INDICES],
            [('G', 'G'), ('G', 'D'), ('D', 'G'), ('D', 'D')])
        for index in DEFAULT_INDICES:
            with self.subTest(index=index):
                scene = probe_scene(index)
                self.assertEqual(scene.count('controller "grand_prix_v2_l_probe"'), 1)
                self.assertIn('window "<none>"', scene)
                self.assertEqual(scene.count('DEF GP_V2_L_'), 4)
                self.assertEqual(scene.count('boundingObject Box { size '), 4)
                self.assertNotIn('GP_ROUTE_EVALUATOR', scene)

    def test_synthetic_result_never_qualifies_native(self):
        course = reference_course(5)
        with self.assertRaisesRegex(RuntimeError, 'identity'):
            check_native({'claim': 'static-only', 'configuration': course.identifier},
                         course)
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            check_native(dict(claim='L-only-native-teleport-perception-not-flight',
                              configuration=course.identifier, webots='R2025a',
                              timestep_ms=8, samples=[]), course)

    def test_failure_after_previous_summary_does_not_publish_stale_success(self):
        # Pure simulated subprocess failure: never a native sensor PASS.
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'webots').touch()
            out = root / 'evidence'
            out.mkdir()
            summary = out / 'summary.json'
            summary.write_text('{"claim": "old success"}\n')
            with patch.object(runner, 'OUT', out), patch.object(
                    runner.subprocess, 'Popen') as spawned:
                spawned.return_value.wait.return_value = 1
                spawned.return_value.poll.return_value = 1
                with self.assertRaisesRegex(RuntimeError, 'native Webots failure'):
                    runner.native_run(home, (0,))
            # Historical global evidence is untouched, but a failed invocation
            # has no summary at its own announced per-run location.
            self.assertEqual(summary.read_text(), '{"claim": "old success"}\n')
            self.assertEqual(len(list(out.glob('invocation-*'))), 1)
            self.assertFalse(list(out.glob('invocation-*/summary.json')))
            self.assertFalse(list(out.glob('invocation-*/.summary-*.tmp')))

    def test_interleaved_invocations_never_borrow_other_native_bytes(self):
        # Interleave mock B, which produces valid-shaped fake data, while mock
        # A exits zero without writing sensor evidence. A must fail closed.
        # These synthetic records are NOT native R2025a qualification.
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'webots').touch()
            out = root / 'evidence'
            course = reference_course(0)
            nearby = {'front': .20, 'back': 2., 'left': 2., 'right': 2.}
            distant = {'front': .60, 'back': 2., 'left': 2., 'right': 2.}
            mock_result = dict(
                claim='L-only-native-teleport-perception-not-flight',
                configuration=course.identifier, webots='R2025a',
                timestep_ms=8,
                samples=[dict(box=f'GP_V2_L_{i}_{part}', near=nearby, far=distant)
                         for i in range(2) for part in range(2)])

            def b_process(*args, **kwargs):
                target = Path(kwargs['env']['GP_V2_L_NATIVE_OUT'])
                target.write_text(json.dumps(mock_result))
                kwargs['stdout'].write(
                    'GP_V2_L_NATIVE ' + json.dumps(mock_result, sort_keys=True) + '\n')
                process = Mock()
                process.wait.return_value = 0
                process.poll.return_value = 0
                return process

            def a_process(*args, **kwargs):
                process = Mock()

                def wait(*, timeout):
                    with patch.object(runner.subprocess, 'Popen',
                                      side_effect=b_process):
                        runner.native_run(home, (0,))
                    return 0

                process.wait.side_effect = wait
                process.poll.return_value = 0
                return process

            with patch.object(runner, 'OUT', out), patch.object(
                    runner.subprocess, 'Popen', side_effect=a_process):
                with self.assertRaisesRegex(RuntimeError, 'no native output'):
                    runner.native_run(home, (0,))
            run_dirs = list(out.glob('invocation-*'))
            self.assertEqual(len(run_dirs), 2)
            self.assertEqual(len(list(out.glob('invocation-*/summary.json'))), 1)
            self.assertEqual(len(list(out.glob('invocation-*/*/native.json'))), 1)
            self.assertFalse((out / 'summary.json').exists())

    def test_index_outside_reference_set_rejected(self):
        for index in (-1, 12, None, '5'):
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe_scene(index)


if __name__ == '__main__':
    unittest.main()
