"""Parser-only checks: no physical evidence is inferred from fixtures."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.ci.gp_native_latch_phase import (
    CASES, OFFSETS, ReboundUnproven, instrument_phase, verify_phase,
)
from tools.ci.a7_native_rebound import instrument_pilot
from tools.ci.test_a7_native_rebound import fixture_8ms
from tools.grand_prix.prepare_u_runtime import prepare

COURSE = 'gp-progression-v1-a7-v5'
EPOCH = 'a' * 32
NEXT = 'b' * 32
FORCED = 2147483646


def phase_fixture(case, offset):
    """Entirely synthetic; exercises all parser branches, including same tick."""
    touch = 212112
    land = touch-32
    applied = touch+offset
    transfer = applied+8 if case == 'stop' else applied
    start = applied-210000 if case == 'deadline' else 10000
    sep, returned = touch+8, touch+104
    ack = returned+504
    late, before, after = transfer+8, transfer+16, ack+8
    journal = ['GP_ROUTE_CONTROL_TIMING physics_ms=8 control_ms=8 range_ms=32',
               f'GP_U_ADMISSION attempt=1 start_ms={start}',
               f'A7_V5_RX {land} 17 LAND 1 {EPOCH}',
               f'GP_U_LAND_GROUND_READY t={ack/1000:.3f} window=0.504']
    wwi = []
    events = [dict(event='FIRST_CONTACT', ms=touch),
              dict(event='FIRST_SEPARATION', ms=sep)]
    def reply(id, message):
        wwi.append(f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {id} {message}')
    def request(id, command, at):
        journal.append(f'A7_V5_RX {at} {id} {command} 1 {EPOCH}')
        wwi.append(f'A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST {id} {command}')
    if case == 'calibration':
        reply(17, 'OK')
        wwi.append('{"status":"achieved"}')
    else:
        if case == 'stop':
            events.append(dict(event='STOP_EMITTED', ms=applied-8,
                               sender=dict(id=18, observed_ms=applied-8)))
            request(18, 'STOP', applied)
            journal.append(f'A7_V5_STOP_APPLIED {applied} 18 17')
            reply(18, 'OK')
            reply(17, 'ERR USER_STOPPED')
        elif case == 'liveness':
            alive = f'GP_ROUTE_ALIVE_V1 attempt=1 config={COURSE} epoch={EPOCH} time_ms='
            events.append(dict(event='ALIVE_REVOKED', ms=applied-8, previous=alive+str(applied-16)))
            journal.extend([f'A7_V5_LIVENESS_GUARD {applied} 1 {EPOCH}',
                            f'A7_V5_ALIVE {applied} 1 {EPOCH} {applied-16} -1 <empty>',
                            f'A7_V5_ALIVE {applied-8} 1 {EPOCH} {applied-24} {applied-16} {alive}{applied-16}'])
            reply(17, 'ERR TIME_LIMIT')
        else:
            events.append(dict(event='PHASE_LAND_EMITTED', ms=land-8))
            wwi.append('{"status":"not-achieved","reason":"time-limit"}')
            reply(17, 'ERR TIME_LIMIT')
        journal.append(f'GP_U_DEADLINE time_ms={transfer} command=LAND interrupted_id={-1 if case == "stop" else 17}')
        request(19, 'STOP', late)
        reply(19, 'ERR TIME_LIMIT')
        request(20, 'RESET', before)
        reply(20, 'ERR LANDING_UNCONFIRMED')
        reply(FORCED, 'OK')
        request(21, 'RESET', after)
        reply(21, 'OK')
    for ms in range(land, ack+17, 8):
        floor = ms == touch or ms >= returned
        events.append(dict(event='ODE', ms=ms, floor=floor, stable=ms >= returned,
                           contacts=[dict(point=[0., 0., 0.])] if floor else [],
                           velocity=[0., 0., .05 if ms == sep else 0.],
                           epoch=NEXT if ms > after else EPOCH,
                           attempt=2 if ms > after else 1,
                           phase='ready' if ms > after else 'active'))
        if ms > ack:
            continue
        owner = 17
        if case != 'calibration':
            if ms >= transfer:
                owner = FORCED
            elif case == 'stop' and ms >= applied:
                owner = -1
        contact = returned if ms >= returned else touch if ms == touch else -1000
        motors = '0 0 0 0' if ms >= touch else '-56 56 -56 56'
        journal.append(f'A7_V5_CYCLE {ms} 6 {owner} {int(ms>=touch)} 1 1 {int(floor)} '
                       f'{contact} {returned} {returned} {motors}')
    return '\n'.join(journal)+'\n', '\n'.join(map(json.dumps, events)), '\n'.join(wwi)+'\n'


class NativeLatchPhaseTests(unittest.TestCase):
    def test_instrumentation_is_isolated_and_requires_unique_anchors(self):
        with tempfile.TemporaryDirectory() as d:
            prepare(d, legacy_worlds=False, route_observations=True)
            product = (Path(d) / 'runtime_u.c').read_text()
            self.assertNotIn('gp_phase_mark', product)
            source = instrument_phase(instrument_pilot(product))
            self.assertEqual(source.count('gp_phase_mark("phase-land"'), 1)
            self.assertEqual(source.count('gp_phase_mark("phase-force"'), 1)
            self.assertEqual(source.count('gp_phase_mark("phase-tick"'), 1)
            with self.assertRaisesRegex(RuntimeError, 'phase instrumentation already present'):
                instrument_phase(source)
            with self.assertRaisesRegex(RuntimeError, 'phase instrumentation already present'):
                instrument_phase(product + '\n/* gp_phase_mark */\n')
            for changed in (
                product.replace('static int land_has_ground_contact(', 'static int renamed_land_contact('),
                product + '\nstatic int land_has_ground_contact(',
            ):
                with self.subTest(changed_length=len(changed)):
                    with self.assertRaisesRegex(RuntimeError, 'instrumentation anchor changed'):
                        instrument_phase(changed)

    def test_calibration_and_all_nine_exact_phase_parser_paths(self):
        self.assertEqual(verify_phase('calibration', 0, *phase_fixture('calibration', 0), COURSE)['delay_ms'], 32)
        for case in CASES:
            for offset in OFFSETS:
                with self.subTest(case=case, offset=offset):
                    self.assertEqual(verify_phase(case, offset, *phase_fixture(case, offset), COURSE)['phase_ms'], offset)

    def test_off_phase_not_pass_and_motor_violation_not_hidden(self):
        journal, ode, wwi = phase_fixture('stop', 0)
        with self.assertRaisesRegex(ReboundUnproven, 'effective phase'):
            verify_phase('stop', 8, journal, ode, wwi, COURSE)
        line = next(line for line in journal.splitlines() if line.startswith('A7_V5_CYCLE 212112 '))
        pulse = journal.replace(line, line[:-1]+'1')
        with self.assertRaisesRegex(RuntimeError, 'motor/latch violation'):
            verify_phase('stop', 8, pulse, ode, wwi, COURSE)

    def test_transfer_duplicate_late_stop_and_reset_are_blocking(self):
        journal, ode, wwi = phase_fixture('liveness', 0)
        line = next(line for line in journal.splitlines() if line.startswith('GP_U_DEADLINE '))
        with self.assertRaisesRegex(RuntimeError, 'duplicate independent'):
            verify_phase('liveness', 0, journal+line+'\n', ode, wwi, COURSE)
        with self.assertRaisesRegex(RuntimeError, 'late STOP not refused'):
            verify_phase('liveness', 0, journal, ode, wwi.replace('19 ERR TIME_LIMIT', '19 OK'), COURSE)
        with self.assertRaisesRegex(RuntimeError, 'RESET did not straddle'):
            verify_phase('liveness', 0, journal, ode, wwi.replace('20 ERR LANDING_UNCONFIRMED', '20 OK'), COURSE)

    def test_missing_native_admission_cannot_pass(self):
        journal, ode, wwi = fixture_8ms('stop')
        with self.assertRaises(ReboundUnproven):
            verify_phase('stop', 0, journal, ode, wwi, COURSE)
