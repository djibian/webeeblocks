"""Draft-only native V5 experiment. No instrumentation enters the product build."""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from tools.grand_prix.evaluator_native_contacts_v2 import read_contacts
from tools.grand_prix.evaluator_native_kinematics_v2 import _now_ms
from tools.grand_prix.evaluator_publisher_v2 import NativeRouteEvaluator
from tools.grand_prix.prepare_u_runtime import prepare

ROOT = Path(__file__).resolve().parents[2]
COURSE = 'gp-progression-v1-a7-v5'
FORCED_ID = 2147483646
CASES = ('stop', 'liveness')


def replace_once(source, anchor, replacement):
    if source.count(anchor) != 1:
        raise RuntimeError(f'V5 instrumentation anchor changed: {anchor}')
    return source.replace(anchor, replacement, 1)


def instrument_pilot(source):
    # Read the actual commanded speeds, including the ACK cycle that exits
    # before the normal cycle tail. The extra code writes only trace data.
    sample = r'''  printf("A7_V5_CYCLE %lld %d %d %d %d %d %d %lld %lld %lld %.17g %.17g %.17g %.17g\n",
         (long long)llround(now * 1000.0), command, active_id, land_touchdown,
         airborne, gp_ground_sample, land_has_ground_contact(z, origin_z),
         (long long)llround(gp_land_contact_since * 1000.0),
         (long long)llround(gp_ground_since * 1000.0),
         (long long)llround(stable_since * 1000.0),
         wb_motor_get_velocity(m1), wb_motor_get_velocity(m2),
         wb_motor_get_velocity(m3), wb_motor_get_velocity(m4));
  fflush(stdout);
'''
    # The generic Runtime has multiple ACK sites. Observe the specific route
    # LAND confirmation site, after stop_motors and before sending its ACK.
    anchor = '          trace_land();'
    source = replace_once(source, anchor, sample + anchor)
    anchor = '    if (getenv("WBB_GP_PRODUCT_TRACE") &&'
    source = replace_once(source, anchor, sample + r'''    if (command == CMD_LAND &&
        land_touchdown && gp_land_contact_since == now &&
        active_id > 0 && active_id != 2147483646 &&
        wb_motor_get_velocity(m1) == 0 && wb_motor_get_velocity(m2) == 0 &&
        wb_motor_get_velocity(m3) == 0 && wb_motor_get_velocity(m4) == 0) {
      const char *marker = getenv("WEBEEBLOCKS_A7_V5_LATCH");
      FILE *notice = marker ? fopen(marker, "wx") : NULL;
      if (notice) {
        fprintf(notice, "%lld %d\n", (long long)llround(now * 1000.0), active_id);
        fclose(notice);
      }
    }
''' + anchor)
    anchor = '        if (gp_route_a7_attempt() && command == CMD_LAND && land_touchdown) {'
    return replace_once(source, anchor, anchor + r'''
          printf("A7_V5_STOP_APPLIED %lld %d %d\n",
                 (long long)llround(now * 1000.0), request.id, active_id);
          fflush(stdout);''')


def instrument_deadline(source):
    # Count WWI delivery before the native filter can reject RESET. Read the
    # evaluator's actual field at the liveness guard, retaining native identity.
    anchor = '  if(routePauseMessage(message))return 0;'
    source = replace_once(source, anchor, r'''  int witness_id;
  char witness_cmd[32];
  if (message && std::sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s",
                            &witness_id, witness_cmd) == 2 &&
      (!std::strcmp(witness_cmd, "LAND") || !std::strcmp(witness_cmd, "STOP") ||
       !std::strcmp(witness_cmd, "RESET"))) {
    std::printf("A7_V5_RX %lld %d %s %llu %s\n",
                std::llround(wb_robot_get_time() * 1000.0), witness_id,
                witness_cmd, routeAttempt, routeEpoch.c_str());
    std::fflush(stdout);
  }
''' + anchor)
    anchor = '  if(!fresh)return false;'
    source = replace_once(source, anchor, r'''  if (!std::strcmp(kind, "ALIVE")) {
    std::printf("A7_V5_ALIVE %lld %llu %s %lld %lld %s\n",
                now, routeAttempt, routeEpoch.c_str(), routeAlive, observed,
                raw && *raw ? raw : "<empty>");
    std::fflush(stdout);
  }
''' + anchor)
    anchor = '    std::fprintf(stderr,"GP_ROUTE_SAFETY_LAND evaluator-unavailable\\n");'
    return replace_once(source, anchor, anchor + r'''
    std::printf("A7_V5_LIVENESS_GUARD %lld %llu %s\n",
                observed, routeAttempt, routeEpoch.c_str());
    std::fflush(stdout);''')


def provenance(out, paths, home, env):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

    if env.get('GITHUB_ACTIONS') == 'true':
        git_head = env['WEBEEBLOCKS_GP_GIT_HEAD']
        git_tree = env['WEBEEBLOCKS_GP_GIT_TREE']
        git_parents = env['WEBEEBLOCKS_GP_GIT_PARENTS']
        tracked_status = env['WEBEEBLOCKS_GP_GIT_STATUS']
    else:
        git_head = git('rev-parse', 'HEAD')
        git_tree = git('rev-parse', 'HEAD^{tree}')
        git_parents = git('show', '-s', '--format=%P', 'HEAD')
        tracked_status = git('status', '--porcelain', '--untracked-files=no')
    record = {
        'git_head': git_head,
        'git_tree': git_tree,
        'git_parents': git_parents.split(),
        'tracked_status': tracked_status,
        'webots': (home / 'resources/version.txt').read_text().strip(),
        'rebound_height': env.get('WEBEEBLOCKS_A7_V5_HEIGHT'),
        'actions': {name: env.get(name) for name in (
            'GITHUB_REPOSITORY', 'GITHUB_WORKFLOW_SHA', 'GITHUB_REF', 'GITHUB_RUN_ID',
            'GITHUB_RUN_ATTEMPT', 'TARGET_SHA', 'WEBEEBLOCKS_GP_WEBOTS_IMAGE')},
        'sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest()
                   for name, path in paths.items()},
    }
    if env.get('GITHUB_ACTIONS') == 'true' and (
            record['tracked_status'] or record['git_head'] != env.get('TARGET_SHA') or
            not record['git_parents']):
        raise RuntimeError('V5 experiment is not bound to the clean target checkout')
    (out / 'identity.json').write_text(json.dumps(record, indent=2) + '\n')


def build_project(folder, out, home, env):
    """Build the real route pilot with observational additions in a private project."""
    controllers = folder / 'controllers'
    controllers.mkdir()
    for name in ('crazyflie_square', 'crazyflie_runtime_v2', 'grand_prix_u_flight'):
        (controllers / name).symlink_to(ROOT / 'controllers' / name)
    (folder / 'tools').symlink_to(ROOT / 'tools')
    (folder / 'plugins').symlink_to(ROOT / 'plugins')
    flight = controllers / 'grand_prix_route_flight'
    flight.mkdir()
    production_flight = ROOT / 'controllers/grand_prix_route_flight'
    for name in ('Makefile', 'runtime.ini'):
        shutil.copyfile(production_flight / name, flight / name)
    profile = 'gp_route_takeoff_profile.h'
    (flight / profile).symlink_to(production_flight / profile)
    build = flight / 'build'
    prepare(build, legacy_worlds=False, route_observations=True)
    runtime = build / 'runtime_u.c'
    runtime.write_text(instrument_pilot(runtime.read_text()))
    deadline = build / 'rebound_deadline.cpp'
    source = ROOT / 'controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp'
    deadline.write_text(instrument_deadline(source.read_text()))
    evaluator = controllers / 'grand_prix_route_evaluator'
    evaluator.mkdir()
    entry = evaluator / 'grand_prix_route_evaluator.py'
    entry.write_text('import sys\n'
                     f'sys.path.insert(0, {str(ROOT)!r})\n'
                     'from controller import Supervisor\n'
                     'from tools.ci.a7_native_rebound import serve_rebound\n'
                     'serve_rebound(Supervisor(), sys.argv[1])\n')
    paths = {path.name: path for path in (runtime, deadline, entry, build / 'file_broker_u.cpp')}
    for name, path in paths.items():
        shutil.copyfile(path, out / name)
    with (out / 'build.log').open('w') as log:
        subprocess.run(['make', '-C', str(flight), 'GP_DEADLINE_SOURCE=build/rebound_deadline.cpp'],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    for name, path in paths.items():
        if path.read_bytes() != (out / name).read_bytes():
            raise RuntimeError(f'{name} changed while compiling the V5 pilot')
    binary = flight / flight.name
    if not os.access(binary, os.X_OK):
        raise RuntimeError('missing compiled internal pilot')
    return {**paths, binary.name: binary}


class AliveDisconnection:
    """Gate only the actual evaluator-to-pilot ALIVE publication on the native field."""

    def __init__(self, field, log):
        self.field = field
        self.log = log
        self.cut_at = None
        self.last_published = None

    def setSFString(self, value):
        if value.startswith('GP_ROUTE_ALIVE_V1 '):
            if self.cut_at is not None:
                if self.last_published is not None:
                    self.field.setSFString('')
                    self.log('ALIVE_REVOKED', self.cut_at, previous=self.last_published,
                             withheld=value)
                    self.last_published = None
                return
            self.last_published = value
        self.field.setSFString(value)


def serve_rebound(robot, identifier):
    case = os.environ['WEBEEBLOCKS_A7_V5_CASE']
    if identifier != COURSE or case not in CASES or robot.getBasicTimeStep() != 8:
        raise RuntimeError('expected the canonical native A7/V5 world')
    events = Path(os.environ['WEBEEBLOCKS_A7_V5_EVENTS'])
    latch = Path(os.environ['WEBEEBLOCKS_A7_V5_LATCH'])
    evaluator = NativeRouteEvaluator(robot, identifier, scene_policy='classroom-static-v1')
    with (events / 'contacts.jsonl').open('w', buffering=1) as stream:
        def record(event, ms, **data):
            print(json.dumps(dict(event=event, ms=ms, **data), allow_nan=False), file=stream)

        alive = AliveDisconnection(evaluator._reply, record)
        evaluator._reply = alive
        airborne = False
        touch = None
        first_loss = None
        while robot.step(8) != -1:
            now = _now_ms(robot.getTime())
            vehicle = robot.getFromId(evaluator._vehicle_id)
            if vehicle is None or robot.getSelf().getId() != evaluator._self_id:
                raise RuntimeError('V5 observation source replaced')
            position, velocity = vehicle.getPosition(), vehicle.getVelocity()
            orientation = vehicle.getOrientation()
            contacts = read_contacts(vehicle, now).points
            floor = any(point.point[2] <= evaluator._origin_z for point in contacts)
            stable = (floor and abs(position[2] - evaluator._origin_z) < .05 and
                      math.hypot(*velocity[:2]) < .12 and abs(velocity[2]) < .15 and
                      max(map(abs, velocity[3:])) < .10 and
                      abs(math.atan2(orientation[7], orientation[8])) < math.radians(2) and
                      abs(math.asin(max(-1., min(1., -orientation[6])))) < math.radians(2))
            airborne |= position[2] > .80
            if airborne and floor and touch is None:
                touch = now
                record('FIRST_CONTACT', now)
            if touch is not None and not contacts and first_loss is None:
                first_loss = now
                locked = latch.read_text().split() if latch.exists() else []
                record('FIRST_SEPARATION', now, latch=locked)
                if len(locked) == 2 and touch <= int(locked[0]) < now and velocity[2] > 0:
                    if case == 'stop':
                        # Keep this observed 8-ms tick open while Node sends the
                        # genuine WWI STOP. No simulated time or physics changes.
                        request = events / 'stop-request.tmp'
                        request.write_text(str(now))
                        request.replace(events / 'stop-request')
                        sent = events / 'stop-sent'
                        limit = time.monotonic() + 2
                        while not sent.exists() and time.monotonic() < limit:
                            time.sleep(.002)
                        if sent.exists():
                            record('STOP_EMITTED', now, sender=json.loads(sent.read_text()),
                                   wall_monotonic_ns=str(time.monotonic_ns()))
                    else:
                        alive.cut_at = now
            evaluator.tick()
            context = evaluator._context
            record('ODE', now, position=position, velocity=velocity, orientation=orientation,
                   contacts=[{'point': point.point, 'node': point.node_id} for point in contacts],
                   floor=floor, stable=stable, phase=evaluator.phase,
                   attempt=context.attempt if context else None,
                   epoch=context.epoch if context else None,
                   evaluator_ground_since=evaluator._ground_since,
                   controller_sample=evaluator._model.getSFString())
            # Give Webots' streaming thread time to deliver WWI before the
            # next 32-ms cycle, including the pre-ACK RESET. Only wall time
            # is paced, from the first observed contact for 1.2 simulated s.
            if touch is not None and now - touch < 1200:
                time.sleep(.04)


class ReboundUnproven(RuntimeError):
    """The requested intervention did not occur inside the measured window."""


def archived_control_period(out, journal):
    """Bind the cycle requirement to archived compiled input and startup."""
    identity = json.loads((out / 'identity.json').read_text())
    source = (out / 'runtime_u.c').read_bytes()
    if hashlib.sha256(source).hexdigest() != identity['sha256']['runtime_u.c']:
        raise RuntimeError('archived pilot source digest mismatch')
    steps = re.findall(rb'^  const int step = (8|32);', source, re.M)
    if len(steps) != 1:
        raise RuntimeError('unknown compiled pilot control period')
    period = int(steps[0])
    markers = re.findall(r'^GP_ROUTE_CONTROL_TIMING (.*)$', journal, re.M)
    if (period == 8 or markers) and markers != [
            f'physics_ms=8 control_ms={period} range_ms=32']:
        raise RuntimeError('native startup timing absent or inconsistent')
    return period


def verify(case, journal, contacts, wwi, *, control_ms=32):
    """Correlate native stops, motor commands and ODE samples without extrapolation."""
    if type(control_ms) is not int or control_ms not in (8, 32):
        raise ValueError('unsupported pilot period')
    timing = re.findall(r'^GP_ROUTE_CONTROL_TIMING (.*)$', journal, re.M)
    if (control_ms == 8 or timing) and timing != [
            f'physics_ms=8 control_ms={control_ms} range_ms=32']:
        raise RuntimeError('native pilot period does not match verifier')
    records = [json.loads(line) for line in contacts.splitlines()]
    observations = [row for row in records if row['event'] == 'ODE']
    ode = {row['ms']: row for row in observations}
    if not observations or list(ode) != list(range(observations[0]['ms'], observations[-1]['ms'] + 1, 8)):
        raise ReboundUnproven('ODE samples do not cover continuous 8-ms physics')
    if len(ode) != len(observations):
        raise RuntimeError('duplicated ODE observation')

    def one(items, label, error=RuntimeError):
        if len(items) != 1:
            raise error(f'{label}: expected one witness, found {len(items)}')
        return items[0]

    def event(name):
        return one([row for row in records if row['event'] == name], name, ReboundUnproven)

    def pattern(regex, label, error=RuntimeError):
        return one(re.findall(regex, journal, re.M), label, error)

    land_ms, nominal, attempt, epoch = pattern(
        r'^A7_V5_RX (\d+) (\d+) LAND (\d+) ([0-9a-f]{32})$', 'nominal LAND',
        ReboundUnproven)
    land_ms, nominal, attempt = map(int, (land_ms, nominal, attempt))
    touch = event('FIRST_CONTACT')['ms']
    separation = event('FIRST_SEPARATION')['ms']
    contact_return = next((ms for ms, row in ode.items() if ms > separation and row['contacts']), None)
    if (contact_return is None or not land_ms < touch < separation or
            any(ms not in ode for ms in range(touch, contact_return + 1, 8)) or
            not ode[touch]['floor'] or any(not ode[ms]['floor'] for ms in range(touch, separation, 8)) or
            any(ode[ms]['contacts'] for ms in range(separation, contact_return, 8)) or
            ode[separation]['velocity'][2] <= 0):
        raise ReboundUnproven('first continuous ODE separation is not established')

    cycles = {}
    for line in re.findall(r'^A7_V5_CYCLE (.+)$', journal, re.M):
        fields = line.split()
        ms, command, request, locked, airborne, ground, floor, contact, pose, vertical = map(int, fields[:10])
        if ms in cycles or len(fields) != 14:
            raise RuntimeError('malformed/duplicate pilot sample')
        cycles[ms] = (command, request, locked, airborne, ground, floor, contact,
                      pose, vertical, tuple(map(float, fields[10:])))
    latch = next((ms for ms, row in cycles.items() if row[1:3] == (nominal, 1)), None)
    if latch is None or not touch <= latch < separation or not cycles[latch][5]:
        raise ReboundUnproven('nominal motor latch not established before separation')

    if control_ms == 8 and latch != touch:
        raise RuntimeError('8-ms pilot failed to latch on first physical contact')

    if case == 'stop':
        emission = event('STOP_EMITTED')
        sent_id = int(emission['sender']['id'])
        rx, request, stop_attempt, stop_epoch = pattern(
            r'^A7_V5_RX (\d+) (\d+) STOP (\d+) ([0-9a-f]{32})$', 'WWI STOP reception',
            ReboundUnproven)
        applied, applied_id, interrupted = pattern(
            r'^A7_V5_STOP_APPLIED (\d+) (\d+) (\d+)$', 'native STOP during locked LAND',
            ReboundUnproven)
        received, applied = int(rx), int(applied)
        if (emission['ms'] != separation or emission['sender']['observed_ms'] != separation or
                not separation <= received <= applied < contact_return):
            raise ReboundUnproven('STOP emission/reception/application escaped the first ODE rebound')
        if (int(request), int(applied_id), int(interrupted), int(stop_attempt), stop_epoch) != (
                sent_id, sent_id, nominal, attempt, epoch):
            raise RuntimeError('STOP, nominal LAND and native incarnation do not correlate')
        nominal_error = 'USER_STOPPED'
        cause = {'detected_ms': separation, 'emitted_ms': emission['ms'],
                 'received_ms': received, 'applied_ms': applied}
        if (f'WEBEEBLOCKS_RUNTIME_V2 RESPONSE {sent_id} OK\n' not in journal or
                f'A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST {sent_id} STOP\n' not in wwi or
                f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {sent_id} OK\n' not in wwi):
            raise RuntimeError('native STOP request/ACK did not cross WWI')
    else:
        if re.search(r'^A7_V5_RX \d+ \d+ STOP ', journal, re.M):
            raise RuntimeError('liveness experiment received STOP')
        revocation = event('ALIVE_REVOKED')
        applied, guard_attempt, guard_epoch = pattern(
            r'^A7_V5_LIVENESS_GUARD (\d+) (\d+) ([0-9a-f]{32})$',
            'native evaluator-unavailable guard', ReboundUnproven)
        applied = int(applied)
        if revocation['ms'] != separation or not separation <= applied < contact_return:
            raise ReboundUnproven('ALIVE withdrawal/native guard escaped the first ODE rebound')
        previous = re.fullmatch(
            rf'GP_ROUTE_ALIVE_V1 attempt={attempt} config={COURSE} epoch={epoch} time_ms=(\d+)',
            revocation['previous'])
        received_attempt, received_epoch, last_alive, raw_stamp = pattern(
            rf'^A7_V5_ALIVE {applied} (\d+) ([0-9a-f]{{32}}) (\d+) (-\d+) <empty>$',
            'native read of withdrawn ALIVE', ReboundUnproven)
        pattern(
            rf'^A7_V5_ALIVE {applied - control_ms} {attempt} {epoch} \d+ {last_alive} '
            rf'GP_ROUTE_ALIVE_V1 attempt={attempt} config={COURSE} epoch={epoch} time_ms={last_alive}$',
            'last valid pilot ALIVE')
        if (not previous or not 0 < separation - int(previous[1]) <= 32 or
                not 0 <= applied - control_ms - int(last_alive) <= 32 or raw_stamp != '-1' or
                (int(received_attempt), received_epoch) != (attempt, epoch) or
                (int(guard_attempt), guard_epoch) != (attempt, epoch)):
            raise RuntimeError('ALIVE guard lacks healthy-to-withdrawn evidence in the same incarnation')
        nominal_error = 'TIME_LIMIT'
        cause = {'detected_ms': separation, 'emitted_ms': revocation['ms'],
                 'received_ms': applied, 'applied_ms': applied}

    transfer, interrupted = pattern(
        r'^GP_U_DEADLINE time_ms=(\d+) command=LAND interrupted_id=(-?\d+)$',
        'independent LAND transfer', ReboundUnproven)
    transfer, interrupted = int(transfer), int(interrupted)
    expected_transfer = applied + control_ms if case == 'stop' else applied
    if transfer != expected_transfer or transfer >= contact_return:
        raise ReboundUnproven('LAND transfer did not occur during the first ODE rebound')
    if interrupted != (-1 if case == 'stop' else nominal):
        raise RuntimeError('unexpected interrupted request at native LAND transfer')

    ack_stamp = pattern(r'^GP_U_LAND_GROUND_READY t=(\d+\.\d+) window=', 'landing confirmation')
    ack = round(float(ack_stamp) * 1000)
    if f'RESPONSE {nominal} ERR {nominal_error}' not in journal:
        raise RuntimeError('nominal LAND did not report the expected interruption')
    if f'RESPONSE {FORCED_ID} OK' not in journal or f'RESPONSE {FORCED_ID} ERR' in journal:
        raise RuntimeError('independent LAND did not ACK safely')
    land_command = cycles[latch][0]
    if not latch < transfer < ack or (ack - latch) % control_ms:
        raise RuntimeError(f'pilot clock did not retain its {control_ms}-ms phase during LAND')
    for ms in range(latch, ack + 1, control_ms):
        if ms not in cycles:
            raise RuntimeError(f'missing {control_ms}-ms motor sample at {ms}')
        command, request, locked, _, _, _, _, _, _, motors = cycles[ms]
        expected_id = FORCED_ID if ms >= transfer else -1 if case == 'stop' and ms >= applied else nominal
        if command != land_command or request != expected_id or locked != 1 or motors != (0.,) * 4:
            raise RuntimeError(f'LAND ownership, motor cutoff or latch failed at {ms}: {cycles[ms]}')

    if cycles[transfer][6] != -1000:
        raise RuntimeError('independent LAND retained a pre-transfer contact window')
    _, _, _, _, ground, floor, fresh_contact, pose, vertical, _ = cycles[ack]
    if (not ground or not floor or min(fresh_contact, vertical) < transfer or
            max(fresh_contact, pose, vertical) > ack - 500 or pose < 0 or
            fresh_contact not in cycles or
            any(not cycles[ms][5] or cycles[ms][6] != fresh_contact
                for ms in range(fresh_contact, ack + 1, control_ms)) or
            any(ms not in ode or not ode[ms]['stable'] or any(
                    point['point'][2] > .015 for point in ode[ms]['contacts'])
                for ms in range(ack - 504, ack + 1, 8)) or
            any(ms not in ode or ode[ms]['epoch'] != epoch or ode[ms]['attempt'] != attempt
                for ms in range(touch, ack + 1, 8))):
        raise RuntimeError('fresh controller stability and 8-ms continuous Floor contact do not precede ACK')

    resets = re.findall(r'^A7_V5_RX (\d+) (\d+) RESET (\d+) ([0-9a-f]{32})$', journal, re.M)
    if len(resets) != 2:
        raise RuntimeError('expected two real WWI RESET requests')
    before, after = resets
    if (not applied <= int(before[0]) < ack < int(after[0]) or
            any((int(row[2]), row[3]) != (attempt, epoch) for row in resets)):
        raise RuntimeError('RESET requests do not straddle LAND ACK in its native incarnation')
    refusal = re.search(rf'^A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {before[1]} ERR '
                        r'(?:LANDING_UNCONFIRMED|TIME_LIMIT)$', wwi, re.M)
    landed = re.search(rf'^A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {FORCED_ID} OK$', wwi, re.M)
    reset = re.search(rf'^A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {after[1]} OK$', wwi, re.M)
    ready = next((row for row in observations if row['attempt'] == attempt + 1 and
                  row['epoch'] and row['epoch'] != epoch and row['phase'] == 'ready' and
                  row['ms'] > int(after[0])), None)
    if not (refusal and landed and reset and ready and refusal.start() < landed.start() < reset.start()):
        raise RuntimeError('RESET refusal/ACK and fresh native READY are not established')
    for row in (before, after):
        if f'A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST {row[1]} RESET\n' not in wwi:
            raise RuntimeError('RESET was not sent over WWI')
    return {**cause, 'control_ms': control_ms, 'attempt': attempt, 'epoch': epoch, 'first_contact_ms': touch,
            'latch_ms': latch, 'contact_return_ms': contact_return, 'transfer_ms': transfer,
            'fresh_stability_ms': ack - fresh_contact, 'ack_ms': ack,
            'reset_refused_ms': int(before[0]), 'reset_accepted_request_ms': int(after[0]),
            'reset_ready_ms': ready['ms'], 'reset_epoch': ready['epoch']}


def finish(out, case, probe_error):
    result = {'case': case}
    try:
        if not (out / 'webots.log').is_file():
            raise ReboundUnproven('native controller build or launch did not reach Webots')
        journal = (out / 'webots.log').read_text(errors='replace')
        if re.search(r'^ERROR:|^Traceback \(most recent call last\)', journal, re.M):
            raise ReboundUnproven('native Webots startup/observation error')
        if not (out / 'contacts.jsonl').is_file():
            raise ReboundUnproven('native 8-ms evaluator trace missing')
        result.update(verify(case, journal, (out / 'contacts.jsonl').read_text(),
                             (out / 'wwi.log').read_text(),
                             control_ms=archived_control_period(out, journal)))
        if probe_error is not None:
            raise RuntimeError(f'WWI probe terminated unsuccessfully: {probe_error}')
        result['result'] = 'PASS'
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        result['result'] = 'UNPROVEN' if isinstance(error, ReboundUnproven) else 'FAIL'
        result['reason'] = str(error)
        if probe_error is not None:
            result['probe_error'] = str(probe_error)
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"A7/V5 {case} {result['result']}: {out / 'result.json'}", flush=True)
    if result['result'] != 'PASS':
        raise RuntimeError(result['reason'])
