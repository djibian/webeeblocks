"""Synthetic offline measurement tests: no Webots, Blockly or user acceptance."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.grand_prix.analyze_step_wall_ab import compare, main, read_trial
from tools.grand_prix.step_wall_probe import PREFIX

COURSE = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2'


def window(index, step_ns=1_000_000):
    steps = [step_ns] * 125
    ticks = [500_000] * 125
    return {
        'schema': 1, 'course': COURSE, 'window': index, 'reason': 'complete',
        'start_sim_ms': 8 + 1000 * index, 'end_sim_ms': 1000 + 1000 * index,
        'simulated_ms': 1000, 'count': 125,
        'wall_ns': 1_000_000_000, 'speed_x': 1.0,
        'step_ns': steps, 'tick_ns': ticks,
        'step_p50_ns': step_ns, 'step_p95_ns': step_ns,
        'step_p99_ns': step_ns, 'step_max_ns': step_ns,
        'tick_p99_ns': 500_000,
    }


class StepWallABTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def write(self, name, rows):
        path = self.base / name
        path.write_text('other Webots diagnostic\n' + ''.join(
            'INFO: ' + PREFIX + json.dumps(row) + '\n' for row in rows),
            encoding='utf-8')
        return path

    def test_30s_three_triples_keep_raw_tail_per_trial(self):
        arms = []
        for arm, delay in [('reference', 1_000_000), ('candidate', 2_000_000)]:
            for i in range(3):
                arms.append((arm, self.write(f'{arm}{i}.log',
                           [window(j, delay) for j in range(30)])))
        report = compare(arms, COURSE)
        self.assertEqual(report['median_step_p99_ms'],
                         {'reference': 1.0, 'candidate': 2.0})
        self.assertEqual(report['median_step_p99_delta_ms'], 1.0)
        self.assertEqual(report['trials']['candidate'][0]['simulated_s'], 30)
        self.assertEqual(report['trials']['candidate'][0]['optimistic_window_speed_x'], 1)

    def test_corrupted_summary_fails_closed(self):
        row = window(0)
        row['step_p99_ns'] = 5
        path = self.write('tamper.log', [row])
        with self.assertRaisesRegex(ValueError, 'summary'):
            read_trial(path, COURSE, min_seconds=1)

    def test_reset_gap_and_partial_are_not_merged(self):
        for rows in ([window(0), window(2)],
                     [window(0), dict(window(1), start_sim_ms=8, end_sim_ms=1000)],
                     [dict(window(0), reason='partial')]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    read_trial(self.write('bad.log', rows), COURSE, min_seconds=1)

    def test_cross_course_raw_time_and_insufficient_trial_refused(self):
        row = window(0)
        row['course'] = 'different'
        with self.assertRaises(ValueError):
            read_trial(self.write('different.log', [row]), COURSE, 1)
        row = window(0)
        row['step_ns'][0] = -1
        with self.assertRaises(ValueError):
            read_trial(self.write('negative.log', [row]), COURSE, 1)
        good = self.write('good.log', [window(0)])
        with self.assertRaisesRegex(ValueError, 'same log'):
            compare([('reference', good), ('candidate', good)], COURSE, 1)
        another = self.write('another.log', [window(0)])
        with self.assertRaisesRegex(ValueError, 'three independent'):
            compare([('reference', good), ('candidate', another)], COURSE, 1)

    def test_cli_refuses_existing_report_and_writes_no_partial(self):
        arms = []
        for arm in ('reference', 'candidate'):
            for i in range(3):
                arms += ['--trial', f'{arm}:{self.write(f"{arm}{i}.log", [window(0)])}']
        target = self.base / 'report.json'
        args = ['--course-id', COURSE, '--min-seconds', '1', '--output', str(target)] + arms
        self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(target.read_text())['median_step_p99_delta_ms'], 0)
        self.assertEqual(main(args), 2)


if __name__ == '__main__':
    unittest.main()
