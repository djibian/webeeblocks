"""Describe actual Runtime samples; fail on incomplete or inconsistent input."""
import json
import math
from pathlib import Path
import re
import sys


def fields(text):
    result = {}
    for key, value in re.findall(r'(\w+)=([^ ]+)', text):
        parts = value.strip().split(',')
        result[key] = [float(x) for x in parts] if len(parts) > 1 else float(parts[0])
    return result


def summarize(log):
    resets = []
    current = None
    seen_ids = set()
    for line in log.splitlines():
        if ' RESET_PHASE_BEGIN ' in line:
            if current is not None:
                raise ValueError('RESET missing terminal observation')
            begin = fields(line)
            if begin['id'] in seen_ids:
                raise ValueError('duplicate RESET identity')
            seen_ids.add(begin['id'])
            current = {'begin': begin, 'samples': [], 'stable': -1.0}
        elif ' RESET_PHASE_SAMPLE ' in line:
            if current is None:
                raise ValueError('sample without RESET receipt')
            row = fields(line)
            if row['id'] != current['begin']['id']:
                raise ValueError('wrong RESET identity')
            if row['dt'] <= 0 or any(not math.isfinite(x) for value in row.values() for x in (value if isinstance(value,list) else [value])):
                raise ValueError('non-finite/invalid RESET sample')
            if not math.isclose(row['stable_since'],current['stable'],abs_tol=1e-8):
                raise ValueError('inconsistent stable window state')
            samples = current['samples']
            if samples and row['time'] <= samples[-1]['time']:
                raise ValueError('non-increasing sample time')
            if not math.isclose(row['elapsed'], row['time'] - current['begin']['time'], abs_tol=2e-8):
                raise ValueError('inconsistent elapsed time')
            if not all(math.isclose(v, (p-q)/row['dt'], abs_tol=1e-6)
                       for v,p,q in zip(row['velocity'],row['position'],row['previous'])):
                raise ValueError('inconsistent GPS difference')
            origin=current['begin']['origin']; angles=current['begin']['origin_rpy']
            pose = (all(abs(row['position'][i]-origin[i]) < tol for i,tol in enumerate((.03,.03,.05)))
                    and abs(row['rpy'][0]-angles[0]) < math.pi/90
                    and abs(row['rpy'][1]-angles[1]) < math.pi/90
                    and abs(math.remainder(row['rpy'][2]-angles[2],2*math.pi)) < math.pi/90)
            motion = math.hypot(*row['velocity'][:2]) < .12 and abs(row['velocity'][2]) < .15 and abs(row['gyro'][2]) < .10
            if bool(row['pose_ready']) != pose or bool(row['motion_ready']) != motion:
                raise ValueError('logged predicate differs from original formula')
            if pose and motion:
                if current['stable'] < 0: current['stable'] = row['time']
            else:
                current['stable'] = -1.0
            samples.append(row)
        elif current is not None and re.search(r' RESPONSE '+str(int(current['begin']['id']))+r' (OK|ERR RESET_TIMEOUT)$',line):
            current['terminal'] = line
            if not current['samples']:
                raise ValueError('RESET has no samples')
            if line.endswith(' OK') and (current['stable'] < 0 or current['samples'][-1]['time'] - current['stable'] < .25-1e-8):
                raise ValueError('ACK without measured stable window')
            resets.append(current); current=None
    if current is not None or not resets:
        raise ValueError('missing/incomplete RESET evidence')
    summaries=[]
    for case in resets:
        rows=case['samples']; last_bad=max((i for i,r in enumerate(rows) if not(r['pose_ready'] and r['motion_ready'])),default=-1)
        summaries.append({'id':int(case['begin']['id']), 'begin_time':case['begin']['time'],
            'terminal':case['terminal'], 'samples':len(rows),
            'last_sample_elapsed':rows[-1]['elapsed'],
            'pose_bad':sum(not r['pose_ready'] for r in rows),
            'motion_bad':sum(not r['motion_ready'] for r in rows),
            'last_bad_elapsed':rows[last_bad]['elapsed'] if last_bad>=0 else None,
            'first_three_samples':rows[:3],
            'final_stable_span':rows[-1]['time']-rows[last_bad+1]['time'] if last_bad+1<len(rows) else 0})
    return {'scope':'diagnostic observations only; no cause or health claim', 'resets':summaries}

if __name__=='__main__':
    print(json.dumps(summarize(Path(sys.argv[1]).read_text()),indent=2))
