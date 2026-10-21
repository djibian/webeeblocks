#!/usr/bin/env python3
"""Verify the stopped native observation. No simulation or controller execution."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import zipfile

HERE=Path(__file__).resolve().parent
DATA=HERE/'evidence'
sha=lambda data:hashlib.sha256(data).hexdigest()


def require(value,message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--original-zip',type=Path)
    args=parser.parse_args()
    manifest=json.loads((DATA/'sha256.json').read_text())
    for name,digest in manifest.items():
        require(sha((DATA/name).read_bytes())==digest,'retained hash: '+name)
    sources=json.loads((DATA/'sources.json').read_text())
    summary=json.loads((DATA/'summary.json').read_text())
    if args.original_zip:
        require(sha(args.original_zip.read_bytes())==sources['zip_sha256'],'ZIP digest')
        with zipfile.ZipFile(args.original_zip) as archive:
            require(archive.testzip() is None,'ZIP CRC')
            for prefix,name in (('', 'causal-sha256.json'),(sources['source_folder']+'/', 'causal-sha256.json')):
                for file,digest in json.loads(archive.read(prefix+name)).items():
                    require(sha(archive.read(prefix+file))==digest,'original hash: '+file)
            for part in sources['excerpts']:
                data=archive.read(sources['source_folder']+'/'+part['source'])
                require(sha(data)==part['source_sha256'],'excerpt source hash')
                retained=data[:part['header_bytes']]+data[part['byte_start']:part['byte_end_exclusive']]
                require(retained==(DATA/part['retained']).read_bytes(),'excerpt byte identity')
    rows=[{k:float(v) for k,v in row.items() if v!='' and k!='contact_points_xyz'}
          for row in csv.DictReader((DATA/'native-land-window.csv').open())]
    touch=next(r for r in rows if r['time']>=summary['land_start'] and r.get('contact_count',0)>0)
    post=[r for r in rows if r['time']>=touch['time']]
    require(touch==summary['first_contact'],'first contact')
    require(abs(max(math.hypot(r['vx'],r['vy']) for r in post)-summary['max_postcontact_xy_speed'])<1e-12,'speed')
    require(abs(max(math.hypot(r['x']-touch['x'],r['y']-touch['y']) for r in post)-summary['max_postcontact_displacement'])<1e-12,'displacement')
    require(rows[-1]['time']==summary['last_native_time'],'last sample')
    require(summary['retained_coast_seconds']<summary['required_coast_seconds'],'incomplete coast lost')
    require(json.loads((DATA/'native-result-1.json').read_text())==summary['outcome'],'native result')
    events=[json.loads(l) for l in (DATA/'events.jsonl').read_text().splitlines()]
    programs=[r['detail'] for r in events if r['event']=='program']
    require(len(programs)==1 and sha(json.dumps(programs[0],sort_keys=True,separators=(',',':')).encode())=='89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d','ordinary AST')
    controls=[json.loads(l) for l in (DATA/'control-land-window.jsonl').read_text().splitlines()]
    require(not any(r.get('ablation') for r in controls),'unexpected B data')
    failure=json.loads((DATA/'technical-failure.json').read_text())
    require('started.json/webots.log' in failure['error'],'technical failure lost')
    rotor=list(csv.DictReader((DATA/'rotors-switch-window.csv').open()))
    at=lambda t:next(r for r in rotor if abs(float(r['time'])-t)<1e-9)
    phase=lambda r:float(r['m1_z'])*float(r['m1_angle'])
    before=math.remainder(phase(at(17.792))-phase(at(17.784)),2*math.pi)/.008
    after=math.remainder(phase(at(17.800))-phase(at(17.792)),2*math.pi)/.008
    require(abs(abs(before)-49.92)<1e-6 and abs(after)<1e-9,'native rotor discontinuity')
    require(not summary['forces_observed'] and not summary['rotor_reconstruction_valid'],'invented force measurement')
    require(summary['native_processes_started']==1 and summary['native_processes_not_started']==['B1','B2','A2'],'campaign extended')
    require(not summary['defect_exercised'] and not summary['product_fix_validated'] and not summary['independent_go'],'invented qualification')
    print('Verified: one reference success; technical stop, invalid rotor measurement and missing B preserved; no repair established.')


if __name__=='__main__':main()
