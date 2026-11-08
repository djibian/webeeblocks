"""Tests of the conservative R2025a scene export projection."""
from types import SimpleNamespace
import unittest

from tools.grand_prix.native_scene_snapshot_v2 import read_scene_signature


SCENE = '''Group {
  children [
    DEF GP_V2_L_0_0 Solid {
      translation 2 0 0.65
      children [
        Shape {
          geometry Box {
            size 0.6 0.04 1.3
          }
        }
      ]
    }
    Crazyflie {
      hidden linearVelocity_0 0 0 0
      translation 0 0 0.015
      name "Crazyflie WebeeBlocks"
      extensionSlot [
        Pose {
          translation 0 0 0.0066
        }
      ]
    }
    DEF GP_ROUTE_EVALUATOR Robot {
      model "GP_ROUTE_SAMPLE_V1 time_ms=0"
      description "GP_ROUTE_READY_V1 time_ms=8"
      supervisor TRUE
    }
  ]
}'''


def signature(scene):
    return read_scene_signature(SimpleNamespace(exportString=lambda: scene))


class NativeSceneSnapshotTests(unittest.TestCase):
    def test_only_the_root_robots_dynamic_scalars_are_projected(self):
        before = signature(SCENE)
        self.assertIsNotNone(before)
        moving = SCENE.replace('0 0 0.015', '-1.4e-11 0 0.32').replace(
            'linearVelocity_0 0 0 0', 'linearVelocity_0 0 0 0.12').replace(
            '      name "Crazyflie WebeeBlocks"', '      rotation 0 0 1 0.01\n'
            '      customData "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1"\n'
            '      name "Crazyflie WebeeBlocks"').replace('time_ms=0', 'time_ms=32').replace(
            '      description "GP_ROUTE_READY_V1 time_ms=8"\n', '')
        self.assertEqual(signature(moving), before)

        for original, changed in (
            ('translation 2 0 0.65', 'translation 2.000000001 0 0.65'),
            ('geometry Box {', 'geometry Sphere {'),
            ('size 0.6 0.04 1.3', 'size 0.6 0.040000004 1.3'),
            ('translation 0 0 0.0066', 'translation 0 0 0.008'),
            ('supervisor TRUE', 'supervisor FALSE'),
            ('      supervisor TRUE', '      boundingObject Box { size 1 1 1 }\n'
             '      supervisor TRUE'),
        ):
            with self.subTest(changed=changed):
                self.assertNotEqual(signature(SCENE.replace(original, changed)), before)

    def test_ambiguous_or_unsupported_exports_require_the_full_graph(self):
        for scene in (
            SCENE.replace('Crazyflie {', 'DEF DRONE Crazyflie {'),
            SCENE.replace('geometry Box {', 'geometry USE COLLIDER\n          Group {'),
            SCENE.replace('name "Crazyflie WebeeBlocks"',
                          'name "first line\n    }\n    Crazyflie {\nlast line"'),
            SCENE.replace('description "GP_ROUTE_READY_V1 time_ms=8"',
                          'description "escaped \\" quote"'),
            SCENE + '\n',
        ):
            with self.subTest(scene=scene):
                self.assertIsNone(signature(scene))
