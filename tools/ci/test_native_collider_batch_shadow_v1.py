"""Host-only falsification of the experimental grouped-export decoder.

Not a native Webots test. The CI 30s run supplies the independent native witness.
"""
import unittest
from types import SimpleNamespace

from tools.grand_prix.native_collider_batch_shadow_v1 import (
    CanonicalColliderShadow, compare_grouped_to_canonical, grouped_boxes,
)


NAME = 'GP_V2_L_0_0'
ONE = SimpleNamespace(name=NAME, position=(0.25, -0.5, 0.65), size=(0.6, 0.04, 1.3))


def fixture(*, name=NAME, physical='0.6 0.04 1.3', visual='0.6 0.04 1.3',
            locked='TRUE', translation='0.25 -0.5 0.65', rotation=''):
    return ('Group {\n  children [\n'
            f'    DEF {name} Solid {{\n'
            f'      translation {translation}\n'
            f'      {rotation}\n' if rotation else
            'Group {\n  children [\n'
            f'    DEF {name} Solid {{\n'
            f'      translation {translation}\n') + (
            '      children [\n'
            '        Shape {\n'
            '          geometry Box {\n'
            f'            size {visual}\n'
            '          }\n'
            '        }\n'
            '      ]\n'
            '      boundingObject Box {\n'
            f'        size {physical}\n'
            '      }\n'
            f'      locked {locked}\n'
            '    }\n'
            '  ]\n}')


class Probe:
    def __init__(self):
        self.items, self.events = [], []

    def record(self, name, elapsed):
        self.items.append((name, elapsed))

    def sink(self, payload):
        self.events.append(payload)


class BatchShadowTests(unittest.TestCase):
    def test_nominal_accepted(self):
        self.assertEqual(1, compare_grouped_to_canonical(fixture(), [ONE]))

    def test_missing_and_duplicate_rejected(self):
        for raw in (fixture().replace('GP_V2_L_0_0', 'GP_V2_L_0_1'),
                    fixture().replace('  ]\n}', '    DEF GP_V2_L_0_0 Solid {\n    }\n  ]\n}')):
            with self.subTest(raw=raw[-50:]), self.assertRaises(ValueError):
                compare_grouped_to_canonical(raw, [ONE])

    def test_physical_and_visual_mutation_rejected(self):
        for raw in (fixture(physical='0.7 0.04 1.3'),
                    fixture(visual='0.7 0.04 1.3'),
                    fixture(locked='FALSE'),
                    fixture(translation='0.26 -0.5 0.65'),
                    fixture(rotation='rotation 0 0 1 0.2'),
                    fixture(physical='nan 0.04 1.3')):
            with self.subTest(raw=raw[-75:]), self.assertRaises(ValueError):
                compare_grouped_to_canonical(raw, [ONE])

    def test_unlisted_root_escapes_batch_and_requires_historical_authority(self):
        # Deliberate negative counterexample: a foreign physical body is
        # invisible to this *selected* batched export decoder. The historical
        # recursive Supervisor graph check must remain authoritative.
        extra = ('    DEF FOREIGN_PHYSICAL Solid {\\n'
                 '      locked TRUE\\n'
                 '      boundingObject Box { size 0.1 0.1 0.1 }\\n'
                 '    }\\n').replace('\\n', '\n')
        scene = fixture().replace('  ]\n}', extra + '  ]\n}')
        self.assertIn('DEF FOREIGN_PHYSICAL', scene)
        self.assertEqual([NAME], list(grouped_boxes(scene)))
        self.assertEqual(1, compare_grouped_to_canonical(scene, [ONE]))

    def test_reset_same_geometry_is_indistinguishable(self):
        # Explicit counterexample: identical serialized bytes after RESET
        # have no incarnation/revision. #923/#913 still required.
        before, after = fixture(), fixture()
        self.assertEqual(before, after)
        self.assertEqual(1, compare_grouped_to_canonical(after, [ONE]))

    def test_comparison_is_telemetry_only(self):
        probe = Probe()
        shadow = CanonicalColliderShadow([ONE], probe, window=2)
        shadow.observe(fixture())
        shadow.historical(True)
        shadow.observe(fixture(locked='FALSE'))
        shadow.historical(False, ValueError('native physical refusal'))
        self.assertEqual(1, len(probe.events))
        self.assertIn('"parity":2', probe.events[0])
        self.assertEqual(2, len(probe.items))


if __name__ == '__main__':
    unittest.main()
