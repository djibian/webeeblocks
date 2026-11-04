"""Pure negative/preparation tests, NOT a substitute for Webots R2025a."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
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
            self.assertFalse(summary.exists())
            self.assertFalse(list(out.glob('.summary-*.tmp')))

    def test_index_outside_reference_set_rejected(self):
        for index in (-1, 12, None, '5'):
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe_scene(index)


if __name__ == '__main__':
    unittest.main()
