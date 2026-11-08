"""Deterministic measurement-only tests; included by the canonical Grand Prix timing suite."""
import json
import unittest

from tools.grand_prix.step_wall_probe import StepWallProbe, PREFIX


class StepWallProbeTests(unittest.TestCase):
    def test_full_window_and_raw_percentiles(self):
        rows = []
        probe = StepWallProbe('course', rows.append, window_steps=4)
        for index in range(4):
            start = index * 20000000
            probe.record((index + 1) * .008, start,
                         start + 1000000 * (index + 1),
                         start + 1000000 * (index + 2))
        self.assertEqual(len(rows), 1)
        result = json.loads(rows[0][len(PREFIX):])
        self.assertEqual(result['step_ns'], [1000000, 2000000, 3000000, 4000000])
        self.assertEqual(result['tick_ns'], [1000000] * 4)
        self.assertEqual(result['step_p95_ns'], 4000000)
        self.assertEqual(result['step_p99_ns'], 4000000)
        self.assertEqual(result['step_p50_ns'], 2000000)
        self.assertEqual(result['simulated_ms'], 32)
        self.assertEqual(result['wall_ns'], 65000000)
        self.assertEqual(result['speed_x'], round(32 / 65, 6))
        self.assertEqual(result['reason'], 'complete')
        self.assertEqual(probe.records, [])

    def test_discontinuity_never_combines_two_simulation_epochs(self):
        rows = []
        probe = StepWallProbe('course', rows.append, window_steps=4)
        probe.record(.008, 0, 1000000, 2000000)
        probe.record(.016, 10000000, 11000000, 12000000)
        probe.record(.008, 20000000, 21000000, 22000000)
        probe.flush()
        reports = [json.loads(row[len(PREFIX):]) for row in rows]
        self.assertEqual([result['reason'] for result in reports],
                         ['clock-discontinuity', 'partial'])
        self.assertEqual([result['count'] for result in reports], [2, 1])
        self.assertEqual([result['start_sim_ms'] for result in reports], [8, 8])

    def test_missing_or_bad_timing_fails_recording_only(self):
        for invalid in [(float('nan'), 1, 2, 3), (.008, 2, 1, 3),
                        (.008, 1, 2, True), (.001, 1, 2, 3)]:
            probe = StepWallProbe('course', lambda line: None)
            with self.assertRaises(ValueError):
                probe.record(*invalid)

    def test_configuration_rejects_invalid_windows(self):
        for invalid in (0, True, -1, 3751):
            with self.assertRaises(ValueError):
                StepWallProbe('course', lambda line: None, window_steps=invalid)
