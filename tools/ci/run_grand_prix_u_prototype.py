#!/usr/bin/env python3
"""Real-R2025a U integration. Native evidence only; no hardware checkpoint."""
import argparse
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.grand_prix.layout_u import generate,world_text
from tools.ci.run_grand_prix_u_geometry import IMAGE,SOURCE
OUT=ROOT/'ci-artifacts/grand-prix-u'

def stop_groups(children):
    for child in reversed(children):
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()

def trial(home,seed=4,side=2.,mode='witness',tcp=False,require_success=True):
    layout=generate(seed,side);token=uuid.uuid4().hex[:10]
    out=OUT/f'{layout.identifier}-{mode}-{token}';out.mkdir(parents=True,exist_ok=False)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    events=out/'events.jsonl'
    source=world_text(layout,controller='<extern>' if tcp else 'grand_prix_u_flight',window='<none>',evaluator=True)
    if tcp:source=source.replace('controller "grand_prix_u_evaluator"','controller "<extern>"')
    target=ROOT/f'worlds/ci_gp_u_flight_{token}.wbt'
    target.write_text(source.replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/','webots://'))
    (out/'layout.json').write_text(json.dumps(dataclasses.asdict(layout),indent=2)+'\n')
    (out/'world.wbt').write_text(target.read_text())
    env=os.environ.copy();env.update(WEBOTS_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='true',
        WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',WEBEEBLOCKS_CI_ARTIFACT_DIR=str(out))
    if tcp:
        env['LD_LIBRARY_PATH']=str(home/'lib/webots')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    children=[];streams=[]
    try:
        with (out/'webots.log').open('w') as log:
            webots=subprocess.Popen([str(home/'webots'),'--stdout','--stderr','--batch','--mode=fast',
                '--no-rendering','--port='+str(port),str(target)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            children.append(webots);limit=time.monotonic()+30
            while webots.poll() is None and time.monotonic()<limit:
                text=(out/'webots.log').read_text()
                if tcp and text.count(f'Waiting for local or remote connection on port {port} ')>=2:break
                if not tcp and 'WEBEEBLOCKS_RUNTIME_V2 READY' in text:break
                time.sleep(.1)
            else:raise RuntimeError('native readiness not established: '+str(out))
            if tcp:
                for name,path,args in (
                  ('Crazyflie WebeeBlocks',ROOT/'controllers/grand_prix_u_flight/grand_prix_u_flight',[]),
                  ('Évaluateur Grand Prix',ROOT/'controllers/grand_prix_u_evaluator/grand_prix_u_evaluator.py',[str(seed),str(side)])):
                    stream=(out/('flight.log' if not args else 'evaluator.log')).open('w');streams.append(stream)
                    children.append(subprocess.Popen([str(home/'webots-controller'),'--protocol=tcp','--ip-address=127.0.0.1',
                       '--port='+str(port),'--robot-name='+name,str(path),*args],env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True))
            node_log=(out/'node.log').open('w');streams.append(node_log)
            node=subprocess.Popen(['node',str(ROOT/'tools/ci/grand_prix_u_node_probe.js'),str(port),mode,str(events)],
                cwd=ROOT,env=env,stdout=node_log,stderr=subprocess.STDOUT,start_new_session=True)
            children.append(node);node.wait(timeout=300)
            limit=time.monotonic()+30
            while time.monotonic()<limit and webots.poll() is None:
                text=(out/'webots.log').read_text()
                if tcp:text+=''.join(Path(s.name).read_text() for s in streams)
                if 'GP_U_RESULT ' in text and (not mode.startswith('timeout') or 'TRACE LAND' in text):break
                time.sleep(.1)
        text=(out/'webots.log').read_text()
        if tcp:text+=(out/'flight.log').read_text()+(out/'evaluator.log').read_text()
        native_errors=[line for line in text.splitlines() if line.startswith('ERROR:')]
        if tcp:native_errors=[line for line in native_errors if not (line.startswith('ERROR: Cannot listen to the local server (server name = ') and 'QLocalServer::listen: Unknown error 1' in line)]
        if native_errors or 'Traceback (most recent call last)' in text:raise RuntimeError('native error; see '+str(out))
        rows=[json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
        records=[json.loads(line.split('GP_U_RESULT ',1)[1]) for line in text.splitlines() if line.startswith('GP_U_RESULT ')]
        file=out/'native-result-1.json'
        result=json.loads(file.read_text()) if file.exists() else (records[0] if len(records)==1 else None)
        if result is None or any(record!=result for record in records):raise RuntimeError('native result missing/inconsistent: '+str(out))
        fatal=[e for e in rows if e['event'] in ('wall-timeout','transport-error')]
        errors=[e for e in rows if e['event']=='error']
        if fatal:raise RuntimeError('transport/preparation failed: '+str(out))
        if mode=='witness' and require_success and (errors or result['status']!='achieved'):
            raise RuntimeError('witness refuted: '+str(result)+' '+str(errors)+' '+str(out))
        expected={'short':'wrong-landing','wrong-landing':'wrong-landing','low-outside':'low-outside-zone'}
        if mode in ('collision','reverse') and (result['status']!='not-achieved' or result['reason'] not in ('envelope-contact','device-contact','reverse-crossing')):
            raise RuntimeError('incorrect crossing/collision accepted: '+str(result))
        if mode=='unavailable' and (result['status']!='not-achieved' or not errors or not any(e['event']=='injected-range' for e in rows)):
            raise RuntimeError('unavailable measurement not rejected')
        if mode in expected and (result['status']!='not-achieved' or result['reason']!=expected[mode]):
            raise RuntimeError('negative accepted/wrong rejection: '+str(result))
        if mode.startswith('timeout'):
            admitted=[int(line.split('start_ms=',1)[1]) for line in text.splitlines() if line.startswith('GP_U_ADMISSION ')]
            deadline=[int(line.split('time_ms=',1)[1].split()[0]) for line in text.splitlines() if line.startswith('GP_U_DEADLINE ')]
            if len(admitted)!=1 or len(deadline)!=1 or deadline[0]-admitted[0]!=210000:
                raise RuntimeError('deadline not exactly 210 s: '+str(out))
            if 'command=LAND' not in text or 'TRACE LAND' not in text or result['status']!='not-achieved' or result['reason']!='time-limit':
                raise RuntimeError('missing independent forced LAND/failure')
            if not any(e['event']=='error' and e['detail']['code']=='TIME_LIMIT' for e in rows):raise RuntimeError('program not interrupted')
            for command in ('COMPLETE','FAILURE','RESET','MOVE'):
                if not any(e['event']=='late-command-rejected' and e['detail']['command']==command and e['detail']['code']=='TIME_LIMIT' for e in rows):
                    raise RuntimeError('late command not rejected: '+command)
            if not any(e['event']=='late-stop-rejected' and e['detail']['code']=='TIME_LIMIT' for e in rows):raise RuntimeError('late STOP not rejected')
        if result['configuration']!=layout.identifier or result['attempt']!=1:raise RuntimeError('wrong native subject')
        programs=[e['detail'] for e in rows if e['event']=='program']
        if len(programs)!=1:raise RuntimeError('missing exact shared-interpreter AST')
        result['ast_sha256']=hashlib.sha256(json.dumps(programs[0],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        result['claim']='native-shared-interpreter';result['webots_version']='R2025a';result['mode']=mode
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        (out/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
           for p in out.iterdir() if p.is_file() and p.name!='sha256.json'},indent=2)+'\n')
        print('GP_U_NATIVE '+json.dumps(result,sort_keys=True),flush=True)
        return result
    finally:
        stop_groups(children)
        for stream in streams:stream.close()
        target.unlink(missing_ok=True);target.with_name('.'+target.stem+'.wbproj').unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--native',action='store_true');parser.add_argument('--tcp',action='store_true')
    parser.add_argument('--suite',choices=('short','timeout','timeout-gate','wrong-landing','low-outside','collision','reverse','unavailable','witness','all','sizes'),default='all')
    parser.add_argument('--seed',type=int,default=4);parser.add_argument('--side',type=float,default=2.)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    print('GP_U_ENTRY native='+str(args.native)+' suite='+args.suite,flush=True)
    if not args.native:
        if not shutil.which('docker'):raise RuntimeError('required R2025a Docker runtime unavailable')
        assets=ROOT/'.ci-grand-prix-u-webots'
        if not assets.exists():
            subprocess.run(['git','clone','--depth=1','--filter=blob:none','--sparse','--branch','R2025a','https://github.com/cyberbotics/webots.git',str(assets)],check=True)
            subprocess.run(['git','-C',str(assets),'sparse-checkout','set','projects/robots/bitcraze/crazyflie','projects/objects/backgrounds','projects/objects/floors','projects/appearances','projects/default'],check=True)
        if subprocess.check_output(['git','-C',str(assets),'rev-parse','HEAD'],text=True).strip()!=SOURCE:raise RuntimeError('wrong R2025a assets')
        subprocess.run(['docker','pull',IMAGE],check=True)
        node=shutil.which('node')
        if not node:raise RuntimeError('Node 22+ required for shared WWI backend')
        with tempfile.TemporaryDirectory(prefix='gp-u-native-') as tmp:
            cid=Path(tmp)/'container.cid'
            command="set -eu\npython3 -u -c 'import sys; print(\"GP_U_CONTAINER_PYTHON\",sys.version,flush=True)'\ntimeout -k 2s 10s /usr/local/bin/node --version\ntimeout -k 5s 1400s xvfb-run -a python3 -u tools/ci/run_grand_prix_u_prototype.py --native --suite "+args.suite+' --seed '+str(args.seed)+' --side '+str(args.side)
            try:
                with (OUT/'docker.log').open('w') as log:
                    log.write('GP_U_CONTAINER_START '+IMAGE+'\n');log.flush()
                    subprocess.run(['docker','run','--rm','--cidfile',str(cid),'--entrypoint','/bin/bash','-e','WEBOTS_HOME=/usr/local/webots',
                       '-v',f'{ROOT}:/workspace','-v',f'{assets/"projects"}:/usr/local/webots/projects:ro',
                       '-v',f'{Path(node).resolve()}:/usr/local/bin/node:ro','-w','/workspace',IMAGE,'-c',command],
                       stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1500)
            finally:
                if cid.exists():
                    identity=cid.read_text().strip()
                    if not re.fullmatch('[0-9a-f]{64}',identity):raise RuntimeError('invalid owned container identity')
                    state=subprocess.run(['docker','inspect','--format','{{.State.Running}}',identity],capture_output=True,text=True,timeout=10)
                    if state.returncode==0 and state.stdout.strip()=='true':
                        stopped=subprocess.run(['docker','stop','--time','5',identity],capture_output=True,text=True,timeout=20)
                        if stopped.returncode:raise RuntimeError('container retirement unproven')
        return
    home=Path(os.environ['WEBOTS_HOME'])
    if (home/'resources/version.txt').read_text().strip()!='R2025a':raise RuntimeError('wrong Webots version')
    subprocess.run([sys.executable,str(ROOT/'tools/grand_prix/prepare_u_runtime.py')],check=True)
    subprocess.run(['make','-C',str(ROOT/'controllers/grand_prix_u_flight')],check=True)
    cases=[(args.seed,args.side,args.suite)]
    if args.suite=='all':cases=[(4,2.,'short'),(4,2.,'timeout'),(0,2.,'timeout-gate'),(1,2.,'wrong-landing'),(0,2.,'low-outside'),(0,2.,'collision'),(0,2.,'reverse'),(0,2.,'unavailable')]+[(s,2.,'witness') for s in (0,1,4)]
    if args.suite=='sizes':cases=[(4,size,'witness') for size in (2.,3.,4.,5.,6.)]
    summaries=[];digest=None
    for seed,side,mode in cases:
        result=trial(home,seed,side,mode,args.tcp,require_success=args.suite!='sizes')
        if mode=='witness':
            if digest is not None and digest!=result['ast_sha256']:raise RuntimeError('AST changed between configurations/sizes')
            digest=result['ast_sha256']
        summaries.append(result)
        (OUT/('sizes.json' if args.suite=='sizes' else 'campaign.json')).write_text(json.dumps(summaries,indent=2)+'\n')
if __name__=='__main__':main()
