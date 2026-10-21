#!/usr/bin/env python3
"""One bounded ABBA protocol, isolated from product branches and CI Gate."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REF='149c0b61b48f335eb4cb925113ccc03afce80cca'
IMAGE='cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099'
ASSETS='c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b'
SOURCE=ROOT/'.land-causal-reference'
OUT=ROOT/'ci-artifacts/land-causal'
from instrument import instrument
from analyze import summarize, compare


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(folder):
    (folder/'causal-sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.iterdir() if p.is_file() and p.name!='causal-sha256.json'},indent=2)+'\n')


def native():
    home=Path(os.environ['WEBOTS_HOME'])
    if (home/'resources/version.txt').read_text().strip()!='R2025a':
        raise ValueError('wrong native Webots')
    sys.path.insert(0,str(SOURCE))
    prepare=load('land_prepare',SOURCE/'tools/grand_prix/prepare_u_runtime.py')
    prepare.prepare()
    instrument(SOURCE)
    subprocess.run(['make','-C',str(SOURCE/'controllers/grand_prix_u_flight')],check=True)
    for path in ('controllers/grand_prix_u_flight/build/runtime_u.c',
                 'controllers/grand_prix_u_flight/grand_prix_u_flight',
                 'controllers/grand_prix_u_evaluator/grand_prix_u_evaluator.py',
                 'controllers/crazyflie_square/pid_controller.c'):
        shutil.copy2(SOURCE/path, OUT/Path(path).name)
    runner=load('land_runner',SOURCE/'tools/ci/run_grand_prix_u_prototype.py')
    original_stop=runner.stop_groups

    def stop_with_coast(children):
        # Observe actual spin-down after ACK, before retiring the simulator.
        try:
            folders=list(runner.OUT.glob('*'))
            if folders:
                folder=folders[0]
                text=(folder/'webots.log').read_text()
                stops=[json.loads(l.split('GP_U_LAND_CONTROL ',1)[1]) for l in text.splitlines()
                       if l.startswith('GP_U_LAND_CONTROL ') and '"phase":"stop"' in l]
                if stops:
                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline:
                        file=folder/'causal-control.jsonl'
                        if file.exists():
                            with file.open('rb') as stream:
                                stream.seek(max(0,file.stat().st_size-8192))
                                lines=stream.read().decode().splitlines()[1:]
                            times=[json.loads(l)['time'] for l in lines if l.endswith('}')]
                            if times and max(times)>=stops[-1]['time_ms']/1000+3.032:
                                break
                        time.sleep(.1)
                    else: raise ValueError('native coast window not completed')
        finally:
            original_stop(children)
    runner.stop_groups=stop_with_coast
    records=[]
    for index,variant in enumerate(('A','B','B','A'),1):
        case=OUT/f'{index}-{variant}';case.mkdir()
        runner.OUT=case
        os.environ['GP_LAND_ABLATE']='1' if variant=='B' else '0'
        (case/'started.json').write_text(json.dumps(dict(index=index,variant=variant,reference=REF))+'\n')
        try:
            runner.trial(home,14,2.,'witness',False,require_success=False)
            folder=next(p for p in case.iterdir() if p.is_dir())
            record=summarize(folder,variant)
            records.append(record)
            (OUT/'observed.json').write_text(json.dumps(records,indent=2)+'\n')
            manifest(folder)
        except Exception as error:
            (case/'technical-failure.json').write_text(json.dumps(dict(error=str(error),
                stop='first technical failure; no replacement or retry'))+'\n')
            for folder in case.iterdir():
                if folder.is_dir():manifest(folder)
            raise
    pairs=[compare(records[0],records[1]),compare(records[3],records[2])]
    verdict='BOUNDED_SUPPORT' if all(p['supports_hypothesis'] for p in pairs) else 'INCONCLUSIVE_OR_REFUTED'
    (OUT/'comparison.json').write_text(json.dumps(dict(pairs=pairs,verdict=verdict,
        product_fix_validated=False,claim='bounded diagnostic only'),indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--native',action='store_true')
    args=parser.parse_args()
    if args.native:
        native();return
    OUT.mkdir(parents=True,exist_ok=False)
    shutil.copy2(HERE/'PROTOCOL.md',OUT/'PROTOCOL.md')
    if SOURCE.exists():raise ValueError('refuse reused experimental source or acquisition')
    subprocess.run(['git','fetch','origin',REF],cwd=ROOT,check=True)
    SOURCE.mkdir()
    archive=OUT/'reference.tar'
    with archive.open('wb') as stream:
        subprocess.run(['git','archive',REF],cwd=ROOT,stdout=stream,check=True)
    with tarfile.open(archive) as stream:stream.extractall(SOURCE)
    subprocess.run(['bash','tools/prepare_runtime_v2.sh'],cwd=SOURCE,check=True)
    assets=ROOT/'.land-causal-assets'
    subprocess.run(['git','clone','--depth=1','--filter=blob:none','--sparse','--branch','R2025a',
        'https://github.com/cyberbotics/webots.git',str(assets)],check=True)
    subprocess.run(['git','-C',str(assets),'sparse-checkout','set','projects/robots/bitcraze/crazyflie',
        'projects/objects/backgrounds','projects/objects/floors','projects/appearances','projects/default'],check=True)
    if subprocess.check_output(['git','-C',str(assets),'rev-parse','HEAD'],text=True).strip()!=ASSETS:
        raise ValueError('wrong native assets')
    subprocess.run(['docker','pull',IMAGE],check=True)
    (OUT/'provenance.json').write_text(json.dumps(dict(reference=REF,image=IMAGE,assets=ASSETS,
        experiment_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        protocol_sha256=hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest()),indent=2)+'\n')
    node=Path(shutil.which('node')).resolve()
    cid=OUT/'container.cid'
    try:
        with (OUT/'docker.log').open('w') as log:
            subprocess.run(['docker','run','--rm','--cidfile',str(cid),'--entrypoint','/bin/bash',
                '-e','WEBOTS_HOME=/usr/local/webots','-v',f'{ROOT}:/workspace',
                '-v',f'{assets/"projects"}:/usr/local/webots/projects:ro','-v',f'{node}:/usr/local/bin/node:ro',
                '-w','/workspace',IMAGE,'-c',
                'python3 -u experiments/grand-prix-land-causal/run.py --native'],
                stdout=log,stderr=subprocess.STDOUT,check=True,timeout=2100)
    finally:
        if cid.exists():
            identity=cid.read_text().strip()
            if not re.fullmatch('[0-9a-f]{64}',identity):raise ValueError('unknown container identity')
            state=subprocess.run(['docker','inspect','--format','{{.State.Running}}',identity],capture_output=True,text=True,timeout=10)
            if state.returncode==0 and state.stdout.strip()=='true':
                subprocess.run(['docker','stop','--time','5',identity],check=True,timeout=20)
        manifest(OUT)


if __name__=='__main__':main()
