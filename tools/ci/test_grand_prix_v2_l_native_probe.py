"""Pure negative/preparation tests, NOT a substitute for Webots R2025a."""
import unittest
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

    def test_index_outside_reference_set_rejected(self):
        for index in (-1, 12, None, '5'):
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe_scene(index)


if __name__ == '__main__':
    unittest.main()
