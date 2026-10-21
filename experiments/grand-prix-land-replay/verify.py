#!/usr/bin/env python3
"""Verify retained native excerpts and replay the real PID, without Webots.

Optional original ZIP arguments additionally verify every original scenario
manifest and the byte offsets of each retained native CSV window.
"""
import argparse
import csv
import ctypes
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def records(path):
    rows = [json.loads(line.split('GP_U_LAND_CONTROL ', 1)[1])
            for line in path.read_text().splitlines()
            if line.startswith('GP_U_LAND_CONTROL ')]
    require(rows and rows[-1]['phase'] == 'stop', 'missing stop')
    require(sum(r['phase'] == 'stop' for r in rows) == 1, 'multiple stops')
    require(all(b['time_ms'] > a['time_ms'] for a, b in zip(rows, rows[1:])), 'clock')
    return rows


def replay(lib, rows, scale=1):
    lib.replay_init()
    result = []
    for i, row in enumerate(rows):
        if row['phase'] != 'control':
            continue
        dt = (row['time_ms']-rows[i-1]['time_ms'])/1000 if i else .032
        require(dt > 0, 'non-positive dt')
        vx, vy, _ = row['velocity_world']
        roll, pitch, yaw = row['rpy']
        body = [vx*math.cos(yaw)+vy*math.sin(yaw), -vx*math.sin(yaw)+vy*math.cos(yaw)]
        out = (ctypes.c_double*4)()
        lib.replay_step(dt, roll, pitch, row['position'][2], *body,
                        row['desired_altitude'], scale, out)
        require(all(math.isfinite(x) for x in (*out, *body)), 'nonfinite replay')
        result.append(dict(time_ms=row['time_ms'], attitude=list(out[:2]),
                           roll_mix=out[2], pitch_mix=out[3], body=body))
    return result


def analyze(case, lib):
    data = HERE/'data'/case['name']
    original = json.loads((data/'source-sha256.json').read_text())
    for name in ('webots.log', 'world.wbt', 'layout.json', 'events.jsonl',
                 'native-result-1.json', 'native-diagnostic-1.json'):
        require(sha((data/name).read_bytes()) == original[name], 'original hash: '+name)
    rows = records(data/'webots.log')
    controls = rows[:-1]
    base = replay(lib, rows)
    derivative_off = replay(lib, rows, 0)
    errors = []
    compared = 0
    clipped = []
    for i, (row, predicted) in enumerate(zip(controls, base)):
        require(row['desired_velocity_body'] == [0, 0], 'not ordinary LAND')
        if i < 2:
            continue  # Unretained pre-LAND PID history, erased after two steps.
        if 'attitude_cmd' in row:
            errors.extend(abs(a-b) for a, b in zip(row['attitude_cmd'][:2], predicted['attitude']))
            errors.extend(abs(a-b) for a, b in zip(row['actual_velocity_body'], predicted['body']))
        motors = [abs(x) for x in row['motors']]
        require(row['motors'][0] <= 0 and row['motors'][1] >= 0 and
                row['motors'][2] <= 0 and row['motors'][3] >= 0, 'motor signs')
        # Clamps destroy invertibility. Do not pretend a clipped command is a
        # measurement of its raw PID mixture. Keep excluded timestamps explicit.
        if not all(0 < m < 600 for m in motors):
            clipped.append(row['time_ms'])
            continue
        observed = [(-motors[0]-motors[1]+motors[2]+motors[3])/4,
                    (motors[0]-motors[1]-motors[2]+motors[3])/4]
        errors.extend(abs(a-b) for a, b in zip(observed, [predicted['roll_mix'], predicted['pitch_mix']]))
        compared += 1
    require(compared > 10 and max(errors) < 0.00001, 'PID replay differs from native commands')
    native = list(csv.DictReader((data/'native-land-window.csv').open(newline='')))
    active = [r for r in native if controls[0]['time_ms'] <= float(r['time'])*1000 <= rows[-1]['time_ms']]
    contact = next(r for r in active if int(r['contact_count']) > 0)
    contact_ms = round(float(contact['time'])*1000)
    after = [r for r in active if float(r['time'])*1000 >= contact_ms-1e-6]
    diagnostic = json.loads((data/'native-diagnostic-1.json').read_text())
    target = diagnostic['landing_target']
    events = [json.loads(line) for line in (data/'events.jsonl').read_text().splitlines()]
    ast = [e['detail'] for e in events if e['event'] == 'program']
    require(len(ast) == 1, 'missing exact AST')
    landmarks = []
    for i, r in enumerate(controls):
        if contact_ms <= r['time_ms'] <= contact_ms+72:
            landmarks.append(dict(time_ms=r['time_ms'], actual_roll_degrees=math.degrees(r['rpy'][0]),
                requested_roll_degrees=math.degrees(base[i]['attitude'][0]),
                measured_body_vy=base[i]['body'][1], roll_mix=base[i]['roll_mix'],
                derivative_off_requested_roll_degrees=math.degrees(derivative_off[i]['attitude'][0])))
    return dict(name=case['name'], result=json.loads((data/'native-result-1.json').read_text()),
        ast_sha256=sha(json.dumps(ast[0], sort_keys=True, separators=(',', ':')).encode()),
        compared_control_samples=compared, clipped_mix_excluded_ms=clipped,
        maximum_replay_error=max(errors),
        first_contact_ms=contact_ms, first_contact_count=int(contact['contact_count']),
        first_contact_position=[float(contact[k]) for k in ('x','y','z')],
        first_contact_xy_error=math.hypot(float(contact['x'])-target[0], float(contact['y'])-target[1]),
        first_contact_native_velocity=[float(contact[k]) for k in ('vx','vy','vz')],
        max_post_contact_native_xy_speed=max(math.hypot(float(r['vx']),float(r['vy'])) for r in after),
        max_post_contact_native_roll_degrees=max(abs(math.degrees(math.atan2(float(r['r7']),float(r['r8'])))) for r in after),
        max_requested_roll_before_verdict_degrees=max(abs(math.degrees(r['attitude'][0]))
            for r in base[2:] if r['time_ms'] <= round(diagnostic['time']*1000)),
        max_requested_roll_until_stop_degrees=max(abs(math.degrees(r['attitude'][0])) for r in base[2:]),
        first_contact_control_landmarks=landmarks, motor_stop=rows[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-zip', action='append', default=[], type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE/'sha256.json').read_text())
    for name, digest in manifest.items():
        require(sha((HERE/name).read_bytes()) == digest, 'retained hash: '+name)
    sources = json.loads((HERE/'sources.json').read_text())
    for name, digest in sources['pid_sources'].items():
        require(sha((ROOT/name).read_bytes()) == digest, 'production source changed: '+name)
    archives = {sha(p.read_bytes()): p for p in args.original_zip}
    if args.original_zip:
        for case in sources['cases']:
            require(case['archive_sha256'] in archives, 'missing original ZIP')
            with zipfile.ZipFile(archives[case['archive_sha256']]) as z:
                require(z.testzip() is None, 'ZIP CRC')
                folder = case['source_folder']+'/'
                original = json.loads(z.read(folder+'sha256.json'))
                for name, digest in original.items():
                    require(sha(z.read(folder+name)) == digest, 'ZIP scenario manifest')
                window = case['native_excerpt']
                full = z.read(folder+window['source'])
                excerpt = full[:window['header_bytes']]+full[window['byte_start']:window['byte_end_exclusive']]
                require(excerpt == (HERE/'data'/case['name']/window['retained']).read_bytes(), 'not exact source slice')
                if case['artifact'] == 12216162199:
                    require(z.read('campaign.json') == (HERE/'data/campaign-success.json').read_bytes(),
                            'campaign summary differs from original ZIP')
                    require(z.read('landing-contrast.json') == (HERE/'data/landing-contrast.json').read_bytes(),
                            'contrast summary differs from original ZIP')
    with tempfile.TemporaryDirectory(prefix='gp-land-replay-') as tmp:
        library = Path(tmp)/'pid.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-I'+str(ROOT/'controllers/crazyflie_square'),
            str(HERE/'pid_replay.c'), str(ROOT/'controllers/crazyflie_square/pid_controller.c'),
            '-lm', '-o', str(library)], check=True)
        lib = ctypes.CDLL(str(library))
        lib.replay_init.argtypes = []; lib.replay_init.restype = None
        lib.replay_step.argtypes = [ctypes.c_double]*8+[ctypes.POINTER(ctypes.c_double)]
        lib.replay_step.restype = None
        result = [analyze(case, lib) for case in sources['cases']]
    require(len({r['ast_sha256'] for r in result}) == 1, 'AST differs')
    campaign = json.loads((HERE/'data/campaign-success.json').read_text())
    expected = {'short': 'wrong-landing', 'wrong-landing': 'wrong-landing',
                'low-outside': 'low-outside-zone', 'collision': 'envelope-contact',
                'reverse': 'reverse-crossing', 'unavailable': 'runtime',
                'timeout': 'time-limit', 'timeout-gate': 'time-limit'}
    negatives = [r for r in campaign if r['mode'] in expected]
    require(set(r['mode'] for r in negatives) == set(expected), 'negative case missing')
    require(all(r['status'] == 'not-achieved' and r['reason'] == expected[r['mode']]
                for r in negatives), 'negative result changed')
    def without_cells(path):
        return b''.join(l for l in path.read_bytes().splitlines(keepends=True)
                        if not (l.startswith(b'DEF GP_U_TARGET_') and b'_CELL_' in l))
    require(without_cells(HERE/'data/flat-s14/world.wbt') ==
            without_cells(HERE/'data/checkered-a-s14/world.wbt'), 'visual contrast changed more than tiles')
    print(json.dumps(dict(claim='open-loop PID replay of retained native LAND states; no plant counterfactual',
        original_archives_verified=bool(args.original_zip), cases=result,
        historical_negative_results=negatives), indent=2))


if __name__ == '__main__':
    main()
