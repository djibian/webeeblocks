"""Quarantined real-pilot admission/fault/RESET proofs, no pupil program."""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, os.environ['GP_ROUTE_EVALUATOR_SOURCE'])
from controller import Supervisor
from tools.grand_prix.evaluator_publisher_v2 import NativeRouteEvaluator
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.route_solid_v2 import corner_boxes


def witness():
    robot = Supervisor()
    course = reference_course(5)
    output = Path(os.environ['GP_ROUTE_EVALUATOR_OUT'])
    trace = output.with_suffix('.trace')
    mode = os.environ['GP_ROUTE_EVALUATOR_MODE']
    if mode not in ('idle', 'flight-reset'):
        raise RuntimeError('unknown native evaluator probe mode')
    ack_path = Path(os.environ['GP_ROUTE_PILOT_ACK_OUT'])
    ready_path = Path(os.environ['GP_ROUTE_PILOT_NATIVE_READY_OUT'])
    body = robot.getFromDef(corner_boxes(course.route)[0].name)
    translation = body.getField('translation')
    original = list(translation.getSFVec3f())
    if mode == 'idle':
        # Prepare two real scene states. loadState() later applies the moved
        # pose after step() has returned, without advancing the native clock.
        body.saveState('canonical')
        moved = [original[0] + .10, original[1], original[2]]
        translation.setSFVec3f(moved)
        if robot.step(8) == -1 or abs(body.getPosition()[0] - moved[0]) > 1e-6:
            raise RuntimeError('could not prepare displaced native L')
        body.saveState('displaced')
        body.loadState('canonical')
        if abs(body.getPosition()[0] - original[0]) > 1e-6:
            raise RuntimeError('could not restore canonical native L before READY')
    evaluator = NativeRouteEvaluator(robot, course.identifier)
    evidence = dict(claim=('native-route-evaluator-ready-and-scene-revocation-no-flight'
                          if mode == 'idle' else 'native-route-evaluator-flight-service-loss-LAND-RESET-TAKEOFF-no-pupil-program'),
                    configuration=course.identifier, webots='R2025a', timestep_ms=8)
    phase = 'waiting'
    wall_started = time.monotonic()
    restored_ticks = 0
    service_lost = False
    first_context = None
    reset_context = None

    def ready_record(now):
        sample = evaluator.observation
        if (not description.startswith('GP_ROUTE_READY_V1 ') or
                sample.time_ms != now or not sample.flight.ground_confirmed or
                sample.flight.sensor_period_ms != 32 or
                not 0 <= now - sample.flight.time_ms <= 32 or
                now - evaluator._ground_since < 500 or evaluator._active is not None):
            raise RuntimeError('missing real native ground/range/READY evidence')
        return dict(time_ms=now, stable_since_ms=evaluator._ground_since,
                    sample_time_ms=sample.flight.time_ms, ranges_m=sample.flight.ranges_m,
                    position=sample.kinematics.position, velocity=sample.kinematics.velocity,
                    contact_count=len(sample.contacts.points))

    def finish():
        encoded = json.dumps(evidence, allow_nan=False, sort_keys=True)
        output.write_text(encoded + '\n')
        print('GP_ROUTE_EVALUATOR_NATIVE ' + encoded, flush=True)
        if robot.step(8) == -1:
            raise RuntimeError('native evaluator stdout grace step interrupted')
        robot.simulationQuit(0)

    def cue_takeoff(attempt, now):
        # Stimulus only. The production pilot still owns READY/START admission.
        target = ready_path if attempt == 1 else ready_path.with_suffix(ready_path.suffix + '.second')
        marker = f'GP_ROUTE_PROBE_READY_V1 attempt={attempt} course={course.identifier} time_ms={now}\n'
        pending = target.with_suffix(target.suffix + '.pending')
        pending.write_text(marker, encoding='utf-8')
        pending.replace(target)

    while True:
        step_started = time.monotonic()
        step_cpu_started = time.process_time()
        if robot.step(8) == -1:
            break
        step_cpu = time.process_time() - step_cpu_started
        step_wall = time.monotonic() - step_started
        if phase == 'corrupted':
            before = robot.getTime()
            body.loadState('displaced')
            if (abs(body.getPosition()[0] - moved[0]) > 1e-6 or
                    robot.getTime() != before):
                raise RuntimeError('native L mutation did not occur at the current tick')
            evidence['mutated_ms'] = round(before * 1000)
        tick_started = time.monotonic()
        tick_cpu_started = time.process_time()
        if not service_lost:
            evaluator.tick()
        tick_cpu = time.process_time() - tick_cpu_started
        tick_wall = time.monotonic() - tick_started
        now = round(robot.getTime() * 1000)
        description = robot.getSelf().getField('description').getSFString()
        with trace.open('a') as log:
            log.write(json.dumps(dict(time_ms=now, phase=evaluator.phase,
                                      error=evaluator.last_error,
                                      wall_elapsed_s=time.monotonic() - wall_started,
                                      step_wall_s=step_wall, tick_wall_s=tick_wall,
                                      step_cpu_s=step_cpu, tick_cpu_s=tick_cpu,
                                      position=(evaluator.observation.kinematics.position
                                                if evaluator.observation is not None else None))) + '\n')
        if now > (4000 if mode == 'idle' else 30000):
            raise RuntimeError('native READY/refusal witness incomplete: ' + evaluator.phase)
        if phase == 'waiting' and evaluator.phase == 'ready':
            evidence['ready'] = ready_record(now)
            first_context = evaluator._context
            if first_context.attempt != 1:
                raise RuntimeError('native first attempt is not fresh')
            if mode == 'flight-reset':
                cue_takeoff(1, now)
                phase = 'flying'
                continue
            phase = 'corrupted'
        elif phase == 'corrupted':
            if description or evaluator.phase != 'failed' or evaluator.last_error is None:
                raise RuntimeError('moved native L did not revoke READY')
            evidence['refused_ms'] = now
            body.loadState('canonical')
            if abs(body.getPosition()[0] - original[0]) > 1e-6:
                raise RuntimeError('could not restore native L after revocation')
            phase = 'restored'
        elif phase == 'restored':
            if description or evaluator._active is not None:
                raise RuntimeError('old native attempt resurrected after scene restoration')
            restored_ticks += 1
            if restored_ticks == 4:
                evidence['restored_still_refused_ms'] = now
                finish()
                return
        elif phase == 'flying':
            acks = json.loads(ack_path.read_text()) if ack_path.exists() else {}
            if acks.get('takeoff_ack_ms', -1) >= 0 and evaluator.phase == 'active':
                if (not description.startswith('GP_ROUTE_ALIVE_V1 attempt=1 ') or
                        evaluator.observation.kinematics.position[2] < .20):
                    raise RuntimeError('native TAKEOFF/ALIVE/airborne evidence absent')
                evidence['start_ms'] = evaluator._start_ms
                evidence['stalled_ms'] = now
                evidence['airborne_z'] = evaluator.observation.kinematics.position[2]
                service_lost = True  # do NOT clear the last ALIVE; stop renewal
                phase = 'await-reset'
        elif phase == 'await-reset':
            vehicle_data = evaluator._vehicle.getField('customData').getSFString()
            if vehicle_data == ('WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 '
                                'oracle=grand-prix-route-v2 status=not-achieved'):
                evidence.setdefault('failure_observed_ms', now)
            acks = json.loads(ack_path.read_text()) if ack_path.exists() else {}
            if acks.get('reset_ack_ms', -1) >= 0:
                if 'failure_observed_ms' not in evidence:
                    raise RuntimeError('native failed outcome not observed before RESET')
                # Resume the production evaluator in place after the broker
                # ACK. Recreating it would hide stale writes across RESET.
                service_lost = False
                phase = 'reset-ready'
        elif phase == 'reset-ready' and evaluator.phase == 'ready':
            if (evaluator._context.attempt != 2 or evaluator._context.epoch == first_context.epoch or
                    evaluator._vehicle.getField('customData').getSFString() != 'WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2'):
                raise RuntimeError('native RESET retained an old attempt/epoch/outcome')
            evidence['reset_ready'] = ready_record(now)
            evidence['fresh_epoch'] = True
            reset_context = evaluator._context
            cue_takeoff(2, now)
            phase = 'flying-after-reset'
        elif phase == 'flying-after-reset':
            acks = json.loads(ack_path.read_text())
            if acks.get('second_takeoff_ack_ms', -1) >= 0:
                if (evaluator.phase != 'active' or evaluator._context != reset_context or
                        not description.startswith('GP_ROUTE_ALIVE_V1 attempt=2 ') or
                        evaluator.observation.kinematics.position[2] < .20):
                    raise RuntimeError('native second TAKEOFF/ALIVE/airborne evidence absent')
                evidence['acks'] = acks
                evidence['second_takeoff'] = dict(start_ms=evaluator._start_ms, observed_ms=now,
                    airborne_z=evaluator.observation.kinematics.position[2])
                finish()
                return
    raise RuntimeError('native evaluator witness interrupted')


if __name__ == '__main__':
    try:
        witness()
    except Exception:
        import traceback
        traceback.print_exc()
        Supervisor().simulationQuit(1)
        raise
