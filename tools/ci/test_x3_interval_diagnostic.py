#!/usr/bin/env python3
"""Production recorder/orchestration controls for the bounded X3 contrasts."""
import copy
import csv
import json
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/physical'))
import diagnose_x3_interval as subject

# Independent healthy decoded samples, not generated from health validator bounds.
DATA = {
    'barometer': {'baro.asl': 30., 'baro.pressure': 1000., 'baro.temp': 20.},
    'imu': {'acc.x': 0., 'acc.y': 0., 'acc.z': 1., 'gyro.x': 0., 'gyro.y': 0., 'gyro.z': 0.},
    'pose': {'range.zrange': 600., 'stabilizer.roll': 0., 'stabilizer.pitch': 0.,
             'stateEstimate.z': 0.6, 'stateEstimate.vz': 0., 'stabilizer.intToOut': 200.},
    'detector': {'sensorFilter.surfState': 0., 'sensorFilter.surfReason': 0.,
                 'sensorFilter.surfOffset': 0., 'sensorFilter.surfBaroD': 0.,
                 'sensorFilter.flowLocal': 1., 'sensorFilter.lateElig': 0.},
}
PARAMS = {'stabilizer.estimator': ('uint8_t', '3'), 'ukf.qualityGateTof': ('float', '20'),
          'ukf.baroNoise': ('float', '6.25'), 'ukf.surfaceOffsetS3': ('uint8_t', '1')}


class Callback:
    def __init__(self): self.rows = []
    def add_callback(self, callback): self.rows.append(callback)
    def call(self, *args):
        for row in self.rows: row(*args)


class Config:
    def __init__(self, name, period):
        self.name = name; self.period = period; self.columns = []
        self.data_received_cb = Callback(); self.error_cb = Callback(); self.active = False
    def add_variable(self, name, ctype):
        assert ctype == 'float'; self.columns.append(name)
    def start(self): self.active = True
    def stop(self): self.active = False


class FakePort(subject.LivePort):
    def __init__(self, failure=None):
        self.now = 5000.; self.connections = []; self.configs = []; self.failure = failure
        self.sequence = 0; self.parameter_reads = []; self.closed = []; self.stopped = []
    def clock(self): return self.now
    def open(self, uri):
        if self.failure == 'open': raise RuntimeError('connection uncertain')
        callback = Callback()
        cf = types.SimpleNamespace(connection_lost=callback, connection_failed=Callback(), state=3,
            log=types.SimpleNamespace(toc=types.SimpleNamespace(get_element_by_complete_name=lambda _: object()),
                                      add_config=self.configs.append),
            param=types.SimpleNamespace(get_value=lambda name: PARAMS[name][1]),
            commander=types.SimpleNamespace(send_setpoint=lambda *_: (_ for _ in ()).throw(AssertionError('Commander'))))
        self.connections.append(cf); self.sequence = 0
        return cf
    def close(self, cf):
        self.closed.append(cf)
        if self.failure == 'close': raise RuntimeError('close uncertain')
        super().close(cf)
    def stop(self, configs, recorder):
        self.stopped.extend(configs)
        super().stop(configs, recorder)
        if self.failure == 'stop': recorder.fail('log stop uncertain')
    def sleep(self, duration):
        self.now += duration
        self.sequence += 1
        if self.failure == 'interrupt' and self.sequence == 3: raise KeyboardInterrupt('operator interrupted')
        if self.failure == 'disconnect' and self.sequence == 3:
            self.connections[-1].connection_lost.call('uri', 'lost')
        for config in self.configs:
            if not config.active: continue
            stream = config.name.removeprefix('X3_interval_')
            if self.failure == 'startup' and stream == 'imu': continue
            if self.failure == 'stale' and self.sequence > 3: continue
            data = copy.deepcopy(DATA[stream])
            if self.failure == 'z' and stream == 'pose' and self.sequence == 3:
                data['stateEstimate.z'] = -2.814063310623169
            if self.failure == 'nan' and stream == 'pose' and self.sequence == 3:
                data['stabilizer.pitch'] = float('nan')
            config.data_received_cb.call(self.sequence * 20, data, config)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'trace'
    def geometry(self, mode):
        return json.dumps({'mode': mode, 'method': 'fixed guide with separately retained metric/time witness',
            'vehicle_z_before_m': .6, 'vehicle_z_after_m': .6,
            'surface_z_before_m': 0., 'surface_z_after_m': 0., 'uncertainty_m': .005}).encode()
    def run_trace(self, mode='handling-connected', failure=None):
        port = FakePort(failure)
        class Adapter:
            def __init__(self, cf): pass
            def describe(self, name): return PARAMS[name][0], False, 'wrong cached value'
            def read_fresh(self, name):
                port.parameter_reads.append(name)
                if failure == 'parameters' and name == 'stabilizer.estimator': return '2'
                return PARAMS[name][1]
            def write(self, *_): raise AssertionError('parameter write')
        module = types.ModuleType('cflib.crazyflie.log'); module.LogConfig = Config
        with patch.dict(sys.modules, {'cflib.crazyflie.log': module}), \
             patch.object(subject.preparation, 'CflibParamAdapter', Adapter), \
             patch.object(subject.capture.time, 'monotonic', port.clock):
            result = subject.observe_interval(self.output, 'radio://0/80/2M', mode, b'{"status":"PREPARED"}',
                self.geometry(mode), port=port, clock=port.clock, sleeper=port.sleep)
        value = json.loads((self.output / 'diagnostic-result.json').read_text())
        return result, value, port
    def test_connected_contrast_reuses_one_real_four_stream_recorder(self):
        result, value, port = self.run_trace()
        self.assertEqual(result, 0); self.assertEqual(value['status'], 'OBSERVED')
        self.assertEqual(len(port.connections), 1); self.assertEqual(len(port.closed), 1)
        self.assertEqual(port.parameter_reads, list(PARAMS))
        self.assertIsNone(value['physical_verdict']); self.assertFalse(value['scientific_trial'])
        phases = [e['phase'] for e in value['events'] if e['event'] == 'phase-start']
        self.assertEqual(phases, ['stationary-before', 'handling', 'stationary-after'])
        for name in DATA:
            rows = list(csv.DictReader(io.StringIO((self.output / 'epoch-1' / (name + '.csv')).read_text())))
            self.assertGreater(len(rows), 1000)
            self.assertEqual(value['epochs'][0]['streams'][name]['rows'], len(rows))
        self.assertEqual(port.connections[0].state, 0)
    def test_reconnection_has_two_disjoint_epochs_and_an_explicit_gap(self):
        result, value, port = self.run_trace('reconnect-stationary')
        self.assertEqual(result, 0); self.assertEqual(len(port.connections), 2)
        self.assertEqual(len(port.closed), 2); self.assertEqual(len(value['epochs']), 2)
        events = value['events']; closed = next(e for e in events if e['event'] == 'connection-close-complete')
        reopened = next(e for e in events if e['event'] == 'connection-open-start' and e['epoch'] == 2)
        self.assertGreaterEqual(reopened['host_monotonic_s'] - closed['host_monotonic_s'], 5.)
        self.assertEqual(sum(e['event'] == 'coverage-gap-start' for e in events), 2)
        self.assertTrue((self.output / 'epoch-2/pose.csv').is_file())
    def test_cleanup_event_storage_failure_cannot_bypass_transport_close(self):
        original = subject.capture.write_json_once
        for event in ('coverage-gap-start', 'logs-stop-start', 'connection-close-start', 'connection-close-complete'):
            self.output = Path(self.temp.name) / event
            writes = []
            def write(path, value):
                if isinstance(value, dict) and value.get('event') == event:
                    writes.append(path)
                    raise OSError('independent ' + event + ' storage failure')
                original(path, value)
            with patch.object(subject.capture, 'write_json_once', write):
                result, value, port = self.run_trace('reconnect-stationary')
            self.assertEqual(result, 1); self.assertEqual(value['status'], 'INCOMPLETE')
            self.assertEqual(len(port.connections), 1); self.assertEqual(len(port.closed), 1)
            self.assertEqual(len(port.stopped), 4); self.assertEqual(len(set(map(id, port.stopped))), 4)
            self.assertEqual(len(writes), 1)
            self.assertTrue(any(event + ' storage failure' in row for row in value['errors']))
            before = {p.name: p.read_bytes() for p in (self.output / 'epoch-1').glob('*.csv')}
            for config in port.configs:
                config.data_received_cb.call(999999, DATA[config.name.removeprefix('X3_interval_')], config)
            self.assertEqual({p.name: p.read_bytes() for p in (self.output / 'epoch-1').glob('*.csv')}, before)

    def test_primary_and_each_raw_close_failure_are_retained_without_retries(self):
        original_recorder = subject.capture.Recorder
        closes = []
        recorders = []
        def recorder(root):
            value = original_recorder(root)
            recorders.append(value)
            for name, stream in list(value.streams.items()):
                class Stream:
                    def __init__(self, name, stream): self.name, self.stream = name, stream
                    def flush(self): self.stream.flush()
                    def close(self):
                        closes.append(self.name); self.stream.close()
                        if self.name in ('barometer', 'pose'):
                            raise OSError('independent ' + self.name + ' close failure')
                value.streams[name] = Stream(name, stream)
            return value
        with patch.object(subject.capture, 'Recorder', recorder):
            result, value, port = self.run_trace('reconnect-stationary', 'z')
        self.assertEqual(result, 1); self.assertEqual(len(port.connections), 1)
        self.assertEqual(len(port.closed), 1)
        self.assertEqual(closes, list(DATA), 'every raw stream must close once despite another failure')
        self.assertTrue(any('stateEstimate.z' in row for row in value['errors']))
        self.assertTrue(any('barometer close failure' in row for row in value['errors']))
        self.assertTrue(any('pose close failure' in row for row in value['errors']))
        before = recorders[0].error
        bad = copy.deepcopy(DATA['pose']); bad['stateEstimate.z'] = -200.
        next(c for c in port.configs if c.name == 'X3_interval_pose').data_received_cb.call(999999, bad, None)
        self.assertEqual(recorders[0].error, before, 'late health callback changed sealed state')

    def test_result_storage_failure_reports_primary_and_storage_uncertainty(self):
        original = subject.capture.write_json_once
        writes = []
        def write(path, value):
            if path.name == 'diagnostic-result.json':
                writes.append(path); raise OSError('independent result storage failure')
            original(path, value)
        with patch.object(subject.capture, 'write_json_once', write):
            with self.assertRaises(subject.IntervalDiagnosticError) as caught:
                self.run_trace('reconnect-stationary', 'z')
        self.assertTrue(any('stateEstimate.z' in row for row in caught.exception.errors))
        self.assertTrue(any('result storage failure' in row for row in caught.exception.errors))
        self.assertEqual(len(writes), 1)
        self.assertTrue((self.output / 'epoch-1/pose.csv').is_file())
        self.assertFalse((self.output / 'diagnostic-result.json').exists())

    def test_primary_log_and_transport_failures_remain_distinct(self):
        original = FakePort
        class Port(original):
            def stop(self, configs, recorder):
                super().stop(configs, recorder)
                raise RuntimeError('independent log teardown uncertainty')
            def close(self, cf):
                super().close(cf)
                raise RuntimeError('independent transport teardown uncertainty')
        with patch.object(sys.modules[__name__], 'FakePort', Port):
            result, value, port = self.run_trace('reconnect-stationary', 'z')
        self.assertEqual(result, 1); self.assertEqual(len(port.connections), 1)
        self.assertEqual(len(port.closed), 1); self.assertEqual(len(port.stopped), 4)
        for cause in ('stateEstimate.z', 'log teardown uncertainty', 'transport teardown uncertainty'):
            self.assertTrue(any(cause in row for row in value['errors']))

    def test_raw_write_failure_retains_partial_trace_and_still_closes(self):
        original = subject.capture.Recorder
        def recorder(root):
            value = original(root)
            writer = value.writers['pose']
            class Writer:
                def writerow(self, row):
                    if value.stats['pose']['rows'] >= 3:
                        raise OSError('independent raw storage failure')
                    writer.writerow(row)
            value.writers['pose'] = Writer()
            return value
        with patch.object(subject.capture, 'Recorder', recorder):
            result, value, port = self.run_trace('reconnect-stationary')
        self.assertEqual(result, 1); self.assertEqual(len(port.connections), 1)
        self.assertEqual(len(port.closed), 1)
        self.assertTrue(any('raw storage failure' in row for row in value['errors']))
        self.assertEqual(value['epochs'][0]['streams']['pose']['rows'], 3)
    def test_all_failures_retain_partial_raw_and_preparation_without_reopening(self):
        for failure in ('open', 'startup', 'parameters', 'stale', 'z', 'nan', 'stop', 'close', 'interrupt', 'disconnect'):
            with self.subTest(failure=failure):
                self.output = Path(self.temp.name) / failure
                result, value, port = self.run_trace('reconnect-stationary', failure)
                self.assertEqual(result, 1); self.assertEqual(value['status'], 'INCOMPLETE')
                self.assertTrue(value['errors']); self.assertLessEqual(len(port.connections), 1)
                self.assertEqual((self.output / 'preparation-record.json').read_bytes(), b'{"status":"PREPARED"}')
                self.assertEqual(len(value['epochs']), 1)
                if failure in ('z', 'nan'):
                    rows = list(csv.DictReader(io.StringIO((self.output / 'epoch-1/pose.csv').read_text())))
                    field = 'stateEstimate.z' if failure == 'z' else 'stabilizer.pitch'
                    self.assertEqual(rows[-1][field], '-2.814063310623169' if failure == 'z' else 'nan')
    def test_cli_local_rejections_precede_health_hardware(self):
        import verify_x3_characterization_bundle as manifest
        record = Path(self.temp.name) / 'prepared.json'
        record.write_text(json.dumps({'repository_target_sha': 'a' * 40}))
        geometry = Path(self.temp.name) / 'geometry.json'
        geometry.write_bytes(self.geometry('handling-connected'))
        args = ['diagnose', '--uri', 'radio://0/80/2M', '--mode', 'handling-connected',
            '--checkpoint-url', 'https://github.com/djibian/webeeblocks/issues/1',
            '--request-sha', 'a' * 40, '--preparation-record', str(record),
            '--geometry', str(geometry), '--output', str(self.output), '--props-removed']
        calls = []
        with patch.object(manifest, 'verify_bundle'), \
             patch.object(subject.preparation, 'validate_record'), \
             patch.object(subject.preparation, 'verify_live_health', lambda *_args, **_kw: calls.append('health')), \
             patch.object(sys, 'argv', args):
            geometry.write_bytes(b'{}')
            with self.assertRaises(ValueError): subject.main()
            geometry.write_bytes(self.geometry('handling-connected'))
            self.output.mkdir()
            with self.assertRaises(ValueError): subject.main()
            self.output.rmdir()
            record.write_text(json.dumps({'repository_target_sha': 'b' * 40}))
            with self.assertRaises(ValueError): subject.main()
        self.assertFalse(calls, 'failed local admission must not open even the health connection')

    def test_bad_geometry_and_existing_evidence_do_not_open(self):
        port = FakePort()
        for geometry in (b'{}', self.geometry('handling-connected')):
            with self.assertRaises(ValueError):
                subject.observe_interval(self.output, 'uri', 'reconnect-stationary', b'{}', geometry, port=port)
        self.output.mkdir(); (self.output / 'sentinel').write_text('existing')
        with self.assertRaises(FileExistsError):
            subject.observe_interval(self.output, 'uri', 'handling-connected', b'{}', self.geometry('handling-connected'), port=port)
        self.assertFalse(port.connections); self.assertEqual((self.output / 'sentinel').read_text(), 'existing')


if __name__ == '__main__': unittest.main()
