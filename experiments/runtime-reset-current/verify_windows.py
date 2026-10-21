"""Reassemble, hash and inspect the explicitly partial native RESET archive."""
import gzip
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
DIRECT=HERE/'evidence/direct-windows'

def main():
    manifest=json.loads((DIRECT/'WINDOWS.json').read_text())
    results=json.loads((HERE/'DIRECT_RESULTS.json').read_text())
    samples={}
    for name,record in manifest['files'].items():
        pieces=[]
        for part in record['parts']:
            data=(DIRECT/part['name']).read_bytes()
            if len(data)!=part['bytes'] or hashlib.sha256(data).hexdigest()!=part['sha256']:
                raise ValueError('invalid archive part '+part['name'])
            pieces.append(data)
        data=b''.join(pieces)
        if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
            raise ValueError('invalid complete compressed subset '+name)
        rows=[json.loads(line) for line in gzip.decompress(data).splitlines()]
        samples[name]={round(row['time'],9):row for row in rows if row['type']=='sample'}
    physics=samples['physics-state.jsonl.windows.gz']
    for case in results['resets']:
        receipt=physics[round(case['begin_time'],9)]
        if receipt['motor_current']!=case['receipt_current']:
            raise ValueError('receipt current disagrees with raw native subset')
        if sum(receipt['propeller_thrust'])!=case['receipt_total_thrust']:
            raise ValueError('receipt thrust disagrees with raw native subset')
    print('Verified original-line subsets and all 14 native receipt currents/thrusts; full trajectory remains in artifact12303527298.')

if __name__=='__main__':main()
