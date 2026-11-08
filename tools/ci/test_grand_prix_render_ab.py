"""Synthetic parser tests: no native/GUI or product acceptance claims."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.grand_prix.analyze_render_ab import PREFIX, analyze


class RenderABTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.data = {
            'schema': 'webeeblocks.gp-render-ab-v1',
            'common': {
                'source_sha': 'a' * 40, 'webots_sha256': 'b' * 64,
                'wbb_sha256': 'c' * 64, 'host_token': 'same-local-host',
                'course_id': 'route-test', 'viewport': '1280x720',
                'renderer': 'Mesa', 'browser': 'Chrome', 'phase': 'flight',
                'physical_step_ms': 8, 'gui_visible': True,
            },
            'candidate_fps': 25,
            'trials': [],
        }
        for pair, arms in enumerate((('reference', 'candidate'),
                                     ('candidate', 'reference'),
                                     ('reference', 'candidate')), 1):
            for arm in arms:
                name = f'{pair}-{arm}.log'
                self.data['trials'].append({
                    'pair': pair, 'arm': arm,
                    'render_fps': None if arm == 'reference' else 25,
                    'log': name, 'first_window': 0, 'last_window': 1,
                })
                lines = []
                for index in range(2):
                    v = 8_000_000 if arm == 'reference' else 6_000_000
                    lines.append(PREFIX + json.dumps({
                        'schema': 1, 'course': 'route-test', 'window': index,
                        'reason': 'complete', 'start_sim_ms': index * 16,
                        'end_sim_ms': index * 16 + 8, 'simulated_ms': 16,
                        'count': 2, 'wall_ns': 2 * v, 'step_ns': [v, v],
                        'step_p99_ns': v, 'step_max_ns': v,
                    }))
                (self.root / name).write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.save()

    def save(self):
        self.manifest = self.root / 'runs.json'
        self.manifest.write_text(json.dumps(self.data), encoding='utf-8')

    def test_counterbalanced_pairs_and_raw_quantiles(self):
        report = analyze(self.manifest, minimum_sim_ms=32)
        self.assertEqual(report['product_or_windows_acceptance'], 'NOT_ESTABLISHED')
        self.assertEqual(len(report['paired_differences']), 3)
        self.assertAlmostEqual(report['paired_differences'][0]['speed_ratio_candidate_over_reference'], 4 / 3, places=6)
        self.assertEqual(report['paired_differences'][0]['step_p99_delta_ms'], -2)
        self.assertEqual(report['trials'][0]['simulated_ms'], 32)
        self.assertEqual(report['trials'][0]['step_p99_ms'], 8)

    def test_real_default_requires_30_seconds(self):
        with self.assertRaisesRegex(ValueError, 'shorter than 30000'):
            analyze(self.manifest)

    def test_rejects_duplicate_and_incomplete_evidence(self):
        self.data['trials'][1]['log'] = self.data['trials'][0]['log']
        self.save()
        with self.assertRaisesRegex(ValueError, 'log reused'):
            analyze(self.manifest, minimum_sim_ms=32)
        self.data['trials'][1]['log'] = '1-candidate.log'
        self.data['trials'][0]['first_window'] = 0
        self.data['trials'][0]['last_window'] = 2
        self.save()
        with self.assertRaisesRegex(ValueError, 'missing window'):
            analyze(self.manifest, minimum_sim_ms=32)

    def test_rejects_forged_stats_and_clock_gap(self):
        path = self.root / '1-reference.log'
        content = path.read_text(encoding='utf-8').replace('"step_p99_ns": 8000000',
                                                       '"step_p99_ns": 1', 1)
        path.write_text(content, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            analyze(self.manifest, minimum_sim_ms=32)
        content = content.replace('"step_p99_ns": 1', '"step_p99_ns": 8000000', 1)
        content = content.replace('"start_sim_ms": 16', '"start_sim_ms": 32')
        content = content.replace('"end_sim_ms": 24', '"end_sim_ms": 40')
        path.write_text(content, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'clock gap'):
            analyze(self.manifest, minimum_sim_ms=32)

    def test_rejects_uncounterbalanced_order_and_gui_claim(self):
        self.data['trials'][2:4] = list(reversed(self.data['trials'][2:4]))
        self.save()
        with self.assertRaisesRegex(ValueError, 'counterbalanced'):
            analyze(self.manifest, minimum_sim_ms=32)
        self.data['trials'][2:4] = list(reversed(self.data['trials'][2:4]))
        self.data['common']['gui_visible'] = False
        self.save()
        with self.assertRaisesRegex(ValueError, 'visible GUI'):
            analyze(self.manifest, minimum_sim_ms=32)

    def test_rejects_path_escape(self):
        self.data['trials'][0]['log'] = '../foreign.log'
        self.save()
        with self.assertRaisesRegex(ValueError, 'relative to manifest'):
            analyze(self.manifest, minimum_sim_ms=32)


if __name__ == '__main__':
    unittest.main()
