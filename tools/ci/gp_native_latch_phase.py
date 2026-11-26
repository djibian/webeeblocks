"""Isolated native phase experiment, calibrated on the same world and pilot.

Only fault timing and wall pacing are instrumented. A missed phase is not a
PASS. The ordinary A7 rebound verifier and product checks remain untouched.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

from tools.ci.a7_native_rebound import (
    FORCED_ID, ReboundUnproven, archived_control_period, replace_once,
)

PRODUCT_SHA = '7c4f50ff5d3892b49cb6ca43807e1d6614cf2d291f66f6f011132a33b24eb504'
OFFSETS = (-8, 0, 8)
CASES = ('stop', 'liveness', 'deadline')


def instrument_phase(source):
    # Observe the accepted LAND and independent transfer. Atomic marker writes
    # are scheduling aids only; the trace verifier does not trust them as ODE.
    helper = r'''static void gp_phase_mark(const char *name, long long stamp) {
  const char *folder = getenv("WEBEEBLOCKS_A7_V5_EVENTS");
  if (!folder) return;
  char path[4096], temp[4096];
  int a = snprintf(path, sizeof(path), "%s/%s", folder, name);
  int b = snprintf(temp, sizeof(temp), "%s/%s.tmp", folder, name);
  if (a < 0 || b < 0 || a >= (int)sizeof(path) || b >= (int)sizeof(temp)) return;
  FILE *f = fopen(temp, "w");
  if (!f) return;
  fprintf(f, "%lld\n", stamp);
  if (fclose(f) == 0) rename(temp, path);
}

'''
    source = replace_once(source, 'static int land_has_ground_contact(',
                          helper + 'static int land_has_ground_contact(')
    source = replace_once(source, '        command = CMD_LAND;\n',
                          '        command = CMD_LAND;\n'
                          '        gp_phase_mark("phase-land", (long long)llround(now*1000.0));\n')
    anchor = '      printf("GP_U_DEADLINE'
    source = replace_once(source, anchor,
                          '      gp_phase_mark("phase-force", (long long)llround(now*1000.0));\n' + anchor)
    anchor = '    if (getenv("WBB_GP_PRODUCT_TRACE") &&'
    return replace_once(source, anchor,
                        '    if (airborne || command == CMD_LAND)\n'
                        '      gp_phase_mark("phase-tick", (long long)llround(now*1000.0));\n' + anchor)


class PhaseSchedule:
    def __init__(self, case, folder):
        self.case, self.folder = case, folder
        self.offset = int(os.environ['WEBEEBLOCKS_LATCH_OFFSET'])
        self.delay = int(os.environ['WEBEEBLOCKS_LATCH_DELAY'])
        if self.case != 'calibration' and (self.offset not in OFFSETS or
                                           self.delay <= 0 or self.delay % 8):
            raise ValueError('invalid calibrated phase')
        self.target = None
        self.sent = False

    def stamp(self, name):
        path = self.folder / name
        return int(path.read_text()) if path.exists() else None

    def wait(self, name, predicate):
        end = time.monotonic() + 2
        while time.monotonic() < end:
            stamp = self.stamp(name)
            if stamp is not None and predicate(stamp):
                return
            time.sleep(.002)
        raise ReboundUnproven('native phase handshake missed: ' + name)

    def send(self, name, now):
        # Prior tick's ordinary parser has completed; only wall time is held.
        self.wait('phase-tick', lambda stamp: stamp == now)
        temp = self.folder / (name + '.tmp')
        temp.write_text(str(now))
        temp.replace(self.folder / name)

    def tick(self, now, evaluator, alive, record):
        if self.case == 'calibration' or self.sent:
            return
        if self.case == 'deadline':
            if evaluator._start_ms is None:
                return
            # Transfer at the actual admission+210000 cap. Schedule LAND
            # earlier/later, never alter time or the guard.
            self.target = evaluator._start_ms + 210000 - self.delay - self.offset - 8
            if now < self.target:
                return
            if now != self.target or not (self.folder / 'phase-land-wanted').exists():
                raise ReboundUnproven('nominal approach missed deadline LAND stimulus')
            self.send('phase-land-send', now)
            self.wait('phase-land-sent', lambda stamp: stamp == now)
            record('PHASE_LAND_EMITTED', now)
        else:
            land = self.stamp('phase-land')
            if land is None:
                return
            self.target = land + self.delay + self.offset - 8
            if now < self.target:
                return
            if now != self.target:
                raise ReboundUnproven('calibrated fault emission missed')
            if self.case == 'stop':
                self.send('stop-request', now)
                sent = self.folder / 'stop-sent'
                end = time.monotonic() + 2
                while not sent.exists() and time.monotonic() < end:
                    time.sleep(.002)
                if not sent.exists():
                    raise ReboundUnproven('genuine WWI STOP not sent')
                record('STOP_EMITTED', now, sender=json.loads(sent.read_text()))
            else:
                alive.cut_at = now
        self.sent = True

    def pace(self, now):
        return self.target is not None and self.target-32 <= now <= self.target+4200


def one(values, name):
    if len(values) != 1:
        raise ReboundUnproven(f'{name}: expected one, found {len(values)}')
    return values[0]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_phase(case, offset, journal, contacts, wwi, course):
    """Only observed effective fault phase can qualify; never infer it."""
    require(case in ('calibration', *CASES), 'invalid case')
    require(case == 'calibration' or offset in OFFSETS, 'invalid requested phase')
    require(re.findall(r'^GP_ROUTE_CONTROL_TIMING (.*)$', journal, re.M) ==
            ['physics_ms=8 control_ms=8 range_ms=32'], 'native timing missing')
    rows = [json.loads(line) for line in contacts.splitlines()]
    def event(name):
        return one([row for row in rows if row['event'] == name], name)
    def match(pattern, name):
        return one(re.findall(pattern, journal, re.M), name)
    observations = [row for row in rows if row['event'] == 'ODE']
    ode = {row['ms']: row for row in observations}
    if (not observations or len(ode) != len(observations) or
            list(ode) != list(range(observations[0]['ms'], observations[-1]['ms']+1, 8))):
        raise ReboundUnproven('missing continuous ODE samples')
    land, nominal, attempt, epoch = match(
        r'^A7_V5_RX (\d+) (\d+) LAND (\d+) ([0-9a-f]{32})$', 'nominal LAND')
    land, nominal, attempt = map(int, (land, nominal, attempt))
    start_attempt, start = map(int, match(r'^GP_U_ADMISSION attempt=(\d+) start_ms=(\d+)$',
                                         'admission'))
    require(start_attempt == attempt and start <= land, 'admission identity mismatch')
    touch = event('FIRST_CONTACT')['ms']
    require(land < touch and ode[touch]['floor'], 'invalid first ODE contact')
    require(all(not ode[ms]['floor'] for ms in range(land, touch, 8)),
            'earlier floor contact during LAND')
    cycles = {}
    for line in re.findall(r'^A7_V5_CYCLE (.+)$', journal, re.M):
        fields = line.split()
        require(len(fields) == 14, 'malformed pilot sample')
        ms, *state = map(int, fields[:10])
        require(ms not in cycles, 'duplicate pilot sample')
        cycles[ms] = (*state, tuple(map(float, fields[10:])))
    ack = round(float(match(r'^GP_U_LAND_GROUND_READY t=(\d+\.\d+) window=', 'LAND ACK'))*1000)
    require(land in cycles and cycles[land][1] == nominal, 'nominal LAND not accepted')
    require(touch in cycles and cycles[touch][5] == 1, 'first ODE contact not sampled by pilot')
    require(touch < ack, 'ACK before physical contact')
    require(touch-8 in cycles and cycles[touch-8][2] == 0, 'premature motor latch before floor contact')
    # Safety first: even an off-phase intervention must not mask a motor pulse.
    land_mode = cycles[land][0]
    for ms in range(touch, ack+1, 8):
        require(ms in cycles, f'missing pilot cycle {ms}')
        command, request, latch, _, _, _, _, _, _, motors = cycles[ms]
        require(command == land_mode and latch == 1 and motors == (0.,)*4,
                f'motor/latch violation at {ms}: {cycles[ms]}')
        require(ode[ms]['epoch'] == epoch and ode[ms]['attempt'] == attempt,
                f'changed native incarnation at {ms}')
    _, _, _, _, ground, floor, fresh, pose, vertical, _ = cycles[ack]
    require(ground and floor and fresh >= touch and pose >= 0 and vertical >= 0 and
            max(fresh, pose, vertical) <= ack-500 and fresh in cycles,
            'missing fresh 500-ms pilot stability')
    require(all(cycles[ms][5] and cycles[ms][6] == fresh for ms in range(fresh, ack+1, 8)),
            'contact window not continuous')
    require(all(ode[ms]['stable'] and ode[ms]['floor'] and
                all(point['point'][2] <= .015 for point in ode[ms]['contacts'])
                for ms in range(ack-504, ack+1, 8)), 'missing final 504-ms ODE stability')
    transfers = re.findall(r'^GP_U_DEADLINE time_ms=(\d+) command=LAND interrupted_id=(-?\d+)$',
                           journal, re.M)
    if case == 'calibration':
        require(ack-start < 210000, 'nominal calibration exceeds mission cap')
        require(not transfers and all(cycles[ms][1] == nominal for ms in range(touch, ack+1, 8)),
                'calibration not nominal')
        require(f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {nominal} OK\n' in wwi,
                'nominal ACK absent')
        require('"status":"achieved"' in wwi, 'nominal oracle not achieved')
        return dict(first_contact_ms=touch, land_ms=land, delay_ms=touch-land, ack_ms=ack)
    if not transfers:
        raise ReboundUnproven('independent transfer absent')
    require(len(transfers) == 1, 'duplicate independent transfers')
    transfer, interrupted = map(int, transfers[0])
    if case != 'deadline':
        require(0 < transfer-start < 210000, 'early safety transfer crossed mission cap')
    require(land < transfer < ack and min(fresh, vertical) >= transfer,
            'independent owner lacks fresh stability')
    require(transfer in cycles and cycles[transfer][6] ==
            (transfer if cycles[transfer][5] else -1000),
            'independent LAND retained earlier contact window')
    stops = re.findall(r'^A7_V5_RX (\d+) (\d+) STOP (\d+) ([0-9a-f]{32})$', journal, re.M)
    if case == 'stop':
        applied, stop_id, interrupted_id = map(int, match(
            r'^A7_V5_STOP_APPLIED (\d+) (\d+) (\d+)$', 'nominal STOP application'))
        first = event('STOP_EMITTED')
        require((int(first['sender']['id']), int(first['sender']['observed_ms'])) ==
                (stop_id, first['ms']) and first['ms'] <= applied, 'STOP emission identity/order')
        require(len(stops) == 2 and tuple(map(int, stops[0][:3])) ==
                (applied, stop_id, attempt) and stops[0][3] == epoch,
                'STOP reception mismatch')
        require(transfer == applied+8 and interrupted == -1 and interrupted_id == nominal,
                'STOP did not transfer on next native tick')
        require(f'A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST {stop_id} STOP\n' in wwi and
                f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {stop_id} OK\n' in wwi,
                'STOP WWI request/ACK absent')
        error = 'USER_STOPPED'
    else:
        require(len(stops) == 1 and interrupted == nominal, 'unexpected STOP or interrupted ID')
        applied = transfer
        if case == 'liveness':
            revocation = event('ALIVE_REVOKED')
            gms, ga, ge = match(r'^A7_V5_LIVENESS_GUARD (\d+) (\d+) ([0-9a-f]{32})$',
                                'liveness guard')
            require((int(gms), int(ga), ge) == (applied, attempt, epoch), 'wrong liveness guard')
            previous = re.fullmatch(
                rf'GP_ROUTE_ALIVE_V1 attempt={attempt} config={re.escape(course)} epoch={epoch} time_ms=(\d+)',
                revocation['previous'])
            require(previous is not None and 0 < revocation['ms']-int(previous[1]) <= 32,
                    'no preceding valid ALIVE')
            a, e, last, raw = match(
                rf'^A7_V5_ALIVE {applied} (\d+) ([0-9a-f]{{32}}) (\d+) (-\d+) <empty>$',
                'withdrawn native ALIVE')
            require((int(a), e, raw) == (attempt, epoch, '-1'), 'ALIVE withdrawal identity')
            match(rf'^A7_V5_ALIVE {applied-8} {attempt} {epoch} \d+ {last} '
                  rf'GP_ROUTE_ALIVE_V1 attempt={attempt} config={re.escape(course)} epoch={epoch} time_ms={last}$',
                  'last consumed ALIVE')
            require(0 <= applied-8-int(last) <= 32 and revocation['ms'] <= applied,
                    'ALIVE causal order')
        else:
            event('PHASE_LAND_EMITTED')
            require(transfer-start == 210000 and '"reason":"time-limit"' in wwi and
                    not re.search(r'^A7_V5_LIVENESS_GUARD ', journal, re.M),
                    'real exact deadline not established')
        error = 'TIME_LIMIT'
    require(f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {nominal} ERR {error}\n' in wwi,
            'nominal interruption absent')
    late_ms, late_id, late_attempt = map(int, stops[-1][:3])
    require(transfer <= late_ms < ack and late_attempt == attempt and stops[-1][3] == epoch,
            'late STOP not received under independent ownership')
    require(f'A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST {late_id} STOP\n' in wwi and
            f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {late_id} ERR TIME_LIMIT\n' in wwi,
            'late STOP not refused')
    for ms in range(min(touch, transfer), ack+1, 8):
        require(ms in cycles, f'missing owner cycle {ms}')
        expected = FORCED_ID if ms >= transfer else -1 if case == 'stop' and ms >= applied else nominal
        require(cycles[ms][0:2] == (land_mode, expected), f'LAND ownership changed at {ms}')
    require(wwi.count(f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {FORCED_ID} OK\n') == 1 and
            f'RESPONSE {FORCED_ID} ERR' not in journal, 'independent ACK not unique')
    resets = re.findall(r'^A7_V5_RX (\d+) (\d+) RESET (\d+) ([0-9a-f]{32})$', journal, re.M)
    require(len(resets) == 2, 'missing two real RESET requests')
    before, after = resets
    require(late_ms <= int(before[0]) < ack < int(after[0]) and
            all((int(row[2]), row[3]) == (attempt, epoch) for row in resets), 'RESET identity/order')
    refused = re.search(rf'^A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {before[1]} ERR '
                        r'(?:LANDING_UNCONFIRMED|TIME_LIMIT)$', wwi, re.M)
    accepted = re.search(rf'^A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {after[1]} OK$', wwi, re.M)
    landed = re.search(rf'^A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {FORCED_ID} OK$', wwi, re.M)
    require(refused and accepted and landed and refused.start() < landed.start() < accepted.start(),
            'RESET did not straddle ACK')
    require(all(f'A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST {row[1]} RESET\n' in wwi
                for row in resets), 'RESET WWI request absent')
    require(any(row['attempt'] == attempt+1 and row['epoch'] and row['epoch'] != epoch and
                row['phase'] == 'ready' and row['ms'] > int(after[0]) for row in observations),
            'new epoch not ready')
    # Do not hide safety failures when the requested phase was missed.
    observed = applied-touch
    if observed != offset:
        raise ReboundUnproven(f'effective phase {observed:+d} ms, requested {offset:+d} ms')
    sep = event('FIRST_SEPARATION')['ms']
    return_contact = next((ms for ms in range(sep+8, ack+1, 8) if ode[ms]['contacts']), None)
    if (not touch < sep < ack or return_contact is None or ode[sep]['velocity'][2] <= 0 or
            any(not ode[ms]['floor'] for ms in range(touch, sep, 8)) or
            any(ode[ms]['contacts'] for ms in range(sep, return_contact, 8))):
        raise ReboundUnproven('real first ODE rebound not established')
    return dict(first_contact_ms=touch, land_ms=land, applied_ms=applied, phase_ms=observed,
                transfer_ms=transfer, separation_ms=sep, return_ms=return_contact,
                late_stop_ms=late_ms, ack_ms=ack, fresh_stability_ms=ack-fresh)


def finish(out, case, probe_error, env):
    result = dict(case=case, requested_ms=int(env['WEBEEBLOCKS_LATCH_OFFSET']))
    try:
        if not (out / 'identity.json').is_file():
            raise ReboundUnproven('native build/provenance absent')
        identity = json.loads((out / 'identity.json').read_text())
        require(identity['git_head'] == env['TARGET_SHA'] and not identity['tracked_status'] and
                identity['case'] == case and identity['phase'] ==
                {key: env['WEBEEBLOCKS_LATCH_' + key] for key in ('PHASE', 'OFFSET', 'DELAY', 'COURSE')},
                'phase provenance mismatch')
        require(identity['webots'] == 'R2025a' and
                all(identity['actions'][key] == env.get(key) for key in
                    ('TARGET_SHA', 'GITHUB_RUN_ID', 'GITHUB_WORKFLOW_SHA', 'GITHUB_RUN_ATTEMPT')),
                'run or engine identity mismatch')
        require(identity['sha256']['runtime_product.c'] == PRODUCT_SHA, 'unexpected product C')
        for name, digest in identity['sha256'].items():
            require(hashlib.sha256((out / name).read_bytes()).hexdigest() == digest,
                    'archive hash mismatch: ' + name)
        journal, contacts, wwi = ((out / name).read_text() for name in
                                  ('webots.log', 'contacts.jsonl', 'wwi.log'))
        require(archived_control_period(out, journal) == 8, 'wrong control period')
        if re.search(r'^ERROR:|^Traceback \(most recent call last\)', journal, re.M):
            raise ReboundUnproven('native startup/observation error')
        result.update(verify_phase(case, result['requested_ms'], journal, contacts, wwi,
                                   env['WEBEEBLOCKS_LATCH_COURSE']))
        if probe_error is not None:
            raise RuntimeError(f'WWI probe failed: {probe_error}')
        result['result'] = 'PASS'
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        result.update(result='UNPROVEN' if isinstance(exc, ReboundUnproven) else 'FAIL', reason=str(exc))
        if probe_error is not None:
            result['probe_error'] = str(probe_error)
    (out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print('LATCH_PHASE', out.name, result, flush=True)
    if result['result'] != 'PASS':
        raise RuntimeError(result['reason'])


def run():
    from tools.ci.run_grand_prix_progression_native import OUT, run_native
    activity = int(os.environ['ACTIVITY'])
    variant = {6: 4, 7: 5, 8: 1}[activity]
    project = OUT / 'route-a8-native/pupil-project.wbb' if activity == 8 else None
    home = Path(os.environ['WEBOTS_HOME'])
    summary = []
    delay = 0
    for case, offset in [('calibration', 0)] + [(c, p) for c in CASES for p in OFFSETS]:
        out = OUT / f'route-a{activity}-v{variant}-native-phase-{case}-{offset}'
        if out.exists():
            raise RuntimeError('phase directory already exists: ' + str(out))
        env = dict(os.environ, WEBEEBLOCKS_LATCH_PHASE='1',
                   WEBEEBLOCKS_LATCH_OFFSET=str(offset), WEBEEBLOCKS_LATCH_DELAY=str(delay))
        try:
            run_native(home, env, activity, variant, pupil_project=project, rebound=case)
            row = json.loads((out / 'result.json').read_text())
            require(row['result'] == 'PASS', 'unexpected native result')
        except (OSError, RuntimeError, ValueError) as exc:
            row = (json.loads((out / 'result.json').read_text()) if (out / 'result.json').exists()
                   else dict(result='UNPROVEN', reason=str(exc)))
        summary.append(dict(row, path=out.name))
        (OUT / 'latch-phase-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        if case == 'calibration':
            if row['result'] != 'PASS':
                raise RuntimeError('no native calibration; refusing blind phase trials')
            delay = row['delay_ms']
    if any(row['result'] != 'PASS' for row in summary):
        raise RuntimeError('one or more requested native phases remain blocking')


if __name__ == '__main__':
    run()
