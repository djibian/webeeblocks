"""Quarantined real-pilot admission/fault/RESET proofs, no pupil program."""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, os.environ['GP_ROUTE_EVALUATOR_SOURCE'])
from controller import Supervisor
from tools.grand_prix import evaluator_publisher_v2 as publisher
from tools.grand_prix.evaluator_publisher_v2 import (
    NativeRouteEvaluator, SCENE_POLICY_CLASSROOM_STATIC, SCENE_POLICY_CONTINUOUS)
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.route_solid_v2 import corner_boxes


def witness():
    robot = Supervisor()
    # A real Webots worldLoad() terminates and restarts every controller.
    # Test-only on-disk stage distinguishes the new process from a RESET.
    stage_file = Path(os.environ['GP_ROUTE_EVALUATOR_OUT']).with_name('switch-stage.json')
    switched = (os.environ.get('GP_ROUTE_EVALUATOR_MODE') in ('classroom-switch', 'classroom-switch-invalid') and
                stage_file.is_file())
    index = int(os.environ['GP_ROUTE_SWITCH_INDEX'] if switched else
                os.environ.get('GP_ROUTE_EVALUATOR_INDEX', '5'))
    course = reference_course(index)
    output = Path(os.environ['GP_ROUTE_EVALUATOR_OUT'])
    trace = output.with_suffix('.trace')
    mode = os.environ['GP_ROUTE_EVALUATOR_MODE']
    if mode not in ('idle', 'flight-reset', 'classroom-startup', 'classroom-invalid',
                    'paired-benchmark', 'session-benchmark', 'flight-window',
                    'classroom-switch', 'classroom-switch-invalid',
                    'flight-course-negative', 'flight-altitude-negative'):
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
    # Instrument the production native checker without replacing its code or
    # feeding it synthetic scene values. Static checks must occur exactly once
    # per fresh Webots evaluator, including after ordinary RESET.
    scene_checks = [0]
    real_read_scene = publisher.read_native_evaluator_scene
    def traced_read_scene(*args, **kwargs):
        scene_checks[0] += 1
        return real_read_scene(*args, **kwargs)
    publisher.read_native_evaluator_scene = traced_read_scene
    policy = (SCENE_POLICY_CONTINUOUS if mode == 'idle' or
              (mode == 'flight-window' and
               os.environ.get('GP_ROUTE_PROFILE_POLICY') == SCENE_POLICY_CONTINUOUS)
              else SCENE_POLICY_CLASSROOM_STATIC)
    if mode == 'paired-benchmark':
        # SAME R2025a process, real 8-ms physics steps, actual native sensor
        # readings, idle pilot and identical timestamps. Alternate execution
        # order to control first-reader bias. This is only a per-tick CPU/wall
        # experiment, NOT a rendered FPS or whole-flight qualification.
        historical = NativeRouteEvaluator(robot, course.identifier,
                                          scene_policy=SCENE_POLICY_CONTINUOUS)
        classroom = NativeRouteEvaluator(robot, course.identifier,
                                         scene_policy=SCENE_POLICY_CLASSROOM_STATIC)
        if historical._scene_snapshot is None or classroom._scene_snapshot is not None:
            raise RuntimeError('paired native scene policies differ from expectation')
        names = ('historical-continuous-v1', 'classroom-static-v1')
        series = {name: [] for name in names}
        reads = {name: 0 for name in names}
        ready_at = first = last = None
        for index in range(800):
            if robot.step(8) == -1:
                raise RuntimeError('paired native Webots steps interrupted')
            now = round(robot.getTime() * 1000)
            order = ((names[0], historical), (names[1], classroom))
            if index % 2:
                order = order[::-1]
            durations = {}
            scene_deltas = {}
            for name, evaluator in order:
                old_checks = scene_checks[0]
                begin = time.perf_counter_ns()
                evaluator.tick()
                durations[name] = time.perf_counter_ns() - begin
                scene_deltas[name] = scene_checks[0] - old_checks
                if durations[name] <= 0:
                    raise RuntimeError('paired monotonic timing invalid')
            if historical.phase == 'failed' or classroom.phase == 'failed':
                raise RuntimeError('paired evaluator failed before READY witness')
            if ready_at is None:
                if historical.phase == classroom.phase == 'ready':
                    ready_at = now
                continue
            if (historical.phase != 'ready' or classroom.phase != 'ready' or
                    historical._context != classroom._context or
                    historical.observation is None or classroom.observation is None or
                    historical.observation != classroom.observation):
                raise RuntimeError('paired native observations diverged')
            if now - ready_at < 128:
                continue
            if scene_deltas != {names[0]: 1, names[1]: 0}:
                raise RuntimeError('paired native full-scene check counts diverged')
            if first is None:
                first = now
            last = now
            for name in names:
                series[name].append(durations[name])
                reads[name] += scene_deltas[name]
            if len(series[names[0]]) == 96:
                break
        if any(len(series[name]) != 96 for name in names):
            raise RuntimeError('paired native READY interval not established')
        evidence = dict(
            claim='native-route-evaluator-paired-ticks-v1',
            configuration=course.identifier, webots='R2025a',
            timestep_ms=8, phase='idle-ready', paired_same_step=True,
            order='alternating-AB-BA', samples=96,
            first_sim_ms=first, last_sim_ms=last,
            tick_wall_ns=series, scene_reads_measured=reads,
            wall_tick_ratio_historical_over_classroom=round(
                sum(series[names[0]]) / sum(series[names[1]]), 6))
        encoded = json.dumps(evidence, allow_nan=False, sort_keys=True)
        output.write_text(encoded + '\n')
        print('GP_ROUTE_EVALUATOR_NATIVE ' + encoded, flush=True)
        if robot.step(8) == -1:
            raise RuntimeError('paired native stdout grace step interrupted')
        robot.simulationQuit(0)
        return
    if mode == 'session-benchmark':
        # Separate R2025a simulator incarnation: exactly one production
        # evaluator per world. Different policies run in independent launches
        # of the SAME job, world, host and Webots binary. The real pilot stays
        # idle; READY is native. These are no-GUI performance observations,
        # never authority for real flight or pupil mission success.
        selected = os.environ.get('GP_ROUTE_PROFILE_POLICY')
        if selected not in (SCENE_POLICY_CONTINUOUS, SCENE_POLICY_CLASSROOM_STATIC):
            raise RuntimeError('session benchmark requires explicit policy')
        evaluator = NativeRouteEvaluator(robot, course.identifier,
                                         scene_policy=selected)
        if scene_checks[0] != 1:
            raise RuntimeError('session benchmark startup attestation count invalid')
        durations = {'step_wall_ns': [], 'tick_wall_ns': [], 'cycle_wall_ns': []}
        ready_at = first = last = None
        first_wall_ns = last_wall_ns = None
        observed_scene_reads = 0
        for _ in range(900):
            step_started = time.perf_counter_ns()
            if robot.step(8) == -1:
                raise RuntimeError('session benchmark native Webots interrupted')
            step_ended = time.perf_counter_ns()
            before_checks = scene_checks[0]
            evaluator.tick()
            tick_ended = time.perf_counter_ns()
            now = round(robot.getTime() * 1000)
            if (evaluator.phase == 'failed' or
                    tick_ended <= step_ended or step_ended <= step_started):
                raise RuntimeError('session benchmark terminal or invalid timing')
            if ready_at is None:
                if evaluator.phase == 'ready':
                    ready_at = now
                continue
            if evaluator.phase != 'ready':
                raise RuntimeError('session benchmark READY not sustained')
            observation = evaluator.observation
            if (observation is None or observation.time_ms != now or
                    not observation.flight.ground_confirmed or
                    not 0 <= now - observation.flight.time_ms <= 32):
                raise RuntimeError('session benchmark lacked fresh native observation')
            if now - ready_at < 128:
                continue
            checks_this_tick = scene_checks[0] - before_checks
            expected_checks = 1 if selected == SCENE_POLICY_CONTINUOUS else 0
            if checks_this_tick != expected_checks:
                raise RuntimeError('session benchmark scene-read policy mismatch')
            observed_scene_reads += checks_this_tick
            if first is None:
                first = now
                first_wall_ns = step_started
            last = now
            last_wall_ns = tick_ended
            durations['step_wall_ns'].append(step_ended - step_started)
            durations['tick_wall_ns'].append(tick_ended - step_ended)
            durations['cycle_wall_ns'].append(tick_ended - step_started)
            if len(durations['step_wall_ns']) == 96:
                break
        if any(len(values) != 96 for values in durations.values()):
            raise RuntimeError('session benchmark 96 native cycles unavailable')
        record = dict(
            claim='native-route-evaluator-independent-session-cycles-v1',
            configuration=course.identifier, webots='R2025a',
            timestep_ms=8, phase='idle-ready', mode='batch-fast-minimized',
            policy=selected, samples=96, ready_sim_ms=ready_at,
            first_sim_ms=first, last_sim_ms=last,
            simulated_ms=96 * 8, measured_window_wall_ns=last_wall_ns - first_wall_ns,
            scene_reads_measured=observed_scene_reads,
            scene_checks_total=scene_checks[0], durations_ns=durations)
        encoded = json.dumps(record, allow_nan=False, sort_keys=True)
        output.write_text(encoded + '\n')
        print('GP_ROUTE_EVALUATOR_NATIVE ' + encoded, flush=True)
        if robot.step(8) == -1:
            raise RuntimeError('session benchmark stdout grace step interrupted')
        robot.simulationQuit(0)
        return
    if mode in ('classroom-startup', 'classroom-invalid', 'classroom-switch',
                'classroom-switch-invalid'):
        # Exercise the *actual* production serve_native() loop, not an
        # isolated constructor/tick emulation. This observer wraps only the
        # evaluator's methods and terminates after genuine native READY.
        class ObserveRealEvaluator:
            def __init__(self, native_robot, identifier, *, scene_policy):
                if scene_policy != SCENE_POLICY_CLASSROOM_STATIC:
                    raise RuntimeError('product entrypoint selected non-classroom policy')
                self.real = NativeRouteEvaluator(native_robot, identifier,
                                                 scene_policy=scene_policy)

            def tick(self):
                self.real.tick()
                if self.real.phase != 'ready':
                    return
                observation = self.real.observation
                now = round(robot.getTime() * 1000)
                if (scene_checks[0] != 1 or self.real._scene_snapshot is not None or
                        observation is None or observation.time_ms != now or
                        not observation.flight.ground_confirmed or
                        observation.flight.sensor_period_ms != 32 or
                        not 0 <= now - observation.flight.time_ms <= 32 or
                        self.real._ground_since is None or
                        now - self.real._ground_since < 500):
                    raise RuntimeError('real serve_native READY lacked startup attestation')
                ready = dict(time_ms=now, stable_since_ms=self.real._ground_since,
                             sample_time_ms=observation.flight.time_ms,
                             ranges_m=observation.flight.ranges_m,
                             position=observation.kinematics.position,
                             velocity=observation.kinematics.velocity,
                             contact_count=len(observation.contacts.points))
                evidence = dict(claim='native-classroom-startup-attestation-v1',
                                configuration=course.identifier, webots='R2025a',
                                timestep_ms=8, ready=ready, scene_checks=scene_checks[0],
                                new_evaluator_native_id=robot.getSelf().getId(),
                                ready_before_mission=True)
                if mode in ('classroom-switch', 'classroom-switch-invalid'):
                    # The first READY is in course 5. worldLoad() replaces the
                    # world with course 0 and restarts both C pilot and evaluator.
                    # Neither scene nor authority from the first incarnation
                    # may be used to grant READY to the second.
                    current = dict(configuration=course.identifier,
                                   time_ms=now, ready=ready,
                                   scene_checks=scene_checks[0],
                                   native_evaluator_id=robot.getSelf().getId(),
                                   controller_pid=os.getpid())
                    if not switched:
                        if stage_file.exists() or output.exists():
                            raise RuntimeError('native world switch stage already exists')
                        source = json.dumps(current, allow_nan=False, sort_keys=True)
                        stage_file.write_text(source + '\n')
                        print('GP_ROUTE_SWITCH_BEFORE ' + source, flush=True)
                        # Let Webots forward the first native stdout before
                        # replacing the world and terminating this controller.
                        if robot.step(8) == -1:
                            raise RuntimeError('native world switch first stdout step interrupted')
                        robot.worldLoad(os.environ['GP_ROUTE_SWITCH_WORLD'])
                        return
                    first = json.loads(stage_file.read_text())
                    if (first['controller_pid'] == os.getpid() or
                            first['configuration'] == course.identifier or
                            first['scene_checks'] != 1):
                        raise RuntimeError('native world switch reused evaluator authority')
                    evidence = dict(
                        claim='native-classroom-world-switch-attestation-v1',
                        webots='R2025a', timestep_ms=8,
                        first=first, second=current,
                        new_world_loaded=True, fresh_controller=True)
                    encoded = json.dumps(evidence, allow_nan=False, sort_keys=True)
                    output.write_text(encoded + '\n')
                    print('GP_ROUTE_EVALUATOR_NATIVE ' + encoded, flush=True)
                    if robot.step(8) == -1:
                        raise RuntimeError('native world switch second stdout step interrupted')
                    robot.simulationQuit(0)
                    return
                encoded = json.dumps(evidence, allow_nan=False, sort_keys=True)
                output.write_text(encoded + '\n')
                print('GP_ROUTE_EVALUATOR_NATIVE ' + encoded, flush=True)
                robot.simulationQuit(0)

        publisher.NativeRouteEvaluator = ObserveRealEvaluator
        if mode == 'classroom-invalid':
            try:
                publisher.serve_native(robot, course.identifier)
            except RuntimeError as error:
                if not str(error).startswith('native collider world pose mismatch: GP_V2_L_'):
                    raise
                if robot.getSelf().getField('description').getSFString():
                    raise RuntimeError('invalid native initial scene published READY')
                evidence = dict(claim='native-classroom-startup-attestation-v1',
                                configuration=course.identifier, webots='R2025a',
                                timestep_ms=8, rejected_before_ready=True,
                                scene_checks=scene_checks[0], error=str(error))
                encoded = json.dumps(evidence, allow_nan=False, sort_keys=True)
                output.write_text(encoded + '\n')
                print('GP_ROUTE_EVALUATOR_NATIVE ' + encoded, flush=True)
                # Webots forwards controller stdout on a native step. Without
                # this grace step the JSON is durable, but the stdout mirror
                # can be lost when the rejected world exits immediately.
                # Do not resume serve_native() or publish READY.
                if robot.step(8) == -1:
                    raise RuntimeError('native invalid startup stdout grace step interrupted')
                if robot.getSelf().getField('description').getSFString():
                    raise RuntimeError('invalid native initial scene published READY during grace step')
                robot.simulationQuit(0)
                return
            raise RuntimeError('noncanonical initial native world was admitted')
        if mode == 'classroom-switch-invalid' and switched:
            # The same Webots process has loaded a *different* world, whose
            # native L collider is malformed before the new evaluator starts.
            # serve_native() must reject construction before any READY.
            try:
                publisher.serve_native(robot, course.identifier)
            except RuntimeError as error:
                if (not str(error).startswith('native collider world pose mismatch: GP_V2_L_') or
                        scene_checks[0] != 1):
                    raise
                if robot.getSelf().getField('description').getSFString():
                    raise RuntimeError('noncanonical reloaded world published READY')
                first = json.loads(stage_file.read_text())
                if (first['configuration'] == course.identifier or
                        first['controller_pid'] == os.getpid() or
                        first['scene_checks'] != 1):
                    raise RuntimeError('noncanonical reload reused old evaluator identity')
                second = dict(
                    configuration=course.identifier, controller_pid=os.getpid(),
                    native_evaluator_id=robot.getSelf().getId(),
                    time_ms=round(robot.getTime() * 1000),
                    scene_checks=scene_checks[0],
                    rejected_before_ready=True, error=str(error))
                evidence = dict(
                    claim='native-classroom-world-switch-invalid-rejection-v1',
                    webots='R2025a', timestep_ms=8,
                    first=first, second=second,
                    new_world_loaded=True, fresh_controller=True)
                encoded = json.dumps(evidence, allow_nan=False, sort_keys=True)
                output.write_text(encoded + '\n')
                print('GP_ROUTE_EVALUATOR_NATIVE ' + encoded, flush=True)
                if robot.step(8) == -1:
                    raise RuntimeError('invalid reloaded world stdout grace interrupted')
                if robot.getSelf().getField('description').getSFString():
                    raise RuntimeError('invalid reloaded world published READY during grace')
                robot.simulationQuit(0)
                return
            raise RuntimeError('malformed reloaded world admitted by serve_native')
        publisher.serve_native(robot, course.identifier)
        if mode in ('classroom-switch', 'classroom-switch-invalid') and not switched:
            # worldLoad has taken ownership of termination. The second
            # incarnation alone publishes native.json; missing it fails CI.
            return
        if not output.is_file():
            raise RuntimeError('production serve_native did not publish real READY')
        return
    evaluator = NativeRouteEvaluator(robot, course.identifier, scene_policy=policy)
    evidence = dict(claim=('native-route-evaluator-ready-and-scene-revocation-no-flight'
                          if mode == 'idle' else
                          'native-route-evaluator-flight-service-loss-LAND-RESET-TAKEOFF-no-pupil-program'
                          if mode == 'flight-reset' else
                          'native-classroom-startup-attestation-v1'),
                    configuration=course.identifier, webots='R2025a', timestep_ms=8)
    if mode == 'flight-window':
        evidence['claim'] = 'native-route-evaluator-real-airborne-window-v1'
    if mode == 'flight-course-negative':
        evidence['claim'] = 'native-route-evaluator-real-lateral-course-negative-v1'
    if mode == 'flight-altitude-negative':
        evidence['claim'] = 'native-route-evaluator-real-vertical-altitude-negative-v1'
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

    if mode == 'flight-window':
        # Two separate R2025a processes share the same flight probe binary.
        # Retain the authentic pilot C++ PID, native sensors, 8-ms physics,
        # mission oracle and TAKEOFF/ALIVE authority, without pupil AST.
        requested = os.environ.get('GP_ROUTE_PROFILE_POLICY')
        if requested not in (SCENE_POLICY_CONTINUOUS, SCENE_POLICY_CLASSROOM_STATIC):
            raise RuntimeError('airborne native comparison needs explicit policy')
        if policy != requested:
            raise RuntimeError('airborne evaluator policy mismatch')
        streams = {'step_wall_ns': [], 'tick_wall_ns': [], 'cycle_wall_ns': [],
                   'sim_time_ms': [], 'altitude_m': []}
        stage = 'await-ready'
        first_wall_ns = last_wall_ns = None
        measured_reads = 0
        for _ in range(2400):
            before = time.perf_counter_ns()
            if robot.step(8) == -1:
                raise RuntimeError('airborne native step interrupted')
            after_step = time.perf_counter_ns()
            before_reads = scene_checks[0]
            evaluator.tick()
            after_tick = time.perf_counter_ns()
            now = round(robot.getTime() * 1000)
            description = robot.getSelf().getField('description').getSFString()
            if evaluator.phase in ('failed', 'authority-revoked'):
                raise RuntimeError('airborne native evaluator revoked unexpectedly: ' +
                                   str(evaluator.last_error))
            if stage == 'await-ready':
                if evaluator.phase == 'ready':
                    evidence['ready'] = ready_record(now)
                    if evaluator._context is None or evaluator._context.attempt != 1:
                        raise RuntimeError('airborne first attempt not fresh')
                    cue_takeoff(1, now)
                    stage = 'await-airborne'
                continue
            if stage == 'await-airborne':
                acks = json.loads(ack_path.read_text()) if ack_path.exists() else {}
                if acks.get('takeoff_ack_ms', -1) < 0 or evaluator.phase != 'active':
                    continue
                z = evaluator.observation.kinematics.position[2]
                if z < .20:
                    continue
                if (not description.startswith('GP_ROUTE_ALIVE_V1 attempt=1 ') or
                        evaluator._start_ms is None or
                        acks['takeoff_ack_ms'] < evaluator._start_ms or
                        now < acks['takeoff_ack_ms'] or z > 1.165):
                    raise RuntimeError('native TAKEOFF/ALIVE/airborne ordering invalid')
                stage = 'measure'
                evidence['start_ms'] = evaluator._start_ms
                evidence['takeoff_ack_ms'] = acks['takeoff_ack_ms']
                evidence['first_airborne_ms'] = now
                evidence['first_airborne_z'] = z
                continue
            if stage != 'measure':
                raise RuntimeError('unexpected airborne phase')
            observation = evaluator.observation
            if (evaluator.phase != 'active' or evaluator._context.attempt != 1 or
                    observation is None or observation.time_ms != now or
                    not description.startswith('GP_ROUTE_ALIVE_V1 attempt=1 ') or
                    not 0 <= now - observation.flight.time_ms <= 32 or
                    observation.flight.sensor_period_ms != 32):
                raise RuntimeError('native airborne live observation or ALIVE lost')
            z = observation.kinematics.position[2]
            if not .20 <= z <= 1.165:
                raise RuntimeError('airborne altitude left bounded window')
            required_reads = 1 if policy == SCENE_POLICY_CONTINUOUS else 0
            if scene_checks[0] - before_reads != required_reads:
                raise RuntimeError('airborne native scene policy changed')
            measured_reads += required_reads
            if first_wall_ns is None:
                first_wall_ns = before
            last_wall_ns = after_tick
            streams['step_wall_ns'].append(after_step - before)
            streams['tick_wall_ns'].append(after_tick - after_step)
            streams['cycle_wall_ns'].append(after_tick - before)
            streams['sim_time_ms'].append(now)
            streams['altitude_m'].append(z)
            if len(streams['sim_time_ms']) == 96:
                evidence.update(
                    policy=policy, phase='active-airborne',
                    native_pilot=True, no_pupil_program=True,
                    samples=96, first_sim_ms=streams['sim_time_ms'][0],
                    last_sim_ms=now, simulated_ms=96 * 8,
                    measured_window_wall_ns=last_wall_ns - first_wall_ns,
                    scene_reads_measured=measured_reads,
                    scene_checks_total=scene_checks[0], streams=streams)
                finish()
                return
        raise RuntimeError('real native airborne measurement incomplete')

    if mode in ('flight-course-negative', 'flight-altitude-negative'):
        # Only a standard WWI MOVE or VERTICAL is injected into the genuine C
        # pilot. No Supervisor pose mutation, fake sensor or oracle override.
        # The vertical target is valid under Runtime's 1.5 m command limit,
        # but crosses the Grand Prix mission's independent 1.15 m ceiling.
        if policy != SCENE_POLICY_CLASSROOM_STATIC or scene_checks[0] != 1:
            raise RuntimeError('native dynamic negative needs one static attestation')
        negative_path = output.with_name('negative-request.txt')
        stage = 'ready'
        terminal_ms = None
        for _ in range(5400):
            if robot.step(8) == -1:
                raise RuntimeError('native dynamic negative Webots interrupted')
            evaluator.tick()
            now = round(robot.getTime() * 1000)
            description = robot.getSelf().getField('description').getSFString()
            if stage == 'ready':
                if evaluator.phase == 'ready':
                    evidence['ready'] = ready_record(now)
                    if evaluator._context is None or evaluator._context.attempt != 1:
                        raise RuntimeError('native dynamic negative lost fresh attempt')
                    cue_takeoff(1, now)
                    stage = 'airborne'
                continue
            acks = json.loads(ack_path.read_text()) if ack_path.is_file() else {}
            if stage == 'airborne':
                if evaluator.phase in ('failed', 'authority-revoked'):
                    raise RuntimeError('native negative failed before verified flight')
                if acks.get('takeoff_ack_ms', -1) < 0 or evaluator.phase != 'active':
                    continue
                sample = evaluator.observation
                if (sample is None or sample.kinematics.position[2] < .20 or
                        not description.startswith('GP_ROUTE_ALIVE_V1 attempt=1 ') or
                        sample.time_ms != now or
                        not 0 <= now - sample.flight.time_ms <= 32):
                    continue
                evidence['start_ms'] = evaluator._start_ms
                evidence['takeoff_ack_ms'] = acks['takeoff_ack_ms']
                evidence['airborne_ms'] = now
                evidence['airborne_z'] = sample.kinematics.position[2]
                stage = 'await-oracle-negative'
            if stage == 'await-oracle-negative':
                if evaluator.phase in ('failed', 'authority-revoked'):
                    if not negative_path.is_file():
                        raise RuntimeError('negative occurred without the real pilot MOVE')
                    command = negative_path.read_text()
                    prefix = ('GP_ROUTE_PILOT_NEGATIVE_REQUEST_V1 time_ms=')
                    action = ('VERTICAL-up-0.8' if mode == 'flight-altitude-negative'
                              else 'MOVE-right-1.2')
                    suffix = (' course=' + course.identifier +
                              ' action=' + action + '\\n')
                    if not command.startswith(prefix) or not command.endswith(suffix):
                        raise RuntimeError('native lateral command evidence corrupted')
                    request_ms = int(command[len(prefix):-len(suffix)])
                    if (request_ms % 8 or
                            not evidence['start_ms'] <= evidence['takeoff_ack_ms'] <=
                            request_ms < now):
                        raise RuntimeError('native lateral request ordering invalid')
                    reason = evaluator.last_error
                    allowed = (('altitude',) if mode == 'flight-altitude-negative'
                               else ('course-boundary', 'envelope-contact',
                                     'low-outside-zone'))
                    if reason not in allowed:
                        raise RuntimeError('oracle did not reject native requested motion: ' +
                                           str(reason))
                    if (evaluator._active is None or evaluator._active.result is None or
                            evaluator._active.result.reason != reason or
                            evaluator._positive_written or scene_checks[0] != 1 or
                            not description.startswith('GP_ROUTE_TERMINAL_V1 attempt=1 ')):
                        raise RuntimeError('native dynamic failure/terminal witness missing')
                    evidence.update(reason=reason, negative_request_ms=request_ms,
                        rejected_ms=now, scene_checks=scene_checks[0],
                        terminal_witness=description,
                        oracle_result=evaluator._active.result.status)
                    terminal_ms = now
                    stage = 'await-pilot-negative'
            if stage == 'await-pilot-negative':
                vehicle = evaluator._vehicle.getField('customData').getSFString()
                negative = ('WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 '
                            'oracle=grand-prix-route-v2 status=not-achieved')
                if vehicle.startswith(negative) and (len(vehicle) == len(negative) or
                         vehicle[len(negative)] == ' '):
                    if now < terminal_ms or scene_checks[0] != 1:
                        raise RuntimeError('native negative witness temporal mismatch')
                    evidence.update(phase='native-dynamic-negative',
                        native_pilot=True, no_pupil_program=True,
                        pilot_outcome=vehicle, pilot_failed_ms=now,
                        aircraft_altitude_at_failure_m=(
                            evaluator.observation.kinematics.position[2]))
                    finish()
                    return
        raise RuntimeError('real native course/altitude oracle negative incomplete')

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
                if scene_checks[0] != 1 or evaluator._scene_snapshot is not None:
                    raise RuntimeError('ordinary RESET unexpectedly rechecked geometry')
                evidence['scene_checks'] = scene_checks[0]
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
