"""Mandatory R2025a READY/refusal and real-pilot LAND/RESET; no pupil program."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile

from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.route_courses_v2 import reference_course

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'ci-artifacts/grand-prix-u-geometry/route-evaluator-native'
CLAIM = 'native-route-evaluator-ready-and-scene-revocation-no-flight'
FLIGHT_CLAIM = 'native-route-evaluator-flight-service-loss-LAND-RESET-TAKEOFF-no-pupil-program'


def _check_ready(ready):
    if type(ready) is not dict:
        raise RuntimeError('native evaluator readiness absent')
    stamps = [ready.get(k) for k in ('stable_since_ms', 'sample_time_ms', 'time_ms')]
    if (any(type(t) is not int or t < 0 or t % 8 for t in stamps) or
            not 500 <= stamps[2] - stamps[0] <= 1000 or
            not 0 <= stamps[2] - stamps[1] <= 32):
        raise RuntimeError('native evaluator continuity/refusal clock invalid')
    for key, count in (('position', 3), ('velocity', 6), ('ranges_m', 5)):
        values = ready.get(key)
        if (type(values) is not list or len(values) != count or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
            raise RuntimeError('native evaluator values unavailable')
    if (math.hypot(*ready['position'][:2]) >= .03 or not 0 <= ready['position'][2] <= .065 or
            math.hypot(*ready['velocity'][:2]) >= .12 or abs(ready['velocity'][2]) >= .15 or
            max(abs(v) for v in ready['velocity'][3:]) >= .10 or
            any(not 0 <= v <= 2.001 for v in ready['ranges_m']) or
            type(ready.get('contact_count')) is not int or not 0 <= ready['contact_count'] <= 4096):
        raise RuntimeError('native evaluator ground/range witness invalid')
    return stamps


def check_native(data):
    if (type(data) is not dict or data.get('claim') not in (CLAIM, FLIGHT_CLAIM) or
            data.get('configuration') != reference_course(5).identifier or
            data.get('webots') != 'R2025a' or data.get('timestep_ms') != 8):
        raise RuntimeError('native evaluator witness identity mismatch')
    stamps = _check_ready(data.get('ready'))
    if data['claim'] == CLAIM:
        refused, restored = data.get('refused_ms'), data.get('restored_still_refused_ms')
        mutated = data.get('mutated_ms')
        if (type(refused) is not int or type(restored) is not int or
                type(mutated) is not int or mutated != refused or
                refused != stamps[2] + 8 or restored != refused + 32):
            raise RuntimeError('native evaluator revocation clock invalid')
    else:
        acks = data.get('acks')
        if type(acks) is not dict:
            raise RuntimeError('native pilot ACK evidence absent')
        takeoff, land, reset = [acks.get(k) for k in ('takeoff_ack_ms', 'land_ack_ms', 'reset_ack_ms')]
        start, stalled, failed = [data.get(k) for k in ('start_ms', 'stalled_ms', 'failure_observed_ms')]
        if (any(type(t) is not int or t < 0 or t % 8 for t in (start, stalled, failed, takeoff, land, reset)) or
                not stamps[2] <= start < takeoff <= stalled < failed <= land < reset or
                type(data.get('airborne_z')) not in (int, float) or
                not .20 <= data['airborne_z'] <= 1.165 or data.get('fresh_epoch') is not True):
            raise RuntimeError('native flight/failure/RESET sequence invalid')
        reset_ready = data.get('reset_ready')
        if type(reset_ready) is not dict:
            raise RuntimeError('native post-RESET READY absent')
        _check_ready(reset_ready)
        if reset_ready['time_ms'] <= reset + 500:
            raise RuntimeError('native RESET did not establish a fresh window')
        second = data.get('second_takeoff')
        if type(second) is not dict:
            raise RuntimeError('native second TAKEOFF absent')
        second_start = second.get('start_ms')
        second_ack = acks.get('second_takeoff_ack_ms')
        second_observed = second.get('observed_ms')
        if (any(type(t) is not int or t < 0 or t % 8 for t in (second_start, second_ack, second_observed)) or
                not reset_ready['time_ms'] <= second_start < second_ack <= second_observed or
                type(second.get('airborne_z')) not in (int, float) or
                not .20 <= second['airborne_z'] <= 1.165):
            raise RuntimeError('native second admission/TAKEOFF sequence invalid')


def run_case(home, env, mode, index=5, *, profile_policy=None):
    if mode not in ('idle', 'flight-reset', 'classroom-startup', 'classroom-invalid',
                    'paired-benchmark', 'session-benchmark', 'flight-window',
                    'classroom-switch', 'classroom-switch-invalid',
                    'flight-course-negative', 'flight-vertical-preflight'):
        raise RuntimeError('unknown native evaluator probe mode')
    if mode in ('session-benchmark', 'flight-window'):
        if profile_policy not in ('historical-continuous-v1', 'classroom-static-v1'):
            raise RuntimeError('session benchmark policy required')
    elif profile_policy is not None:
        raise RuntimeError('unexpected native benchmark policy')
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('R2025a native evaluator witness required')
    OUT.mkdir(parents=True, exist_ok=True)
    case = Path(tempfile.mkdtemp(prefix=mode+'-invocation-', dir=OUT)).resolve()
    # Docker runs Webots as root; tempfile's 0700 would hide raw diagnostics
    # from the host's always-uploaded artifact, including failed native cases.
    case.chmod(0o755)
    # A separate native project supplies only the observation/retirement test
    # wrapper. The real pilot binary and production evaluator class are reused.
    # No production controller file, field-writer contract or pupil AST is edited.
    with tempfile.TemporaryDirectory(prefix='gp-evaluator-project-') as temporary:
        project = Path(temporary)
        (project / 'worlds').mkdir()
        controllers = project / 'controllers'
        controllers.mkdir()
        if mode not in ('flight-reset', 'flight-window', 'flight-course-negative', 'flight-vertical-preflight'):
            (controllers / 'grand_prix_route_flight').symlink_to(ROOT / 'controllers/grand_prix_route_flight', target_is_directory=True)
        else:
            flight = controllers / 'grand_prix_route_flight'
            flight.mkdir()
            shutil.copy2(ROOT / 'controllers/grand_prix_route_publisher_probe/grand_prix_route_publisher_probe',
                         flight / 'grand_prix_route_flight')
            shutil.copy2(ROOT / 'controllers/grand_prix_route_flight/runtime.ini',
                         flight / 'runtime.ini')
        (project / 'plugins').symlink_to(ROOT / 'plugins', target_is_directory=True)
        evaluator = controllers / 'grand_prix_route_evaluator'
        evaluator.mkdir()
        fixture = ROOT / 'tools/ci/fixtures/gp_route_evaluator_probe.py'
        shutil.copyfile(fixture, evaluator / 'grand_prix_route_evaluator.py')
        course = reference_course(index)
        scene = active_course_world(course).replace(
            'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', 'webots://')
        if mode == 'classroom-invalid':
            from tools.grand_prix.route_solid_v2 import corner_boxes
            box = corner_boxes(course.route)[0]
            original = box.vrml()
            displaced = original.replace(
                f'translation {box.x:.6f} ', f'translation {box.x + .10:.6f} ', 1)
            if original == displaced or scene.count(original) != 1:
                raise RuntimeError('failed to corrupt exactly one native initial L collider')
            scene = scene.replace(original, displaced, 1)
        world = project / 'worlds/route.wbt'
        world.write_text(scene)
        (case / 'world.wbt').write_text(scene)
        if mode in ('classroom-switch', 'classroom-switch-invalid'):
            # Different canonical course, *same running simulator process*.
            # Webots worldLoad() restarts the evaluator and the real C pilot.
            other = active_course_world(reference_course(0)).replace(
                'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/',
                'webots://')
            if index != 5 or other == scene:
                raise RuntimeError('native world switch must change exact course 5 to 0')
            if mode == 'classroom-switch-invalid':
                # Mutate exactly one collider in the *new* world before
                # worldLoad, not during flight. Fresh attestation must fail.
                from tools.grand_prix.route_solid_v2 import corner_boxes
                second_box = corner_boxes(reference_course(0).route)[0]
                canonical = second_box.vrml()
                displaced = canonical.replace(
                    f'translation {second_box.x:.6f} ',
                    f'translation {second_box.x + .10:.6f} ', 1)
                if canonical == displaced or other.count(canonical) != 1:
                    raise RuntimeError('failed to corrupt exactly one reloaded L collider')
                other = other.replace(canonical, displaced, 1)
            switched_world = project / 'worlds/route-switched.wbt'
            switched_world.write_text(other)
            (case / 'switched-world.wbt').write_text(other)
        record = case / 'native.json'
        log = case / 'native.log'
        environment = dict(env, WEBOTS_HOME=str(home),
            GP_ROUTE_EVALUATOR_SOURCE=str(ROOT), GP_ROUTE_EVALUATOR_OUT=str(record),
            GP_ROUTE_EVALUATOR_MODE=mode, GP_ROUTE_PILOT_ACK_OUT=str(case / 'pilot-acks.json'),
            GP_ROUTE_PILOT_NATIVE_READY_OUT=str(case / 'pilot-native-ready.txt'),
            GP_ROUTE_PILOT_COURSE_ID=course.identifier,
            GP_ROUTE_EVALUATOR_INDEX=str(index))
        if mode in ('session-benchmark', 'flight-window'):
            environment['GP_ROUTE_PROFILE_POLICY'] = profile_policy
        if mode in ('flight-course-negative', 'flight-vertical-preflight'):
            environment['GP_ROUTE_PILOT_NEGATIVE_OUT'] = str(case / 'negative-request.txt')
        if mode == 'flight-vertical-preflight':
            environment['GP_ROUTE_PILOT_NEGATIVE_ACTION'] = 'VERTICAL-up-0.8'
        if mode in ('classroom-switch', 'classroom-switch-invalid'):
            environment['GP_ROUTE_SWITCH_WORLD'] = str(switched_world)
            environment['GP_ROUTE_SWITCH_INDEX'] = '0'
        process = None
        try:
            with log.open('w') as stream:
                command = [str(home / 'webots'), '--batch', '--mode=fast', '--minimize',
                           '--stdout', '--stderr', str(world)]
                process = subprocess.Popen(command, cwd=project, env=environment,
                    stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                # Native CI 42273038753: 886 ticks reached 7088 ms in 120 s,
                # still rising (z=0.322 m; TAKEOFF target 0.4 m). The probe
                # cannot acknowledge a completed ascent before that point.
                # Bound the flight/LAND/RESET wall budget using this actual
                # R2025a pace; retain idle's 120 s, all native assertions,
                # 8-ms sampling and the 210000-ms mission deadline.
                status = process.wait(timeout=420 if mode in ('flight-reset', 'flight-window', 'flight-course-negative', 'flight-vertical-preflight') else 120)
                if status != 0:
                    raise RuntimeError('native evaluator Webots failed: ' + str(log))
        finally:
            if process is not None and process.poll() is None:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    process.wait()
        text = log.read_text(errors='replace')
        data = json.loads(record.read_text()) if record.is_file() else None
        classroom = mode.startswith('classroom-')
        expected_claim = ('native-route-pilot-vertical-preflight-refusal-v1'
                          if mode == 'flight-vertical-preflight' else
                          'native-route-evaluator-real-lateral-course-negative-v1'
                          if mode == 'flight-course-negative' else
                          'native-classroom-world-switch-invalid-rejection-v1'
                          if mode == 'classroom-switch-invalid' else
                          'native-classroom-world-switch-attestation-v1'
                          if mode == 'classroom-switch' else
                          'native-route-evaluator-real-airborne-window-v1'
                          if mode == 'flight-window' else
                          'native-route-evaluator-independent-session-cycles-v1'
                          if mode == 'session-benchmark' else
                          'native-route-evaluator-paired-ticks-v1' if mode == 'paired-benchmark'
                          else 'native-classroom-startup-attestation-v1' if classroom
                          else CLAIM if mode == 'idle' else FLIGHT_CLAIM)
        if type(data) is not dict or data.get('claim') != expected_claim:
            raise RuntimeError('native evaluator probe mode/claim mismatch')
        if mode == 'flight-vertical-preflight':
            _check_ready(data.get('ready'))
            ready = data['ready']
            start, ack, airborne = (data.get(key) for key in
                                    ('start_ms', 'takeoff_ack_ms', 'airborne_ms'))
            request, last = data.get('request_ms'), data.get('final_ms')
            low_z, high_z = data.get('min_altitude_m'), data.get('max_altitude_m')
            if (data.get('configuration') != course.identifier or
                    data.get('webots') != 'R2025a' or data.get('timestep_ms') != 8 or
                    data.get('phase') != 'native-pilot-vertical-preflight-rejected' or
                    data.get('native_pilot') is not True or
                    data.get('no_pupil_program') is not True or
                    data.get('scene_checks') != 1 or
                    data.get('oracle_phase') != 'active' or
                    data.get('oracle_result') is not None or
                    data.get('observed_steps') != 96 or
                    any(type(v) is not int or v < 0 or v % 8
                        for v in (start, ack, airborne, request, last)) or
                    not ready['time_ms'] <= start <= ack <= airborne <= request < last or
                    not 95 * 8 <= last - request <= 98 * 8 or
                    type(data.get('airborne_z')) not in (int, float) or
                    not .20 <= data['airborne_z'] < 1.165 or
                    any(type(v) not in (int, float) or not math.isfinite(v)
                        for v in (low_z, high_z)) or
                    not 0 < low_z <= high_z < ready['position'][2] + 1.15):
                raise RuntimeError('native vertical preflight/ceiling witness invalid')
            expected = (f'GP_ROUTE_PILOT_NEGATIVE_REQUEST_V1 time_ms={request} '
                        f'course={course.identifier} action=VERTICAL-up-0.8\\n')
            lines = text.splitlines()
            preflights = [line for line in lines if line.startswith(
                'GP_CEILING_PREFLIGHT_V1 command=VERTICAL ')]
            pattern = (r'GP_CEILING_PREFLIGHT_V1 command=VERTICAL '
                       r'z=(\S+) vz=(\S+) target=(\S+) top=(\S+) '
                       r'headroom=(\S+) ceiling=(\S+) code=VERTICAL_LIMIT')
            parsed = re.fullmatch(pattern, preflights[0]) if len(preflights) == 1 else None
            if (parsed is None or not (case / 'negative-request.txt').is_file() or
                    (case / 'negative-request.txt').read_text() != expected or
                    lines.count('GP_ROUTE_PILOT_REQUEST id=1 command=TAKEOFF') != 1 or
                    lines.count('GP_ROUTE_PILOT_REQUEST id=2 command=VERTICAL up 0.8') != 1 or
                    lines.count(f'GP_ROUTE_PILOT_ACK id=1 time_ms={ack}') != 1 or
                    lines.count(f'GP_U_ADMISSION attempt=1 start_ms={start}') != 1 or
                    lines.count('WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 ERR VERTICAL_LIMIT') != 1 or
                    len([line for line in lines if line.startswith(
                        'GP_ROUTE_PILOT_SEND phase=') and line.endswith(
                        'data=WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 ERR VERTICAL_LIMIT')]) != 1 or
                    any(line.startswith('GP_ROUTE_TERMINAL_V1 ') or
                        line.startswith('WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 ')
                        for line in lines)):
                raise RuntimeError('native C pilot vertical VERTICAL_LIMIT trace invalid')
            z, vz, target, top, headroom, ceiling = (float(v) for v in parsed.groups())
            if (not all(math.isfinite(v) for v in
                        (z, vz, target, top, headroom, ceiling)) or
                    not headroom > 0 or not target > top or
                    abs(ceiling - (ready['position'][2] + 1.15)) > .02 or
                    high_z >= ceiling):
                raise RuntimeError('native vertical predictive preflight guard unproven')
        elif mode == 'flight-course-negative':
            _check_ready(data.get('ready'))
            negative = ('WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 '
                        'oracle=grand-prix-route-v2 status=not-achieved')
            outcome = data.get('pilot_outcome')
            ready = data['ready']['time_ms']
            start = data.get('start_ms')
            ack = data.get('takeoff_ack_ms')
            airborne = data.get('airborne_ms')
            request = data.get('negative_request_ms')
            rejected = data.get('rejected_ms')
            failed = data.get('pilot_failed_ms')
            if (data.get('configuration') != course.identifier or
                    data.get('webots') != 'R2025a' or data.get('timestep_ms') != 8 or
                    data.get('phase') != 'native-dynamic-negative' or
                    data.get('native_pilot') is not True or
                    data.get('no_pupil_program') is not True or
                    data.get('reason') not in
                        ('course-boundary', 'envelope-contact', 'low-outside-zone') or
                    data.get('scene_checks') != 1 or
                    data.get('oracle_result') != 'not-achieved' or
                    data.get('post_negative_latched') is not True or
                    data.get('post_negative_steps') != 96 or
                    data.get('post_negative_simulated_ms') != 768 or
                    type(data.get('post_negative_last_ms')) is not int or
                    type(failed) is not int or
                    data['post_negative_last_ms'] != failed + 768 or
                    type(outcome) is not str or not outcome.startswith(negative) or
                    type(data.get('terminal_witness')) is not str or
                    not data['terminal_witness'].startswith('GP_ROUTE_TERMINAL_V1 attempt=1 ') or
                    any(type(v) is not int or v < 0 or v % 8
                        for v in (start, ack, airborne, request, rejected, failed)) or
                    not ready <= start <= ack <= airborne <= request < rejected <= failed or
                    type(data.get('airborne_z')) not in (float, int) or
                    not .20 <= data['airborne_z'] <= 1.165):
                raise RuntimeError('native lateral dynamic negative provenance invalid')
            action = 'MOVE-right-1.2'
            pilot_command = 'MOVE right 1.2'
            expected_command = (
                f'GP_ROUTE_PILOT_NEGATIVE_REQUEST_V1 time_ms={request} '
                f'course={course.identifier} action={action}\\n')
            if (not (case / 'negative-request.txt').is_file() or
                    (case / 'negative-request.txt').read_text() != expected_command or
                    text.splitlines().count('GP_ROUTE_PILOT_REQUEST id=2 command=' +
                                            pilot_command) != 1 or
                    text.splitlines().count('GP_ROUTE_PILOT_REQUEST id=1 command=TAKEOFF') != 1 or
                    text.splitlines().count(f'GP_ROUTE_PILOT_ACK id=1 time_ms={ack}') != 1 or
                    text.splitlines().count(f'GP_U_ADMISSION attempt=1 start_ms={start}') != 1 or
                    text.splitlines().count(
                        'GP_ROUTE_NEGATIVE_LATCHED_V1 attempt=1 '
                        f'checks=96 last_ms={failed + 768} reason={data["reason"]}') != 1):
                raise RuntimeError('native MOVE / TAKEOFF / 96-tick latch evidence invalid')
        elif mode == 'flight-window':
            _check_ready(data.get('ready'))
            streams = data.get('streams')
            required = ('step_wall_ns', 'tick_wall_ns', 'cycle_wall_ns',
                        'sim_time_ms', 'altitude_m')
            start = data.get('start_ms')
            ack = data.get('takeoff_ack_ms')
            airborne = data.get('first_airborne_ms')
            first = data.get('first_sim_ms')
            last = data.get('last_sim_ms')
            window = data.get('measured_window_wall_ns')
            expected_reads = 96 if profile_policy == 'historical-continuous-v1' else 0
            if (data.get('configuration') != course.identifier or
                    data.get('webots') != 'R2025a' or data.get('timestep_ms') != 8 or
                    data.get('phase') != 'active-airborne' or
                    data.get('native_pilot') is not True or
                    data.get('no_pupil_program') is not True or
                    data.get('policy') != profile_policy or
                    data.get('samples') != 96 or data.get('simulated_ms') != 768 or
                    type(start) is not int or type(ack) is not int or
                    type(airborne) is not int or type(first) is not int or
                    type(last) is not int or any(v % 8 for v in
                         (start, ack, airborne, first, last)) or
                    not data['ready']['time_ms'] <= start <= ack <= airborne < first or
                    last - first != 760 or
                    type(window) is not int or window <= 0 or
                    data.get('scene_reads_measured') != expected_reads or
                    (profile_policy == 'classroom-static-v1' and
                     data.get('scene_checks_total') != 1) or
                    (profile_policy == 'historical-continuous-v1' and
                     (type(data.get('scene_checks_total')) is not int or
                      data['scene_checks_total'] < 97)) or
                    type(streams) is not dict or set(streams) != set(required)):
                raise RuntimeError('native airborne A/B provenance invalid')
            for key in required:
                values = streams[key]
                if type(values) is not list or len(values) != 96:
                    raise RuntimeError('native airborne observation series absent')
            for key in required[:3]:
                if any(type(v) is not int or v <= 0 for v in streams[key]):
                    raise RuntimeError('native airborne cycle series invalid')
            if streams['sim_time_ms'] != list(range(first, last + 8, 8)):
                raise RuntimeError('native airborne sample clock not contiguous')
            if (any(type(z) not in (int, float) or not math.isfinite(z) or
                    not .20 <= z <= 1.165 for z in streams['altitude_m']) or
                    type(data.get('first_airborne_z')) not in (int, float) or
                    not .20 <= data['first_airborne_z'] <= 1.165):
                raise RuntimeError('native airborne physics outside sample bounds')
            if any(step + tick != cycle for step, tick, cycle in zip(
                    streams['step_wall_ns'], streams['tick_wall_ns'],
                    streams['cycle_wall_ns'])):
                raise RuntimeError('native airborne step/tick/cycle mismatch')
            if window < sum(streams['cycle_wall_ns']):
                raise RuntimeError('native airborne wall window undercounts cycles')
            if (text.splitlines().count('GP_ROUTE_PILOT_REQUEST id=1 command=TAKEOFF') != 1 or
                    text.splitlines().count(f'GP_ROUTE_PILOT_ACK id=1 time_ms={ack}') != 1 or
                    text.splitlines().count(f'GP_U_ADMISSION attempt=1 start_ms={start}') != 1):
                raise RuntimeError('native airborne TAKEOFF broker evidence absent')
        elif mode == 'session-benchmark':
            expected_metrics = ('step_wall_ns', 'tick_wall_ns', 'cycle_wall_ns')
            series = data.get('durations_ns')
            first, last = data.get('first_sim_ms'), data.get('last_sim_ms')
            ready = data.get('ready_sim_ms')
            window_ns = data.get('measured_window_wall_ns')
            expected_reads = 96 if profile_policy == 'historical-continuous-v1' else 0
            if (data.get('configuration') != course.identifier or
                    data.get('webots') != 'R2025a' or
                    data.get('timestep_ms') != 8 or data.get('phase') != 'idle-ready' or
                    data.get('mode') != 'batch-fast-minimized' or
                    data.get('policy') != profile_policy or
                    data.get('samples') != 96 or data.get('simulated_ms') != 768 or
                    type(ready) is not int or type(first) is not int or
                    type(last) is not int or first - ready < 128 or
                    last - first != 760 or
                    type(series) is not dict or set(series) != set(expected_metrics) or
                    type(window_ns) is not int or window_ns <= 0 or
                    data.get('scene_reads_measured') != expected_reads or
                    (profile_policy == 'classroom-static-v1' and
                     data.get('scene_checks_total') != 1) or
                    (profile_policy == 'historical-continuous-v1' and
                     (type(data.get('scene_checks_total')) is not int or
                      data['scene_checks_total'] < 97))):
                raise RuntimeError('native independent-session provenance invalid')
            for metric in expected_metrics:
                values = series[metric]
                if (type(values) is not list or len(values) != 96 or
                        any(type(v) is not int or v <= 0 for v in values)):
                    raise RuntimeError('native independent-session cycles missing')
            if any(step + tick != cycle for step, tick, cycle in zip(
                    series['step_wall_ns'], series['tick_wall_ns'],
                    series['cycle_wall_ns'])):
                raise RuntimeError('native step+tick cycle decomposition invalid')
            if window_ns < sum(series['cycle_wall_ns']):
                raise RuntimeError('native benchmark wall window undercounts cycles')
        elif mode == 'paired-benchmark':
            names = ('historical-continuous-v1', 'classroom-static-v1')
            series = data.get('tick_wall_ns')
            reads = data.get('scene_reads_measured')
            first, last = data.get('first_sim_ms'), data.get('last_sim_ms')
            if (data.get('configuration') != course.identifier or
                    data.get('webots') != 'R2025a' or data.get('timestep_ms') != 8 or
                    data.get('phase') != 'idle-ready' or
                    data.get('paired_same_step') is not True or
                    data.get('order') != 'alternating-AB-BA' or
                    data.get('samples') != 96 or
                    type(first) is not int or type(last) is not int or
                    last - first != 95 * 8 or
                    type(series) is not dict or set(series) != set(names) or
                    reads != {names[0]: 96, names[1]: 0}):
                raise RuntimeError('paired native benchmark provenance invalid')
            for name in names:
                values = series[name]
                if (type(values) is not list or len(values) != 96 or
                        any(type(v) is not int or v <= 0 for v in values)):
                    raise RuntimeError('paired native tick samples missing')
            ratio = data.get('wall_tick_ratio_historical_over_classroom')
            if (type(ratio) not in (int, float) or not math.isfinite(ratio) or
                    abs(ratio - round(sum(series[names[0]]) / sum(series[names[1]]), 6)) > 1e-6):
                raise RuntimeError('paired native tick ratio invalid')
        elif mode in ('classroom-switch', 'classroom-switch-invalid'):
            first, second = data.get('first'), data.get('second')
            if (data.get('webots') != 'R2025a' or data.get('timestep_ms') != 8 or
                    data.get('new_world_loaded') is not True or
                    data.get('fresh_controller') is not True or
                    type(first) is not dict or type(second) is not dict):
                raise RuntimeError('native two-world switch evidence absent')
            if (first.get('configuration') != course.identifier or
                    first.get('scene_checks') != 1 or
                    type(first.get('native_evaluator_id')) is not int or
                    first['native_evaluator_id'] <= 0 or
                    type(first.get('controller_pid')) is not int or
                    first['controller_pid'] <= 0 or
                    first.get('time_ms') != first.get('ready', {}).get('time_ms')):
                raise RuntimeError('native first evaluator READY provenance invalid')
            _check_ready(first.get('ready'))
            if (second.get('configuration') != reference_course(0).identifier or
                    second.get('scene_checks') != 1 or
                    type(second.get('native_evaluator_id')) is not int or
                    second['native_evaluator_id'] <= 0 or
                    type(second.get('controller_pid')) is not int or
                    second['controller_pid'] <= 0 or
                    first['controller_pid'] == second['controller_pid']):
                raise RuntimeError('native restarted evaluator identity invalid')
            if mode == 'classroom-switch':
                if second.get('time_ms') != second.get('ready', {}).get('time_ms'):
                    raise RuntimeError('native reloaded world READY timestamp invalid')
                _check_ready(second.get('ready'))
            else:
                stamp = second.get('time_ms')
                if (second.get('rejected_before_ready') is not True or
                        'ready' in second or
                        type(stamp) is not int or stamp < 0 or stamp % 8 or
                        not second.get('error', '').startswith(
                            'native collider world pose mismatch: GP_V2_L_')):
                    raise RuntimeError('noncanonical reloaded world not refused before READY')
            # The first controller printed its source record before worldLoad,
            # and the new controller printed the two-world result (or refusal).
            prior = 'GP_ROUTE_SWITCH_BEFORE ' + json.dumps(first, allow_nan=False, sort_keys=True)
            if ([line for line in text.splitlines()
                 if line.startswith('GP_ROUTE_SWITCH_BEFORE ')] != [prior]):
                raise RuntimeError('native first-world stdout mirror missing')
            if (not (case / 'switch-stage.json').is_file() or
                    json.loads((case / 'switch-stage.json').read_text()) != first):
                raise RuntimeError('native two-world durable handoff disagrees')
        elif classroom:
            if (data.get('configuration') != course.identifier or
                    data.get('webots') != 'R2025a' or
                    data.get('timestep_ms') != 8 or
                    data.get('scene_checks') != 1):
                raise RuntimeError('classroom initial attestation evidence absent')
            if mode == 'classroom-invalid':
                if (data.get('rejected_before_ready') is not True or
                        not data.get('error', '').startswith('native collider world pose mismatch: GP_V2_L_') or
                        'ready' in data):
                    raise RuntimeError('noncanonical startup not rejected before READY')
            elif (data.get('ready_before_mission') is not True or
                  type(data.get('new_evaluator_native_id')) is not int or
                  data['new_evaluator_native_id'] <= 0):
                raise RuntimeError('fresh evaluator initial READY missing')
            if mode == 'classroom-startup':
                _check_ready(data.get('ready'))
        else:
            check_native(data)
            if mode == 'flight-reset' and data.get('scene_checks') != 1:
                raise RuntimeError('RESET re-inspected static scene')
        if mode == 'flight-reset':
            for attempt, suffix, key in ((1, '', 'ready'), (2, '.second', 'reset_ready')):
                marker = case / ('pilot-native-ready.txt' + suffix)
                expected_marker = (f'GP_ROUTE_PROBE_READY_V1 attempt={attempt} course='
                                   + data['configuration'] + ' time_ms='
                                   + str(data[key]['time_ms']) + '\n')
                if not marker.is_file() or marker.read_text() != expected_marker:
                    raise RuntimeError('native pilot READY stimulus provenance missing')
        expected = 'GP_ROUTE_EVALUATOR_NATIVE ' + json.dumps(data, allow_nan=False, sort_keys=True)
        if ([line for line in text.splitlines() if line.startswith('GP_ROUTE_EVALUATOR_NATIVE ')] != [expected] or
                'Traceback (most recent call last)' in text or
                any(line.startswith('ERROR:') for line in text.splitlines())):
            raise RuntimeError('native evaluator JSON/stdout/exit evidence disagrees')
        if mode == 'flight-reset':
            commands = re.findall(r'^GP_U_DEADLINE time_ms=(\d+) command=LAND interrupted_id=-?\d+$', text, re.M)
            admissions = re.findall(r'^GP_U_ADMISSION attempt=(\d+) start_ms=(\d+)$', text, re.M)
            expected_admissions = [('1', str(data['start_ms'])), ('2', str(data['second_takeoff']['start_ms']))]
            if (len(commands) != 1 or not 0 < int(commands[0]) - data['stalled_ms'] <= 64 or
                    admissions != expected_admissions or
                    text.splitlines().count('GP_ROUTE_SAFETY_LAND evaluator-unavailable') != 1 or
                    text.splitlines().count('WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1') != 1 or
                    text.count('GP_ROUTE_PILOT_REQUEST id=1 command=TAKEOFF') != 1 or
                    text.count('GP_ROUTE_PILOT_REQUEST id=2 command=RESET') != 1 or
                    text.count('GP_ROUTE_PILOT_REQUEST id=3 command=TAKEOFF') != 1):
                raise RuntimeError('native TAKEOFF, independent LAND or RESET command evidence absent')
            for identifier, key in ((1, 'takeoff_ack_ms'), (2147483646, 'land_ack_ms'),
                                    (2, 'reset_ack_ms'), (3, 'second_takeoff_ack_ms')):
                expected_ack = f'GP_ROUTE_PILOT_ACK id={identifier} time_ms={data["acks"][key]}'
                if text.splitlines().count(expected_ack) != 1:
                    raise RuntimeError('native pilot ACK trace/file evidence disagrees')
            if 'WEBEEBLOCKS_RUNTIME_V2 TRACE RESET ' not in text:
                raise RuntimeError('native reset pose/stability trace absent')
        (case / 'sha256.json').write_text(json.dumps({
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in case.iterdir() if p.is_file()}, indent=2) + '\n')
        print('PASS bounded native route evaluator '+mode+'; no pupil program/mission/GUI qualification', flush=True)
        return data, case


def run_native(home, env):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'pilot-probe-build.log').open('w') as log:
        subprocess.run(['make', '-C', str(ROOT / 'controllers/grand_prix_route_publisher_probe')],
                       env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
    identities = {}
    for name in ('runtime_u.c', 'file_broker_u.cpp'):
        production = (ROOT / 'controllers/grand_prix_route_flight/build' / name).read_bytes()
        probe = (ROOT / 'controllers/grand_prix_route_publisher_probe/build' / name).read_bytes()
        if production != probe:
            raise RuntimeError('native pilot probe drifted from production source: '+name)
        identities[name] = hashlib.sha256(production).hexdigest()
    (OUT / 'production-source-sha256.json').write_text(json.dumps(identities, indent=2)+'\n')
    run_case(home, env, 'idle')
    # The production flight and C pilot are reused; RESET must preserve the
    # attested static world without repeating expensive scene traversal.
    run_case(home, env, 'flight-reset')
    # Twelve separate real R2025a worlds/evaluators: the initial complete
    # readback must precede READY for *every* canonical configuration.
    # These are startup/admission witnesses, NOT twelve flown missions.
    startups = []
    for index in range(12):
        data, case = run_case(home, env, 'classroom-startup', index)
        startups.append(dict(
            index=index, configuration=data['configuration'],
            world_sha256=hashlib.sha256((case / 'world.wbt').read_bytes()).hexdigest(),
            native_json_sha256=hashlib.sha256((case / 'native.json').read_bytes()).hexdigest(),
            scene_checks=data['scene_checks'],
            ready_time_ms=data['ready']['time_ms'],
            native_evaluator_id=data['new_evaluator_native_id'],
            case_directory=case.name))
    expected = {reference_course(index).identifier for index in range(12)}
    if (len(startups) != 12 or
            {row['configuration'] for row in startups} != expected or
            len({row['world_sha256'] for row in startups}) != 12 or
            len({row['native_json_sha256'] for row in startups}) != 12 or
            any(row['index'] != index or row['scene_checks'] != 1
                for index, row in enumerate(startups))):
        raise RuntimeError('native twelve-world initial attestation matrix invalid')
    (OUT / 'classroom-startup-summary.json').write_text(
        json.dumps(dict(claim='native-classroom-static-twelve-startups-not-flights-v1',
                        webots='R2025a', timestep_ms=8,
                        configurations=12, startup_attestations=startups),
                   sort_keys=True, indent=2) + '\n')
    # Unlike independent startup probes, this *same Webots process* invokes
    # native Supervisor.worldLoad() to switch 5 -> 0. Actual GUI interactions
    # and student workspace transition remain outside this native contract.
    run_case(home, env, 'classroom-switch', 5)
    # New evaluator must also reject a *corrupted* second world before READY.
    run_case(home, env, 'classroom-switch-invalid', 5)
    # Corrupt the .wbt *before* Webots loads it; reject before first READY.
    run_case(home, env, 'classroom-invalid', 5)
    # Real same-process native idle READY cost; no rendered FPS claim.
    run_case(home, env, 'paired-benchmark', 5)

    # Separate product-like native processes for each arm. Three matched
    # A/B pairs share the same CI job/host/pinned engine/world and vary only
    # the evaluator scene policy; alternate AB/BA/AB launch order.
    policies = ('historical-continuous-v1', 'classroom-static-v1')
    orders = (policies, policies[::-1], policies)
    sessions = []
    for pair_number, pair_order in enumerate(orders, start=1):
        for position, policy in enumerate(pair_order, start=1):
            data, case = run_case(home, env, 'session-benchmark', 5,
                                  profile_policy=policy)
            series = data['durations_ns']
            sessions.append(dict(
                pair=pair_number, position=position, policy=policy,
                case_directory=case.name,
                native_json_sha256=hashlib.sha256(
                    (case / 'native.json').read_bytes()).hexdigest(),
                world_sha256=hashlib.sha256(
                    (case / 'world.wbt').read_bytes()).hexdigest(),
                ready_sim_ms=data['ready_sim_ms'],
                first_sim_ms=data['first_sim_ms'], last_sim_ms=data['last_sim_ms'],
                samples=data['samples'], simulated_ms=data['simulated_ms'],
                measured_window_wall_ns=data['measured_window_wall_ns'],
                step_total_ns=sum(series['step_wall_ns']),
                tick_total_ns=sum(series['tick_wall_ns']),
                cycle_total_ns=sum(series['cycle_wall_ns']),
                scene_reads_measured=data['scene_reads_measured']))
    if (len(sessions) != 6 or
            len({session['world_sha256'] for session in sessions}) != 1 or
            any(session['pair'] != pair or session['policy'] != policy
                for pair, pair_order in enumerate(orders, 1)
                for session, policy in zip(sessions[(pair-1)*2:pair*2], pair_order))):
        raise RuntimeError('native A/B separate-session matching failed')
    totals = {policy: {key: sum(s[key] for s in sessions if s['policy'] == policy)
                       for key in ('step_total_ns', 'tick_total_ns', 'cycle_total_ns',
                                   'measured_window_wall_ns')}
              for policy in policies}
    if any(value <= 0 for values in totals.values() for value in values.values()):
        raise RuntimeError('native A/B totals invalid')
    summary = dict(
        claim='native-route-evaluator-separate-session-ab-v1',
        webots='R2025a', course=reference_course(5).identifier,
        mode='batch-fast-minimized', host=__import__('platform').node(),
        webots_image=env.get('WEBEEBLOCKS_GP_WEBOTS_IMAGE'),
        order='AB-BA-AB', matched_pairs=3, sessions=sessions,
        total_ns_by_policy=totals,
        ratios_historical_over_classroom={
            key: round(totals[policies[0]][key] / totals[policies[1]][key], 6)
            for key in totals[policies[0]]})
    (OUT / 'session-benchmark-summary.json').write_text(
        json.dumps(summary, sort_keys=True, indent=2) + '\n')
    print('PASS 3 matched native R2025a A/B session pairs; no GUI/FPS/Windows claim',
          flush=True)

    # Three independent R2025a physical counterexamples: sample the
    # canonical one-, two- and three-H configuration groups (0, 5, 11).
    # These are real lateral MOVE commands on the test-wrapped production
    # pilot, NOT Supervisor pose changes or three completed pupil missions.
    negative_cases = []
    for index in (0, 5, 11):
        data, case = run_case(home, env, 'flight-course-negative', index)
        negative_cases.append(dict(
            index=index, configuration=data['configuration'],
            reason=data['reason'],
            ready_ms=data['ready']['time_ms'],
            request_ms=data['negative_request_ms'],
            rejected_ms=data['rejected_ms'],
            pilot_failed_ms=data['pilot_failed_ms'],
            post_negative_last_ms=data['post_negative_last_ms'],
            post_negative_steps=data['post_negative_steps'],
            post_negative_latched=data['post_negative_latched'],
            scene_checks=data['scene_checks'],
            world_sha256=hashlib.sha256((case / 'world.wbt').read_bytes()).hexdigest(),
            native_json_sha256=hashlib.sha256(
                (case / 'native.json').read_bytes()).hexdigest(),
            case_directory=case.name))
    if (len(negative_cases) != 3 or
            {r['index'] for r in negative_cases} != {0, 5, 11} or
            {r['configuration'] for r in negative_cases} !=
            {reference_course(i).identifier for i in (0, 5, 11)} or
            len({r['world_sha256'] for r in negative_cases}) != 3 or
            len({r['native_json_sha256'] for r in negative_cases}) != 3 or
            any(r['scene_checks'] != 1 or
                r['post_negative_latched'] is not True or
                r['post_negative_steps'] != 96 or
                r['post_negative_last_ms'] != r['pilot_failed_ms'] + 768 or
                not r['ready_ms'] <= r['request_ms'] <
                r['rejected_ms'] <= r['pilot_failed_ms']
                for r in negative_cases)):
        raise RuntimeError('native three-course dynamic negative evidence invalid')
    (OUT / 'flight-course-negative-summary.json').write_text(
        json.dumps(dict(
            claim='native-grand-prix-three-course-real-pilot-negatives-not-missions-v1',
            webots='R2025a', timestep_ms=8,
            indices=[0, 5, 11], negative_witnesses=negative_cases),
            sort_keys=True, indent=2) + '\n')

    # Hypothesis refuted in native R2025a: VERTICAL up 0.8 is rejected
    # by the real route-only predictive ceiling guard before mission altitude
    # could be exceeded. Verify the genuine C VERTICAL_LIMIT response, intact
    # dynamic oracle and 96 subsequent safe native 8-ms steps instead of
    # bypassing the safety preflight to manufacture an altitude violation.
    vertical, vertical_case = run_case(home, env, 'flight-vertical-preflight', 5)
    if (vertical.get('phase') != 'native-pilot-vertical-preflight-rejected' or
            vertical.get('scene_checks') != 1 or
            vertical.get('configuration') != reference_course(5).identifier):
        raise RuntimeError('native pilot vertical ceiling preflight unproven')
    (OUT / 'flight-vertical-preflight-summary.json').write_text(
        json.dumps(dict(
            claim='native-route-pilot-vertical-command-rejected-before-oracle-v1',
            index=5, configuration=vertical['configuration'],
            action='VERTICAL up 0.8', error='VERTICAL_LIMIT',
            observed_steps=vertical['observed_steps'],
            min_altitude_m=vertical['min_altitude_m'],
            max_altitude_m=vertical['max_altitude_m'],
            scene_checks=vertical['scene_checks'],
            native_json_sha256=hashlib.sha256(
                (vertical_case / 'native.json').read_bytes()).hexdigest(),
            world_sha256=hashlib.sha256(
                (vertical_case / 'world.wbt').read_bytes()).hexdigest(),
            case_directory=vertical_case.name),
            sort_keys=True, indent=2) + '\n')

    # Three matched independently launched airborne A/B pairs. Alternate
    # policy order AB-BA-AB to expose run-order and host scheduling effects.
    # Both arms run the same native C pilot, geometry, 8-ms physics and exact
    # 96-sample simulated trajectory, but neither has a pupil program or GUI.
    flight_orders = (policies, policies[::-1], policies)
    flight = []
    altitude_series = {}
    cycle_series = {policy: [] for policy in policies}
    for pair_number, pair_order in enumerate(flight_orders, start=1):
        for position, policy in enumerate(pair_order, start=1):
            data, case = run_case(home, env, 'flight-window', 5,
                                  profile_policy=policy)
            durations = data['streams']
            altitude_series[(pair_number, policy)] = durations['altitude_m']
            cycle_series[policy].extend(durations['cycle_wall_ns'])
            flight.append(dict(
                pair=pair_number, position=position,
                policy=policy, case_directory=case.name,
                world_sha256=hashlib.sha256(
                    (case / 'world.wbt').read_bytes()).hexdigest(),
                native_json_sha256=hashlib.sha256(
                    (case / 'native.json').read_bytes()).hexdigest(),
                ready_time_ms=data['ready']['time_ms'],
                samples=96, first_sim_ms=data['first_sim_ms'],
                last_sim_ms=data['last_sim_ms'], start_ms=data['start_ms'],
                takeoff_ack_ms=data['takeoff_ack_ms'],
                first_airborne_z=data['first_airborne_z'],
                first_sample_z=durations['altitude_m'][0],
                last_sample_z=durations['altitude_m'][-1],
                measured_window_wall_ns=data['measured_window_wall_ns'],
                step_total_ns=sum(durations['step_wall_ns']),
                tick_total_ns=sum(durations['tick_wall_ns']),
                cycle_total_ns=sum(durations['cycle_wall_ns']),
                scene_reads_measured=data['scene_reads_measured']))
    if (len(flight) != 6 or
            len({session['world_sha256'] for session in flight}) != 1 or
            any(session['pair'] != pair or session['position'] != position or
                session['policy'] != policy
                for pair, order in enumerate(flight_orders, 1)
                for position, (session, policy) in enumerate(
                    zip(flight[(pair - 1) * 2:pair * 2], order), 1))):
        raise RuntimeError('native airborne three-pair order or world mismatch')

    matched_fields = ('ready_time_ms', 'start_ms', 'takeoff_ack_ms',
                      'first_sim_ms', 'last_sim_ms', 'first_airborne_z',
                      'first_sample_z', 'last_sample_z')
    pair_ratios = []
    for pair_number, order in enumerate(flight_orders, 1):
        matched = flight[(pair_number - 1) * 2:pair_number * 2]
        a = next(x for x in matched if x['policy'] == policies[0])
        b = next(x for x in matched if x['policy'] == policies[1])
        if (any(a[key] != b[key] for key in matched_fields) or
                altitude_series[(pair_number, policies[0])] !=
                altitude_series[(pair_number, policies[1])]):
            raise RuntimeError('native A/B flight policies changed physical trajectory')
        pair_ratios.append(dict(
            pair=pair_number, order=''.join('A' if x == policies[0] else 'B'
                                             for x in order),
            cycle_historical_over_classroom=round(
                a['cycle_total_ns'] / b['cycle_total_ns'], 6),
            speed_historical=round(768 * 1_000_000 /
                                   a['measured_window_wall_ns'], 6),
            speed_classroom=round(768 * 1_000_000 /
                                  b['measured_window_wall_ns'], 6)))

    totals = {policy: {key: sum(x[key] for x in flight if x['policy'] == policy)
                       for key in ('step_total_ns', 'tick_total_ns',
                                   'cycle_total_ns', 'measured_window_wall_ns')}
              for policy in policies}
    if (any(value <= 0 for values in totals.values() for value in values.values()) or
            any(len(cycle_series[policy]) != 3 * 96 for policy in policies)):
        raise RuntimeError('native airborne three-pair durations incomplete')
    p99_cycles_ms = {policy: round(
        sorted(cycle_series[policy])[math.ceil(.99 * len(cycle_series[policy])) - 1] /
        1_000_000, 6) for policy in policies}
    summary = dict(
        claim='native-route-evaluator-airborne-three-matched-ab-pairs-v2',
        course=reference_course(5).identifier, webots='R2025a',
        webots_image=env.get('WEBEEBLOCKS_GP_WEBOTS_IMAGE'),
        host=__import__('platform').node(), mode='batch-fast-minimized',
        order='AB-BA-AB', matched_pairs=3,
        policies=policies, samples_per_session=96, sessions=flight,
        pair_ratios=pair_ratios, total_ns_by_policy=totals,
        p99_cycle_ms_by_policy=p99_cycles_ms,
        simulated_ms_per_policy=3 * 96 * 8,
        simulated_over_wall_by_policy={
            policy: round(3 * 768 * 1_000_000 /
                          totals[policy]['measured_window_wall_ns'], 6)
            for policy in policies},
        ratios_historical_over_classroom={
            key: round(totals[policies[0]][key] /
                       totals[policies[1]][key], 6)
            for key in totals[policies[0]]})
    (OUT / 'flight-window-summary.json').write_text(
        json.dumps(summary, sort_keys=True, indent=2) + '\n')
    print('PASS 3 matched real R2025a airborne AB-BA-AB pairs; no GUI/FPS/Windows/full mission claim',
          flush=True)
