"""Fail closed on incomplete native observations; never turn inconclusive green."""
import csv
import json
import math
from pathlib import Path


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def rotor_states(path):
    rows = list(csv.DictReader(path.open()))
    previous = [0.] * 4
    speeds = [0.] * 4
    result = []
    previous_time = 0.
    for row in rows:
        now = float(row['time'])
        dt = now - previous_time
        if not 0 < dt <= .008001:
            raise ValueError('native rotor sampling gap')
        current = []
        for i in range(1, 5):
            axis = [float(row[f'm{i}_{a}']) for a in ('x','y','z')]
            angle = float(row[f'm{i}_angle'])
            if not all(math.isfinite(v) for v in (*axis, angle)):
                raise ValueError('nonfinite helix')
            if abs(angle) > 1e-9 and (abs(axis[0]) > 1e-8 or abs(axis[1]) > 1e-8 or abs(abs(axis[2])-1) > 1e-8):
                raise ValueError('non-shaft rotation')
            raw = angle * axis[2]
            expected = previous[i-1] + speeds[i-1]*dt
            phase = raw + 2*math.pi*round((expected-raw)/(2*math.pi))
            speed = (phase-previous[i-1])/dt
            if abs(speed-speeds[i-1]) > 30*dt + 1e-4 or abs(speed) > 600.0001:
                raise ValueError('rotor speed reconstruction violates native slew bound')
            previous[i-1] = phase
            current.append(speed)
        speeds = current
        # Model-derived applied force, not a measured contact impulse.
        result.append(dict(time=now, omega=current, thrust=[4e-5*v*v for v in current]))
        previous_time = now
    if not result or max(max(abs(v) for v in r['omega']) for r in result) < 10:
        raise ValueError('native helix state missing/frozen')
    return result


def summarize(folder: Path, variant):
    native = [{k: float(v) for k,v in row.items() if k != 'contact_points_xyz' and v != ''}
              for row in csv.DictReader((folder/'native_trace.csv').open())]
    control = read_jsonl(folder/'causal-control.jsonl')
    land = [json.loads(l.split('GP_U_LAND_CONTROL ',1)[1]) for l in (folder/'webots.log').read_text().splitlines() if l.startswith('GP_U_LAND_CONTROL ')]
    stops = [r for r in land if r['phase']=='stop']
    if len(stops) != 1:
        raise ValueError('missing/ambiguous LAND stop')
    start = min(r['time_ms']/1000 for r in land)
    stop = stops[0]['time_ms']/1000
    if not native or native[-1]['time'] < stop + 3:
        raise ValueError('coast observation truncated')
    touches = [r for r in native if r['time'] >= start and r.get('contact_count',0)>0]
    if not touches:
        raise ValueError('LAND ground contact not observed')
    touch = touches[0]
    after = [r for r in native if touch['time'] <= r['time'] <= stop+3]
    target = json.loads((folder/'native-diagnostic-1.json').read_text())['landing_target']
    error = [touch['x']-target[0],touch['y']-target[1]]
    speed = lambda r: math.hypot(r['vx'],r['vy'])
    max_speed = max(map(speed,after))
    displacement = max(math.hypot(r['x']-touch['x'],r['y']-touch['y']) for r in after)
    outcome = json.loads((folder/'native-result-1.json').read_text())
    rotors = rotor_states(folder/'native-rotors.csv')
    active = [r for r in control if r['phase']=='control' and r['ablation']]
    if (variant=='B') != bool(active):
        raise ValueError('wrong experimental intervention')
    # Derivative ablation must match the unchanged P velocity law in the real C.
    for r in active:
        expected = [-2*max(-1,min(1,r['error'][1])), 2*max(-1,min(1,r['error'][0]))]
        if any(abs(a-b)>1e-6 for a,b in zip(expected,r['attitude_cmd'])):
            raise ValueError('ablation did not isolate velocity derivative')
    applied = [r for r in rotors if touch['time'] <= r['time'] <= stop+3]
    at_stop = min(rotors,key=lambda r:abs(r['time']-stop))
    record = dict(variant=variant, outcome=outcome, first_contact=touch,
        error_xy=error, contact_error=math.hypot(*error), contact_speed=speed(touch),
        max_postcontact_speed=max_speed, max_postcontact_displacement=displacement,
        stop_seconds=stop, stop_target=stops[0]['motors'], rotor_at_stop=at_stop,
        max_thrust_after_contact=max(sum(r['thrust']) for r in applied),
        ablation_steps=len(active), actual_force_claim='native-helix-derived R2025a model force; no direct contact force',
        defect_exercised=math.hypot(*error)<=.10 and speed(touch)<=.02 and
            (displacement>.10 or max_speed>.20) and outcome['reason'] in ('wrong-landing','envelope-contact'),
        bounded_B_success=outcome['status']=='achieved' and max_speed<=.05 and displacement<=.03)
    (folder/'rotor-derived.json').write_text(json.dumps(rotors,indent=2)+'\n')
    (folder/'analysis.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def compare(a,b):
    ac,bc = a['first_contact'],b['first_contact']
    roll=lambda r:math.atan2(r['r7'],r['r8'])
    pitch=lambda r:math.asin(max(-1,min(1,-r['r6'])))
    comparable=(math.dist(a['error_xy'],b['error_xy'])<=.02 and
        math.dist([ac['vx'],ac['vy']],[bc['vx'],bc['vy']])<=.02 and
        abs(ac['vz']-bc['vz'])<=.03 and abs(roll(ac)-roll(bc))<=math.pi/180 and
        abs(pitch(ac)-pitch(bc))<=math.pi/180 and ac['contact_count']==bc['contact_count'])
    return dict(comparable=comparable, reference_exercised=a['defect_exercised'],
        supports_hypothesis=comparable and a['defect_exercised'] and b['bounded_B_success'],
        verdict='INCONCLUSIVE' if not a['defect_exercised'] or not comparable else
                ('SUPPORT_ONE_PAIR' if b['bounded_B_success'] else 'NOT_SUPPORTED'))
