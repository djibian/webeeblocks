#!/usr/bin/env python3
"""Bounded props-off X3 interval observations; no scientific/flight verdict."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1] / 'experiments/crazyflie-ukf-surface-range'
if (EXPERIMENT / 'capture_independent_inputs.py').is_file():
    sys.path.insert(0, str(EXPERIMENT))
import capture_independent_inputs as capture
import prepare_x3_independent_capture as preparation
from x3_no_commander_link import close_link_without_commander

SCHEMA = 'webeeblocks.x3.interval-diagnostic.v1'
PHASE_SECONDS = 10.0
DISCONNECTED_SECONDS = 5.0
PLANS = {
    'handling-connected': (('stationary-before', 'handling', 'stationary-after'),),
    'reconnect-stationary': (('stationary-before-close',), ('stationary-after-reconnect',)),
}


def causal_errors(exc):
    rows, seen = [], set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc)); rows.append(f'{type(exc).__name__}: {exc}')
        exc = exc.__cause__ or exc.__context__
    return rows


def require_geometry(value, mode):
    if (not isinstance(value, dict) or set(value) != {'mode', 'method', 'vehicle_z_before_m',
            'vehicle_z_after_m', 'surface_z_before_m', 'surface_z_after_m', 'uncertainty_m'}
            or value['mode'] != mode or not isinstance(value['method'], str) or not value['method'].strip()):
        raise ValueError('explicit independently witnessed geometry plan required')
    for key in ('vehicle_z_before_m', 'vehicle_z_after_m', 'surface_z_before_m', 'surface_z_after_m', 'uncertainty_m'):
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]):
            raise ValueError('finite planned geometry coordinates required')
    if value['uncertainty_m'] <= 0:
        raise ValueError('positive declared witness uncertainty required')
    if mode == 'reconnect-stationary' and (value['vehicle_z_before_m'] != value['vehicle_z_after_m']
            or value['surface_z_before_m'] != value['surface_z_after_m']):
        raise ValueError('connection contrast requires unchanged declared geometry')


class LivePort:
    """One-shot port; lazy cflib imports and only log/PARAM read operations."""
    def open(self, uri):
        return preparation.open_live_crazyflie(uri)
    def observe(self, cf, recorder):
        from cflib.crazyflie.log import LogConfig
        adapter = preparation.CflibParamAdapter(cf)
        readbacks = {}
        for name, spec in preparation.PARAMETERS.items():
            ctype, _, _ = adapter.describe(name)
            raw = adapter.read_fresh(name)
            readbacks[name] = {'ctype': ctype, 'raw': repr(raw)}
            capture.write_json_once(recorder.root / ('readback-' + name + '.json'), readbacks[name])
            if ctype != spec['ctype'] or not preparation.same_value(ctype, raw, spec['value']):
                raise ValueError('frozen X3 parameter readback mismatch: ' + name)
        capture.require_inputs(cf)
        cf.connection_lost.add_callback(lambda *_: recorder.fail('Crazyradio connection lost'))
        cf.connection_failed.add_callback(lambda *_: recorder.fail('Crazyradio connection failed'))
        configs = []
        try:
            for name, (period, columns) in capture.BLOCKS.items():
                config = LogConfig('X3_interval_' + name, period)
                for column in columns:
                    config.add_variable(column, 'float')
                cf.log.add_config(config)
                raw_callback = recorder.callback(name)
                def received(timestamp, data, config, *, stream=name, raw_callback=raw_callback):
                    raw_callback(timestamp, data, config)
                    if stream == 'pose':
                        # The raw row is retained before applying the unchanged
                        # health bounds. A rejected row cannot complete the trace.
                        for field, (low, high) in preparation.HEALTH_BOUNDS.items():
                            value = data.get(field)
                            if (type(value) not in (int, float) or not math.isfinite(value)
                                    or value < low or value > high):
                                recorder.fail('unchanged health bound rejected: ' + field)
                                break
                config.data_received_cb.add_callback(received)
                config.error_cb.add_callback(lambda conf, message: recorder.fail(f'{conf.name}: {message}'))
                configs.append(config)
                config.start()
            return configs
        except BaseException:
            self.stop(configs, recorder)
            raise
    def stop(self, configs, recorder):
        for config in configs:
            try:
                config.stop()
            except BaseException as exc:
                recorder.fail('log stop failed: ' + str(exc))
    def close(self, cf):
        close_link_without_commander(cf)


def observe_interval(output, uri, mode, preparation_bytes, geometry_bytes, *, port=None,
                     clock=time.monotonic, sleeper=time.sleep, checkpoint_url=None):
    """Execute the frozen diagnostic plan; caller must validate the exact bundle/record."""
    geometry = json.loads(geometry_bytes)
    if mode not in PLANS:
        raise ValueError('unknown diagnostic contrast')
    require_geometry(geometry, mode)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'preparation-record.json').write_bytes(preparation_bytes)
    (output / 'geometry-plan.json').write_bytes(geometry_bytes)
    capture.write_json_once(output / 'diagnostic-start.json', {
        'schema': SCHEMA, 'uri': uri, 'mode': mode, 'plans': PLANS[mode],
        'repository_target_sha': json.loads(preparation_bytes).get('repository_target_sha'),
        'checkpoint_url': checkpoint_url,
        'diagnostic_script_sha256': capture.file_digest(Path(__file__)),
        'phase_seconds': PHASE_SECONDS, 'disconnected_seconds': DISCONNECTED_SECONDS,
        'preparation_record_sha256': hashlib.sha256(preparation_bytes).hexdigest(),
        'geometry_plan_sha256': hashlib.sha256(geometry_bytes).hexdigest(),
        'blocks': capture.BLOCKS, 'health_bounds': preparation.HEALTH_BOUNDS,
        'physical_verdict': None, 'scientific_trial': False,
        'boundary': 'phase markers are host schedule, not measured physical motion; disconnected intervals have no sensor coverage',
    })
    port = port or LivePort()
    events, epochs, error = [], [], None
    def event(kind, **fields):
        row = {'event': kind, 'host_monotonic_s': clock(), **fields}
        events.append(row)
        # Exclusive per-event files preserve partial sequence on failure.
        capture.write_json_once(output / f'event-{len(events):03}.json', row)
    try:
        for index, phases in enumerate(PLANS[mode]):
            root = output / f'epoch-{index + 1}'; root.mkdir()
            recorder = capture.Recorder(root)
            cf, configs = None, []
            try:
                event('connection-open-start', epoch=index + 1)
                cf = port.open(uri)
                event('connection-open-complete', epoch=index + 1)
                configs = port.observe(cf, recorder)
                event('logs-started', epoch=index + 1)
                deadline = clock() + 5.0
                while not recorder.check_streams(startup=True):
                    if clock() >= deadline:
                        raise RuntimeError('required streams did not become observable within 5 s')
                    sleeper(0.02)
                event('logs-ready', epoch=index + 1, coverage='each stream begins at its own first retained sample; setup gaps remain unknown')
                for phase in phases:
                    event('phase-start', epoch=index + 1, phase=phase)
                    print('DIAGNOSTIC PHASE: ' + phase, flush=True)
                    deadline = clock() + PHASE_SECONDS
                    while clock() < deadline:
                        recorder.check_streams(); sleeper(0.02)
                    recorder.check_streams()
                    event('phase-end', epoch=index + 1, phase=phase)
            finally:
                try:
                    event('coverage-gap-start', epoch=index + 1, reason='logs stopping; no interpolation through close/setup')
                    event('logs-stop-start', epoch=index + 1)
                    port.stop(configs, recorder)
                finally:
                    try:
                        if cf is not None:
                            event('connection-close-start', epoch=index + 1)
                            port.close(cf)
                            event('connection-close-complete', epoch=index + 1)
                    finally:
                        recorder.close()
                        epochs.append({'epoch': index + 1, 'streams': recorder.stats, 'error': recorder.error})
                if recorder.error:
                    raise RuntimeError(recorder.error)
            if index + 1 < len(PLANS[mode]):
                sleeper(DISCONNECTED_SECONDS)
                event('coverage-gap-wait-complete', boundary='gap continues until each next stream has fresh samples')
    except BaseException as exc:
        error = causal_errors(exc)
    finally:
        capture.write_json_once(output / 'diagnostic-result.json', {
            'schema': SCHEMA, 'status': 'OBSERVED' if error is None else 'INCOMPLETE',
            'errors': error, 'events': events, 'epochs': epochs,
            'physical_verdict': None, 'scientific_trial': False,
            'boundary': 'raw diagnostic coverage only; no interpolation, causal conclusion, scientific replacement, health guarantee or retry',
        })
    return 0 if error is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uri', required=True)
    parser.add_argument('--checkpoint-url', required=True)
    parser.add_argument('--request-sha', required=True)
    parser.add_argument('--mode', choices=PLANS, required=True)
    parser.add_argument('--preparation-record', type=Path, required=True)
    parser.add_argument('--geometry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--props-removed', action='store_true')
    args = parser.parse_args()
    if not args.props_removed or not re.fullmatch(r'radio://[0-9]+/[0-9]+/(250K|1M|2M)(/[0-9A-Fa-f]+)?', args.uri):
        raise ValueError('props removed and explicit Crazyradio URI required')
    # Exact manifest and PREPARED record are checked before creating output or
    # connecting. Existing #567 admission-health evidence remains its own sidecar.
    from verify_x3_characterization_bundle import verify_bundle
    verify_bundle(HERE)
    record = args.preparation_record.read_bytes()
    value = json.loads(record)
    if (not re.fullmatch(r'https://github.com/djibian/webeeblocks/issues/[1-9][0-9]*', args.checkpoint_url)
            or not re.fullmatch(r'[0-9a-f]{40}', args.request_sha)
            or value.get('repository_target_sha') != args.request_sha):
        raise ValueError('exact checkpoint request SHA/URL required')
    preparation.validate_record(value, uri=args.uri,
        firmware_bin=HERE / 'cf2.bin', provenance_path=HERE / 'PROVENANCE.txt')
    geometry = args.geometry.read_bytes()
    require_geometry(json.loads(geometry), args.mode)
    sidecar = Path(str(args.output) + '.health')
    for output in (args.output, sidecar):
        if output.exists() or output.is_symlink() or output.resolve().is_relative_to(HERE):
            raise ValueError('new output outside the exact bundle is required')
    preparation.verify_live_health(args.uri, evidence_output=Path(str(args.output) + '.health'),
                                   preparation_record=args.preparation_record)
    # The sidecar retains its exact binding before this second connection.
    # No continuous coverage is claimed through that initial gap.
    return observe_interval(args.output, args.uri, args.mode, record, geometry, checkpoint_url=args.checkpoint_url)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print('DIAGNOSTIC_ERROR: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
