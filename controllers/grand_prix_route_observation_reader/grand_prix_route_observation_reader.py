"""Separate Supervisor verifies real drone-owned range transport, never READY."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from controller import Supervisor
from tools.grand_prix.route_evaluator_wire_v2 import parse_flight_channel, Challenge
from tools.grand_prix.route_flight_observation_v2 import parse_flight_observation, OBSERVATION_FIELD


def reader_trace(message):
    """Diagnostic-only; intentionally never used as success evidence."""
    target = os.environ.get('GP_ROUTE_SAMPLE_READER_TRACE')
    if target:
        with Path(target).open('a', encoding='utf-8') as log:
            log.write(message + '\n')


def run(robot):
    reader_trace('reader-start')
    config = sys.argv[1]
    vehicle = robot.getFromDef('GP_SAMPLE_VEHICLE')
    if vehicle is None or vehicle.getField('controller').getSFString() != 'grand_prix_route_observation_probe':
        raise RuntimeError('unexpected native sample producer')
    # This native SFString is written by the OTHER Robot's flight controller;
    # these are never readings from this evaluator's own getDevice().
    sample = robot.getSelf().getField(OBSERVATION_FIELD)
    request = robot.getSelf().getField('customData')
    phase = robot.getFromDef('GP_SAMPLE_PHASE').getField('customData')
    evidence = robot.getSelf().getField('description')
    expected = ['far', 'near', 'shifted', 'invalid', 'stale', 'reset', 'new-epoch']
    records = []
    initial_raw = initial_context = None
    while robot.step(8) != -1:
        now = round(robot.getTime() * 1000)
        if now > 3000:
            raise RuntimeError('incomplete native sample transport sequence')
        label = phase.getSFString()
        if not label or (records and label == records[-1]['phase']):
            continue
        if label != expected[len(records)] or evidence.getSFString():
            raise RuntimeError('phase mismatch or accidental READY')
        raw, control = sample.getSFString(), request.getSFString()
        # Log lengths and phase, never the private epoch/nonce or sensor data.
        reader_trace(f'phase={label} index={len(records)} time_ms={now} '
                     f'sample_bytes={len(raw)} control_bytes={len(control)}')
        event = parse_flight_channel(control, config)
        if label in ('invalid', 'stale', 'reset'):
            try:
                parse_flight_observation(raw, event, now)
            except ValueError:
                pass
            else:
                raise RuntimeError('invalid/stale/reset sample accepted')
            if label != 'stale' and raw:
                raise RuntimeError('invalid/reset did not revoke the field')
            record = dict(phase=label, rejected=True, observed_ms=now, raw=raw)
        else:
            if type(event) is not Challenge:
                raise RuntimeError('no flight-owned challenge')
            value = parse_flight_observation(raw, event, now)
            if label == 'shifted' and value.time_ms % 32 != 16:
                raise RuntimeError('native off-phase sampling was not exercised')
            if value.ground_confirmed:
                raise RuntimeError('transport probe fabricated RESET confirmation')
            if label == 'far':
                initial_raw, initial_context = raw, event
            if label == 'new-epoch':
                if event.attempt != 2 or event.epoch == initial_context.epoch:
                    raise RuntimeError('RESET did not change context')
                try:
                    parse_flight_observation(initial_raw, event, now)
                except ValueError:
                    pass
                else:
                    raise RuntimeError('old attempt sample accepted')
            record = dict(phase=label, observed_ms=now, time_ms=value.time_ms,
                          ranges_m=value.ranges_m, raw=raw, control=control)
        records.append(record)
        reader_trace(f'phase-checked={label} rejected={record.get("rejected", False)}')
        if len(records) == len(expected):
            far, near = records[0]['ranges_m'][0], records[1]['ranges_m'][0]
            if not (.05 < near < far < 1.3 and far - near > .20):
                raise RuntimeError('real front sensor did not distinguish native wall distance')
            result = dict(claim='native-cross-robot-range-transport-no-admission',
                          webots='R2025a', configuration=config, cases=records)
            Path(os.environ['GP_ROUTE_SAMPLE_OUT']).write_text(
                json.dumps(result, allow_nan=False, sort_keys=True) + '\n')
            print('GP_ROUTE_SAMPLE_NATIVE ' + json.dumps(result, allow_nan=False, sort_keys=True), flush=True)
            reader_trace('reader-success-evidence-written')
            # Let Webots collect the flushed controller stdout before quitting.
            # The native JSON alone is insufficient: the host also requires the
            # identical GP_ROUTE_SAMPLE_NATIVE marker in the Webots log.
            if robot.step(8) == -1:
                raise RuntimeError('native sample evidence stdout not retired')
            robot.simulationQuit(0)
            return
    raise RuntimeError('native observer ended without complete evidence')


if __name__ == '__main__':
    robot = Supervisor()
    try:
        run(robot)
    except Exception as exc:
        import traceback
        try:
            reader_trace(f'exception={type(exc).__name__}: {exc}')
        except OSError:
            pass  # Preserve the original failure, never manufacture a PASS.
        traceback.print_exc()
        robot.simulationQuit(1)
        raise
