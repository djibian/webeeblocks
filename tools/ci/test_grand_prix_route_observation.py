"""Adversarial flight-channel parsing and real composition, not native flight."""
import contextlib
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.grand_prix.route_evaluator_wire_v2 import Challenge, Start
from tools.grand_prix.route_flight_observation_v2 import parse_flight_observation
from tools.grand_prix.prepare_u_runtime import prepare

CONFIG = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2'
EPOCH = 'ab' * 16
EVENT = Challenge(1, CONFIG, EPOCH)
RAW = (f'GP_ROUTE_SAMPLE_V1 attempt=1 config={CONFIG} epoch={EPOCH} '
       'time_ms=2112 period_ms=32 ground=1 ranges_um=0,200000,1234567,2000000,2001000')


class FlightObservationTests(unittest.TestCase):
    def test_reading_freshness_and_active_context_are_separate_from_authority(self):
        for delay in (0, 8, 16, 24, 32):
            value = parse_flight_observation(RAW, EVENT, 2112 + delay)
            self.assertEqual(value.time_ms, 2112)  # receipt does not refresh it
            self.assertEqual(value.ranges_m, (0., .2, 1.234567, 2., 2.001))
            self.assertTrue(value.ground_confirmed)
        shifted = parse_flight_observation(RAW.replace('time_ms=2112', 'time_ms=2128'), EVENT, 2136)
        self.assertEqual(shifted.time_ms, 2128)
        self.assertEqual(shifted.sensor_period_ms, 32)
        value = parse_flight_observation(RAW, Start(EVENT, 2112, 'admitted'), 2120)
        self.assertEqual(value.challenge, EVENT)
        self.assertFalse(hasattr(value, 'ready'))
        self.assertFalse(hasattr(value, 'native_validated'))
        self.assertFalse(parse_flight_observation(
            RAW.replace('ground=1', 'ground=0'), EVENT, 2112).ground_confirmed)

    def test_absent_stale_future_alias_and_overflow_are_refused(self):
        for raw in (None, b'', '', 'x' * 384, RAW + '\n', RAW + ' ',
                    RAW.replace('attempt=1', 'attempt=01'),
                    RAW.replace('attempt=1', 'attempt=18446744073709551616'),
                    RAW.replace('time_ms=2112', 'time_ms=+2112'),
                    RAW.replace('time_ms=2112', 'time_ms=02112'),
                    RAW.replace('time_ms=2112', 'time_ms=2113'),
                    RAW.replace('time_ms=2112', 'time_ms=1000000000000032'),
                    RAW.replace('ground=1', 'ground=true'),
                    RAW.replace('ground=1', 'ground=2'),
                    RAW.replace('period_ms=32', 'period_ms=16'),
                    RAW.replace('period_ms=32', 'period_ms=032'),
                    RAW.replace('200000,', '-1,'), RAW.replace('200000,', 'nan,'),
                    RAW.replace('200000,', 'inf,'), RAW.replace('200000,', '0200000,'),
                    RAW.replace('2001000', '2001001'), RAW.replace(',2001000', '')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_flight_observation(raw, EVENT, 2112)
        for now in (2111, 2145, -1, True, 2112., math.nan, 10**15 + 1):
            with self.subTest(now=now), self.assertRaises(ValueError):
                parse_flight_observation(RAW, EVENT, now)

    def test_reset_configuration_and_terminal_context_cannot_reuse_a_packet(self):
        for event in (None, False, Challenge(2, CONFIG, EPOCH),
                      Challenge(1, CONFIG, 'cd' * 16),
                      Challenge(1, CONFIG.replace('TGD', 'TDG'), EPOCH),
                      Challenge(True, CONFIG, EPOCH),
                      Start(EVENT, 2144, 'admitted'), Start(EVENT, 2112, 'failed'),
                      Start(EVENT, 2112, 'deadline')):
            with self.subTest(event=event), self.assertRaises(ValueError):
                parse_flight_observation(RAW, event, 2144)

    def test_native_bench_uses_exact_student_range_up_extension(self):
        from tools.ci import run_grand_prix_u_deadline_native as runner
        template = (runner.ROOT/'worlds/crazyflie_runtime_v2.wbt').read_text()
        drone = template[template.index('Crazyflie {'):
                         template.index('# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN')]
        slot = drone[drone.index('  extensionSlot ['):]
        scene = runner.route_observation_scene()
        self.assertIn(slot, scene)
        self.assertEqual(scene.count('DEF GP_SAMPLE_VEHICLE Crazyflie {'), 1)
        self.assertIn('controller "grand_prix_route_observation_probe"', scene)
        self.assertIn('name "range_up"', scene)
        self.assertNotIn('controller "crazyflie_runtime_v2"', scene)
        self.assertEqual(scene.count('DEF GP_ROUTE_EVALUATOR Robot {'), 1)

    def test_native_bench_refuses_missing_range_up_extension(self):
        from tools.ci import run_grand_prix_u_deadline_native as runner
        template = (runner.ROOT/'worlds/crazyflie_runtime_v2.wbt').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'worlds').mkdir()
            (root/'worlds/crazyflie_runtime_v2.wbt').write_text(
                template.replace('name "range_up"', 'name "miswired_up"'))
            with patch.object(runner, 'ROOT', root), self.assertRaisesRegex(
                    RuntimeError, 'missing or ambiguous native student sensor deck'):
                runner.route_observation_scene()

    def test_native_bench_refuses_exit_zero_without_native_evidence(self):
        from tools.ci import run_grand_prix_u_deadline_native as runner
        source_scene = runner.route_observation_scene()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'worlds').mkdir()
            out = root / 'out'
            out.mkdir()
            with patch.object(runner, 'ROOT', root), patch.object(runner, 'OUT', out), patch.object(
                    runner, 'route_observation_scene', return_value=source_scene), patch.object(
                    runner.subprocess, 'run'):
                with self.assertRaisesRegex(RuntimeError, 'native route sample evidence failed'):
                    runner.run_route_observation_native(root / 'webots', {})
            self.assertEqual(list((root / 'worlds').iterdir()), [])
            self.assertFalse(list(out.glob('*native.json')))

    def test_real_preparer_samples_own_devices_before_admission_only_in_route(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            prepare(root / 'u', legacy_worlds=False)
            prepare(root / 'route', legacy_worlds=False, route_observations=True)
            normal = (root / 'u/runtime_u.c').read_text()
            route = (root / 'route/runtime_u.c').read_text()
            self.assertNotIn('gp_route_observe_native', normal)
            begin = route.index('const double gp_route_ranges[5]')
            end = route.index('    if (gp_u_deadline(now, gp_pose_confirmed))', begin)
            native = route[begin:end]
            for side in ('front', 'back', 'left', 'right', 'up'):
                self.assertIn(f'wb_distance_sensor_get_value(range_{side}) / 1000.0', native)
                self.assertIn(f'wb_distance_sensor_get_sampling_period(range_{side}) == step', native)
            self.assertIn('gp_control_sample && gp_route_periods_valid', native)
            self.assertIn('gp_pose_confirmed, gp_route_ranges', native)
            self.assertLess(route.index('while (wb_robot_step(gp_u_next_step(step))'), begin)
            self.assertLess(end, route.index('if (!gp_u_start(now))'))
            self.assertEqual((root / 'u/file_broker_u.cpp').read_bytes(),
                             (root / 'route/file_broker_u.cpp').read_bytes())


if __name__ == '__main__':
    unittest.main()
