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
        self.assertEqual(result['first_start_wall_ns'], 0)
        self.assertEqual(result['last_end_wall_ns'], 65000000)
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


class ServeNativeSafetyTests(unittest.TestCase):
    """Only the instrumentation is mocked: the actual serve_native body is loaded.

    An import failure, broken output or broken clock must leave all normal
    evaluator steps intact, without hiding exceptions from evaluator.tick().
    """

    class Robot:
        def __init__(self, count=3):
            self.count = count
            self.calls = 0
            self.ticks = 0

        def step(self, duration_ms):
            assert duration_ms == 8
            self.calls += 1
            return 0 if self.calls <= self.count else -1

        def getTime(self):
            return .008 * self.calls

    class Evaluator:
        def __init__(self, robot, course, *, scene_policy):
            assert course == 'course'
            assert scene_policy == 'classroom-static-v1'
            self.robot = robot

        def tick(self):
            self.robot.ticks += 1

    def function(self):
        import ast
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / 'tools/grand_prix/evaluator_publisher_v2.py'
        tree = ast.parse(src.read_text(encoding='utf-8'))
        original = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'serve_native')
        program = compile(ast.Module(body=[original], type_ignores=[]), str(src), 'exec')
        namespace = {'NativeRouteEvaluator': self.Evaluator}
        exec(program, namespace)
        return namespace['serve_native']

    def verify(self, robot):
        self.assertEqual(robot.calls, robot.count + 1, 'physical step count changed')
        self.assertEqual(robot.ticks, robot.count, 'evaluator authority steps were skipped')

    def test_disabled_path_remains_default(self):
        import os
        from unittest import mock
        robot = self.Robot()
        with mock.patch.dict(os.environ, {'WEBEEBLOCKS_GP_STEP_WALL_PROBE': ''}):
            self.function()(robot, 'course')
        self.verify(robot)

    def test_instrument_import_failure_falls_back_to_original_loop(self):
        import os
        import sys
        import types
        from unittest import mock
        robot = self.Robot()
        broken = types.ModuleType('tools.grand_prix.step_wall_probe')
        with mock.patch.dict(os.environ, {'WEBEEBLOCKS_GP_STEP_WALL_PROBE': '1'}):
            with mock.patch.dict(sys.modules, {'tools.grand_prix.step_wall_probe': broken}):
                self.function()(robot, 'course')
        self.verify(robot)

    def test_slow_sink_failure_falls_back_without_skipping_step(self):
        import os
        import sys
        import types
        from unittest import mock
        robot = self.Robot()
        broken = types.ModuleType('tools.grand_prix.step_wall_probe')
        class SinkFails(StepWallProbe):
            recorded = 0
            def __init__(self, course_id, _sink):
                def broken_sink(_line):
                    raise OSError('diagnostic sink failed')
                super().__init__(course_id, broken_sink, window_steps=1)
            def record(self, *args):
                SinkFails.recorded += 1
                return super().record(*args)
        broken.StepWallProbe = SinkFails
        with mock.patch.dict(os.environ, {'WEBEEBLOCKS_GP_STEP_WALL_PROBE': '1'}):
            with mock.patch.dict(sys.modules, {'tools.grand_prix.step_wall_probe': broken}):
                self.function()(robot, 'course')
        self.verify(robot)
        self.assertEqual(SinkFails.recorded, 1)

    def test_instrument_clock_failure_falls_back_without_skipping_step(self):
        import os
        from unittest import mock
        robot = self.Robot()
        with mock.patch.dict(os.environ, {'WEBEEBLOCKS_GP_STEP_WALL_PROBE': '1'}):
            with mock.patch('time.perf_counter_ns', side_effect=OSError('diagnostic clock failed')):
                self.function()(robot, 'course')
        self.verify(robot)

