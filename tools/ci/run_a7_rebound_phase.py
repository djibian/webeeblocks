"""Opt-in bounded native phase experiment, not a replacement for verify().

The four ordinary TAKEOFF stimuli span one 32-ms LAND approach period at
0.40 m/s. The true contact phase is measured, never inferred from this model.
No impulse, scene edit, timing change, threshold change, or forced result.
"""
import json
import os
from pathlib import Path
import re

from tools.ci.a7_native_rebound import CASES, verify
from tools.ci.run_grand_prix_progression_native import OUT, run_native

HEIGHTS = (.90, .8968, .8936, .8904)


def missed_contact_precondition(journal, contacts, wwi, result):
    """Recognize only the measured absent first-contact sampling precondition.

    A missing witness is not a PASS. Any sampled contact without the motor
    latch, intervention after latch, malformed trace, or other failure blocks
    the experiment. Never classify such a run as an admissible absent phase.
    """
    if (result.get('result') != 'UNPROVEN' or
            result.get('reason') != 'nominal motor latch not established before separation'):
        return False
    rows = [json.loads(line) for line in contacts.splitlines()]
    samples = [row for row in rows if row['event'] == 'ODE']
    if not samples or any(b['ms'] - a['ms'] != 8 for a, b in zip(samples, samples[1:])):
        return False
    touch = [row['ms'] for row in rows if row['event'] == 'FIRST_CONTACT']
    separation = [row for row in rows if row['event'] == 'FIRST_SEPARATION']
    land = re.findall(r'^A7_V5_RX (\d+) (\d+) LAND (\d+) ([0-9a-f]{32})$', journal, re.M)
    if len(touch) != 1 or len(separation) != 1 or len(land) != 1:
        return False
    t, sep = touch[0], separation[0]
    if sep['ms'] != t + 8 or sep.get('latch') != [] or not int(land[0][0]) < t:
        return False
    ode = {row['ms']: row for row in samples}
    if (not ode[t]['floor'] or ode[t+8]['contacts'] or ode[t+8]['velocity'][2] <= 0 or
            ode[t]['attempt'] != int(land[0][2]) or ode[t]['epoch'] != land[0][3]):
        return False
    cycles = [line.split() for line in journal.splitlines() if line.startswith('A7_V5_CYCLE ')]
    if any(len(line) != 15 for line in cycles):
        return False
    times = [int(line[1]) for line in cycles]
    # Strictly bracket the 8-ms contact by consecutive 32-ms controller ticks.
    if not any(a < t < t+8 <= b and b-a == 32 for a, b in zip(times, times[1:])):
        return False
    if any(row['event'] in ('STOP_EMITTED', 'ALIVE_REVOKED') for row in rows):
        return False
    nominal = int(land[0][1])
    # A late successful nominal landing does NOT establish the transfer.
    # Do not hide a genuine post-latch motor/pose failure merely because the
    # intended first-rebound intervention could not be exercised.
    nominal_cycles = {int(line[1]): line for line in cycles if int(line[3]) == nominal}
    locked = [ms for ms, line in nominal_cycles.items() if int(line[4]) == 1]
    ready = re.findall(r'^GP_U_LAND_GROUND_READY t=(\d+\.\d+) window=', journal, re.M)
    if not locked or not ready:
        return False
    latch, ack = min(locked), round(float(ready[0])*1000)
    if (not t+8 < latch < ack or (ack-latch) % 32 or
            not all(ms in nominal_cycles and int(nominal_cycles[ms][4]) == 1 and
                    all(float(m) == 0 for m in nominal_cycles[ms][11:15])
                    for ms in range(latch, ack+1, 32)) or
            not all(ms in ode and ode[ms]['stable'] and
                    ode[ms]['attempt'] == int(land[0][2]) and ode[ms]['epoch'] == land[0][3]
                    for ms in range(ack-504, ack+1, 8))):
        return False
    return (f'WEBEEBLOCKS_RUNTIME_V2 RESPONSE {nominal} OK\n' in journal and
            f'A7_V5_WWI < WEBEEBLOCKS_RUNTIME_V2 RESPONSE {nominal} OK' in wwi)


def run():
    evidence = []
    target = os.environ['TARGET_SHA']
    home = Path(os.environ['WEBOTS_HOME'])
    for case in CASES:
        for height in HEIGHTS:
            out = OUT / f'route-a7-v5-native-rebound-{case}-h{round(height*10000):04d}'
            if out.exists():
                raise RuntimeError(f'phase evidence directory already exists: {out}')
            error = None
            try:
                run_native(home, os.environ.copy(), 7, 5, rebound=case, rebound_height=height)
            except (OSError, RuntimeError) as exc:
                error = str(exc)
            item = dict(case=case, height=height, path=out.name, classification='BLOCKING',
                        error=error)
            try:
                result = json.loads((out / 'result.json').read_text())
                identity = json.loads((out / 'identity.json').read_text())
                if (identity['git_head'] != target or identity['tracked_status'] or
                        identity['actions']['TARGET_SHA'] != target or
                        identity['actions']['GITHUB_RUN_ID'] != os.environ['GITHUB_RUN_ID'] or
                        identity['rebound_height'] != str(height) or result['case'] != case):
                    raise RuntimeError('phase identity drift')
                journal, contacts, wwi = ((out / name).read_text() for name in
                                          ('webots.log', 'contacts.jsonl', 'wwi.log'))
                item['native_result'] = result
                if error is None and result['result'] == 'PASS':
                    # Reapply the original verifier to archived bytes; never
                    # replace its continuous-contact/zero-motor/reset checks.
                    item['proof'] = verify(case, journal, contacts, wwi)
                    item['classification'] = 'PASS'
                elif error and missed_contact_precondition(journal, contacts, wwi, result):
                    item['classification'] = 'PRECONDITION_ABSENT_UNPROVEN'
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                item['verification_error'] = str(exc)
            evidence.append(item)
            (OUT / 'a7-rebound-phase-summary.json').write_text(json.dumps(evidence, indent=2)+'\n')
    if (any(item['classification'] == 'BLOCKING' for item in evidence) or
            any(not any(item['case'] == case and item['classification'] == 'PASS'
                        for item in evidence) for case in CASES)):
        raise RuntimeError('A7 phase experiment lacks both strict first-rebound witnesses or has blocking evidence')
    print('PASS A7 controlled phase experiment: both original first-rebound verifiers passed')


if __name__ == '__main__':
    run()
