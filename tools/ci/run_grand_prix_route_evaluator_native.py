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
        if (type(refused) is not int or type(restored) is not int or
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


def run_case(home, env, mode):
    if mode not in ('idle', 'flight-reset'):
        raise RuntimeError('unknown native evaluator probe mode')
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
        if mode == 'idle':
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
        scene = active_course_world(reference_course(5)).replace(
            'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', 'webots://')
        world = project / 'worlds/route.wbt'
        world.write_text(scene)
        (case / 'world.wbt').write_text(scene)
        record = case / 'native.json'
        log = case / 'native.log'
        environment = dict(env, WEBOTS_HOME=str(home),
            GP_ROUTE_EVALUATOR_SOURCE=str(ROOT), GP_ROUTE_EVALUATOR_OUT=str(record),
            GP_ROUTE_EVALUATOR_MODE=mode, GP_ROUTE_PILOT_ACK_OUT=str(case / 'pilot-acks.json'),
            GP_ROUTE_PILOT_NATIVE_READY_OUT=str(case / 'pilot-native-ready.txt'),
            GP_ROUTE_PILOT_COURSE_ID=reference_course(5).identifier)
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
                status = process.wait(timeout=120 if mode == 'idle' else 420)
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
        if type(data) is dict and data.get('claim') != (CLAIM if mode == 'idle' else FLIGHT_CLAIM):
            raise RuntimeError('native evaluator probe mode/claim mismatch')
        check_native(data)
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
    run_case(home, env, 'flight-reset')
