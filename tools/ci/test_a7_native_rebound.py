"""Deterministic falsifiers of the trace oracle, separate from native execution."""

import json
from pathlib import Path
import tempfile
import unittest

from tools.ci.a7_native_rebound import (
    AliveDisconnection, COURSE, FORCED_ID, ReboundUnproven, instrument_deadline,
    instrument_pilot, prepare, verify,
)

EPOCH = 'a' * 32
READY_EPOCH = 'b' * 32
CYCLE = 'A7_V5_CYCLE 256 6 2147483646 1 1 1 1 224 96 160 0 0 0 0'
ALIVE = f'GP_ROUTE_ALIVE_V1 attempt=1 config={COURSE} epoch={EPOCH} time_ms='


def fixture(case):
    """Deliberately small parser fixture without any physical evidentiary claim."""
    records = [{'event': 'FIRST_CONTACT', 'ms': 96}, {'event': 'FIRST_SEPARATION', 'ms': 104}]
    journal = [f'A7_V5_RX 64 17 LAND 1 {EPOCH}']
    wwi = []
    if case == 'stop':
        records.append({'event': 'STOP_EMITTED', 'ms': 104, 'sender': {'observed_ms': 104, 'id': 18}})
        journal += [f'A7_V5_RX 128 18 STOP 1 {EPOCH}', 'A7_V5_STOP_APPLIED 128 18 17',
                    'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 18 OK']
        wwi += ['A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST 18 STOP',
                'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE 18 OK']
        transfer, interrupted, error = 160, -1, 'USER_STOPPED'
    else:
        records.append({'event': 'ALIVE_REVOKED', 'ms': 104, 'previous': ALIVE + '96'})
        journal += [f'A7_V5_ALIVE 96 1 {EPOCH} 56 88 {ALIVE}88',
                    f'A7_V5_ALIVE 128 1 {EPOCH} 88 -1 <empty>',
                    f'A7_V5_LIVENESS_GUARD 128 1 {EPOCH}']
        transfer, interrupted, error = 128, 17, 'TIME_LIMIT'
    journal += [
        f'GP_U_DEADLINE time_ms={transfer} command=LAND interrupted_id={interrupted}',
        f'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 17 ERR {error}',
        'GP_U_LAND_GROUND_READY t=0.736 window=0.512',
        f'WEBEEBLOCKS_RUNTIME_V2 RESPONSE {FORCED_ID} OK',
        f'A7_V5_RX 192 19 RESET 1 {EPOCH}', f'A7_V5_RX 768 20 RESET 1 {EPOCH}',
    ]
    wwi += ['A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST 19 RESET',
            'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE 19 ERR TIME_LIMIT',
            f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {FORCED_ID} OK',
            'A7_V5_WWI > WEBEEBLOCKS_RUNTIME_V2 REQUEST 20 RESET',
            'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE 20 OK']
    for ms in range(96, 737, 32):
        request = FORCED_ID if ms >= transfer else -1 if ms == 128 else 17
        contact = 224 if ms >= 224 else 96 if ms == 96 else -1000
        journal.append(
            f'A7_V5_CYCLE {ms} 6 {request} 1 {int(ms < 736)} 1 {int(contact >= 0)} '
            f'{contact} 96 {max(160, transfer)} 0 0 0 0')
    for ms in range(64, 801, 8):
        floor = ms == 96 or ms >= 200
        records.append(dict(event='ODE', ms=ms, floor=floor, stable=floor,
                            contacts=[{'point': [0, 0, 0]}] if floor else [],
                            velocity=[0, 0, .01],
                            attempt=1 if ms <= 768 else 2,
                            epoch=EPOCH if ms <= 768 else READY_EPOCH,
                            phase='active' if ms <= 768 else 'ready'))
    return ('\n'.join(journal) + '\n', '\n'.join(map(json.dumps, records)),
            '\n'.join(wwi) + '\n')


class ReboundTraceOracleTest(unittest.TestCase):
    def test_composes_only_in_the_experiment_build(self):
        with tempfile.TemporaryDirectory() as directory:
            prepare(directory, legacy_worlds=False, route_observations=True)
            runtime = (Path(directory) / 'runtime_u.c').read_text()
        self.assertNotIn('A7_V5_CYCLE', runtime)
        self.assertEqual(instrument_pilot(runtime).count('A7_V5_CYCLE'), 2)
        deadline = Path('controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp').read_text()
        self.assertIn('A7_V5_LIVENESS_GUARD', instrument_deadline(deadline))

    def test_both_causal_chains_are_required(self):
        self.assertEqual(verify('stop', *fixture('stop'))['transfer_ms'], 160)
        self.assertEqual(verify('liveness', *fixture('liveness'))['transfer_ms'], 128)
        journal, ode, wwi = fixture('stop')
        with self.assertRaisesRegex(ReboundUnproven, 'escaped the first'):
            verify('stop', journal.replace('A7_V5_STOP_APPLIED 128', 'A7_V5_STOP_APPLIED 200'),
                   ode, wwi)
        with self.assertRaisesRegex(ReboundUnproven, 'transfer did not occur'):
            verify('stop', journal.replace('time_ms=160 command=LAND', 'time_ms=224 command=LAND'),
                   ode, wwi)
        journal, ode, wwi = fixture('liveness')
        with self.assertRaisesRegex(ReboundUnproven, 'native read of withdrawn ALIVE'):
            verify('liveness', journal.replace('<empty>', ALIVE + '120'), ode, wwi)
        with self.assertRaisesRegex(RuntimeError, 'received STOP'):
            verify('liveness', journal + f'A7_V5_RX 128 18 STOP 1 {EPOCH}\n', ode, wwi)

    def test_no_pass_on_motor_contact_or_reset_regressions(self):
        journal, ode, wwi = fixture('stop')
        with self.assertRaisesRegex(RuntimeError, 'motor cutoff'):
            verify('stop', journal.replace(CYCLE, CYCLE[:-1] + '.1'), ode, wwi)
        with self.assertRaisesRegex(RuntimeError, 'motor cutoff or latch'):
            verify('stop', journal.replace(CYCLE, CYCLE.replace(' 1 1 1 1 ', ' 0 1 1 1 ')), ode, wwi)
        with self.assertRaisesRegex(ReboundUnproven, 'continuous 8-ms physics'):
            verify('stop', journal, '\n'.join(line for line in ode.splitlines()
                                               if '"ms": 504' not in line), wwi)
        with self.assertRaisesRegex(RuntimeError, 'stability'):
            verify('stop', journal.replace(' 224 96 160 ', ' 224 96 320 '), ode, wwi)
        with self.assertRaisesRegex(RuntimeError, 'RESET requests do not straddle'):
            verify('stop', journal.replace('192 19 RESET', '768 19 RESET'), ode, wwi)

    def test_disconnection_only_suppresses_alive(self):
        class TraceField:
            def __init__(self):
                self.writes = []

            def setSFString(self, value):
                self.writes.append(value)

        field = TraceField()
        events = []
        publication = AliveDisconnection(field, lambda *args, **data: events.append((args, data)))
        publication.setSFString('GP_ROUTE_READY_V1')
        publication.setSFString(ALIVE + '96')
        publication.cut_at = 104
        publication.setSFString(ALIVE + '104')
        publication.setSFString(ALIVE + '112')
        publication.setSFString('GP_ROUTE_TERMINAL_V1')
        self.assertEqual(field.writes, ['GP_ROUTE_READY_V1', ALIVE + '96', '', 'GP_ROUTE_TERMINAL_V1'])
        self.assertEqual(events, [(('ALIVE_REVOKED', 104),
                                   {'previous': ALIVE + '96', 'withheld': ALIVE + '104'})])
