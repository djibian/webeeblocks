#!/usr/bin/env python3
"""Reanalyse archived Supervisor observations; never label them consumed IMU.

No Webots execution. --archive verifies the original tar and exact CSV slice.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def analyze():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    provenance = json.loads((HERE/'sources.json').read_text())
    manifest = json.loads((HERE/'sha256.json').read_text())
    for name, digest in manifest.items():
        require(sha((HERE/'data'/name).read_bytes()) == digest, 'retained digest: '+name)
    original = json.loads((HERE/'data/sha256.json').read_text())
    for name, digest in original.items():
        if name != 'native_trace.csv':
            require(sha((HERE/'data'/name).read_bytes()) == digest, 'original digest: '+name)
    if args.archive:
        payload = args.archive.read_bytes()
        require(len(payload) == provenance['archive_bytes'] and
                sha(payload) == provenance['archive_sha256'], 'archive identity')
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:xz') as archive:
            prefix = provenance['source_folder']+'/'
            for name, digest in original.items():
                raw = archive.extractfile(prefix+name).read()
                require(sha(raw) == digest, 'archive manifest: '+name)
                if name == 'native_trace.csv':
                    window = provenance['window']
                    require(len(raw) == provenance['source_csv_bytes'], 'CSV length')
                    excerpt = raw[:window['header_bytes']]+raw[window['byte_start']:window['byte_end_exclusive']]
                    require(excerpt == (HERE/'data/native-window.csv').read_bytes(), 'CSV slice')
                    require(dict(zip(raw.splitlines()[0].decode().split(','),
                                     raw.splitlines()[-1].decode().split(','))) ==
                            provenance['last_source_sample'], 'final source observation')
                else:
                    require(raw == (HERE/'data'/name).read_bytes(), 'retained bytes: '+name)
    flight = (HERE/'data/flight.log').read_text()
    start = int(re.search(r'GP_U_ADMISSION attempt=1 start_ms=(\d+)', flight)[1])
    deadline = int(re.search(r'GP_U_DEADLINE time_ms=(\d+) command=LAND interrupted_id=59', flight)[1])
    require(deadline-start == 210000, 'deadline')
    require('RESPONSE 2147483646 ERR UNSAFE_OR_TIMEOUT' in flight and
            'FATAL unsafe attitude or action timeout' in flight, 'forced-LAND refusal')
    require('TRACE LAND' not in flight and 'GP_U_LAND_CONTROL' not in flight, 'unexpected telemetry')
    events = [json.loads(line) for line in (HERE/'data/events.jsonl').read_text().splitlines()]
    require(not any(e['event'] == 'request' and e['detail'].endswith(' RESET') for e in events), 'RESET present')
    for command in ('COMPLETE', 'FAILURE', 'MOVE', 'STOP'):
        require(any(e['event'] == 'late-command-rejected' and
                    e['detail'] == {'command': command, 'code': 'TIME_LIMIT'} for e in events),
                'late command not fenced: '+command)
    rows = []
    for source in csv.DictReader((HERE/'data/native-window.csv').open(newline='')):
        r = {k: float(v) for k, v in source.items()}
        require(all(math.isfinite(v) for v in r.values()), 'non-finite Supervisor observation')
        r['time_ms'] = round(r['time']*1000)
        r['reconstructed_roll'] = math.atan2(r['r7'], r['r8'])
        r['reconstructed_pitch'] = math.asin(max(-1., min(1., -r['r6'])))
        rows.append(r)
    require(len(rows) == provenance['window']['rows'] and
            all(b['time_ms']-a['time_ms'] == 8 for a, b in zip(rows, rows[1:])), 'sampling continuity')
    by_time = {r['time_ms']: r for r in rows}
    after = [r for r in rows if r['time_ms'] >= deadline]
    crossing = next(r for r in after if max(abs(r['reconstructed_roll']), abs(r['reconstructed_pitch'])) > 1.2)
    near_ground = next(r for r in after if r['z'] < .04)
    reversal = next(r for r in after if r['time_ms'] > near_ground['time_ms'] and r['vz'] > 0)
    def observation(r):
        return {k: r[k] for k in ('time_ms', 'x', 'y', 'z', 'vx', 'vy', 'vz',
                                  'reconstructed_roll', 'reconstructed_pitch')}
    result = {
        'claim': 'archive integrity and Supervisor chronology, not consumed IMU or closed-loop correction',
        'original_archive_verified': bool(args.archive),
        'admission_ms': start, 'deadline_ms': deadline,
        'action_timeout_eligible_only_after_ms': deadline+25000,
        'first_reconstructed_attitude_crossing': observation(crossing),
        'first_z_below_004': observation(near_ground),
        'vertical_velocity_reversal_near_ground': observation(reversal),
        'chronology': [observation(by_time[t]) for t in
                       (226288, 226800, 227032, 227368, 227384, 227392, 227400, 227616, 227624, 227632, 228000)],
        'horizontal_displacement_deadline_to_227384_m': math.hypot(
            by_time[227384]['x']-by_time[deadline]['x'], by_time[227384]['y']-by_time[deadline]['y']),
        'exact_refusal_disjunct': 'UNPROVEN: consumed samples, guard timestamp and motor commands absent',
        'contact_time': 'unmeasured; velocity reversal is not a contact-point observation',
        'native_correction_trials': 0,
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    analyze()
