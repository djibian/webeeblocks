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
from tools.ci.webots_startup_diagnostics import StartupEvidence
OUT=ROOT/'ci-artifacts/grand-prix-u'

def has_native_land_completion(text):
    # Touchdown/coasting is not the terminal LAND response or its stable window.
    return 'WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1' in text.splitlines()

def validate_timeout_probe(rows, text):
    """Expire first; distinguish fenced descent from confirmed RESET recovery.

    The native pose/gyro/stability probes independently establish the authority
    boundary. This trajectory probe must not mistake its later legal recovery
    for an expired attempt accepting continuation commands.
    """
    for command in ('COMPLETE','FAILURE','MOVE'):
        if not any(e['event']=='late-command-rejected' and
                   e['detail']=={'command':command,'code':'TIME_LIMIT'} for e in rows):
            raise RuntimeError('late command not rejected: '+command)
    if any(e['event'] in ('late-command-accepted','late-stop-accepted','late-outcome-error') for e in rows):
        raise RuntimeError('expired attempt continuation accepted or outcome lost')
    if not any(e['event']=='late-stop-rejected' and e['detail']=={'code':'TIME_LIMIT'} for e in rows):
        raise RuntimeError('late STOP not rejected')
    outcomes=[i for i,e in enumerate(rows) if e['event']=='late-outcome-read' and e['detail']=={'status':'not-achieved'}]
    requests=[(i,re.fullmatch(r'WEBEEBLOCKS_RUNTIME_V2 REQUEST (\d+) RESET',e['detail']))
              for i,e in enumerate(rows) if e['event']=='request' and isinstance(e['detail'],str)]
    resets=[(i,m.group(1)) for i,m in requests if m]
    if len(outcomes)!=1 or len(resets)!=1 or outcomes[0]>=resets[0][0]:
        raise RuntimeError('missing failed outcome before the sole recovery RESET')
    reset_index,reset_id=resets[0]
    recovery=rows[reset_index+1:]
    accepted=[e for e in recovery if e['event']=='recovery-reset-accepted']
    rejected=[e for e in recovery if e['event']=='recovery-reset-rejected']
    if len(accepted)+len(rejected)!=1:
        raise RuntimeError('ambiguous recovery RESET result')
    if rejected:
        if rejected[0]['detail']!={'code':'TIME_LIMIT'}:
            raise RuntimeError('unexpected pre-pose RESET rejection')
        if any(e['event'].startswith('recovery-outcome') or e['event']=='recovery-stale-outcome' for e in recovery):
            raise RuntimeError('continued after refused RESET')
        return
    # The real runtime emits TRACE LAND at forced-LAND completion and TRACE RESET
    # only after its complete post-teleport native pose/stability window.
    land=text.find('WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1')
    reset=text.find('WEBEEBLOCKS_RUNTIME_V2 TRACE RESET ')
    ack=text.find(f'WEBEEBLOCKS_RUNTIME_V2 RESPONSE {reset_id} OK')
    if land<0 or reset<=land or ack<=reset:
        raise RuntimeError('RESET accepted without native LAND then reset completion')
    if any(e['event']=='recovery-stale-outcome' for e in recovery) or not any(
            e['event']=='recovery-outcome-error' and e['detail']=={'code':'OUTCOME_UNAVAILABLE'} for e in recovery):
        raise RuntimeError('confirmed RESET did not revoke the old outcome')

def stop_groups(children):
    for child in reversed(children):
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()

def native_webots_launch(home, port, target):
    """Use minimized R2025a GUI for CI's observed pre-READY Qt crash (#665).

    The R2025a world-loading progress-dialog constructor skips minimized windows.
    Preserve Fast/no-rendering, the real world, port, runtime and mission oracles.
    This is a bounded mitigation hypothesis, not root-cause proof.
    """
    return [str(home/'webots'),'--stdout','--stderr','--batch','--mode=fast',
            '--no-rendering','--minimize','--port='+str(port),str(target)]

def trial(home,seed=4,side=2.,mode='witness',tcp=False,require_success=True,sequence_index=1,*,camera_probe=None):
    layout=generate(seed,side);token=uuid.uuid4().hex[:10]
    out=OUT/f'{layout.identifier}-{mode}-{token}';out.mkdir(parents=True,exist_ok=False)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    events=out/'events.jsonl'
    source=world_text(layout,controller='<extern>' if tcp else 'grand_prix_u_flight',window='<none>',evaluator=True)
    if tcp:source=source.replace('controller "grand_prix_u_evaluator"','controller "<extern>"')
    if camera_probe is not None:
        if tcp or camera_probe not in ('static','tracking'):
            raise ValueError('camera contrast requires a native in-process static/tracking world')
        fields='follow "Crazyflie WebeeBlocks" followType "Tracking Shot" followSmoothness 0.20 '
        if source.count(fields)!=1:
            raise RuntimeError('camera contrast requires the exact production Viewpoint')
        if camera_probe=='static':
            source=source.replace(fields,'')
    target=ROOT/f'worlds/ci_gp_u_flight_{token}.wbt'
    target.write_text(source.replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/','webots://'))
    (out/'layout.json').write_text(json.dumps(dataclasses.asdict(layout),indent=2)+'\n')
    (out/'world.wbt').write_text(target.read_text())
    env=os.environ.copy();env.update(WEBOTS_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='true',
        WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',WEBEEBLOCKS_CI_ARTIFACT_DIR=str(out))
    # Webots/Qt requires private runtime directories. Inside Docker these are
    # root-owned mode 0700, so putting them in OUT prevents the host artifact
    # uploader from even walking the evidence tree (observed in 38473674859).
    # Keep disposable application state separate from the retained witnesses.
    runtime_state=tempfile.TemporaryDirectory(prefix='gp-u-runtime-')
    for variable,folder in (('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime')):
        directory=Path(runtime_state.name)/folder;directory.mkdir(mode=0o700);env[variable]=str(directory)
    env['LP_NUM_THREADS']='1'
    if tcp:
        env['LD_LIBRARY_PATH']=str(home/'lib/webots')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    children=[];streams=[];startup=None
    try:
        with (out/'webots.log').open('w') as log:
            launch=native_webots_launch(home,port,target)
            if not tcp:
                xvfb=shutil.which('xvfb-run')
                if not xvfb:raise RuntimeError('fresh Xvfb display required for each native trial')
                launch=[xvfb,'-a',*launch]
            startup=StartupEvidence(out,sequence_index,launch,env,cwd=ROOT)
            webots=subprocess.Popen(launch,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            children.append(webots);limit=time.monotonic()+30
            while webots.poll() is None and time.monotonic()<limit:
                startup.observe(webots)
                text=(out/'webots.log').read_text()
                if tcp and text.count(f'Waiting for local or remote connection on port {port} ')>=2:break
                if not tcp and 'WEBEEBLOCKS_RUNTIME_V2 READY' in text:break
                time.sleep(.1)
            else:
                startup.failure(webots,home,out/'webots.log')
                raise RuntimeError('native readiness not established: '+str(out))
            startup.ready(webots,'TCP_PORTS_WAITING' if tcp else 'RUNTIME_READY')
            if camera_probe is not None:
                # READY is necessary, but a Webots process dying just after it
                # must not be counted as a valid native camera startup.
                until=time.monotonic()+0.6
                while time.monotonic()<until:
                    if webots.poll() is not None:
                        raise RuntimeError('camera native process exited after READY: '+str(out))
                    time.sleep(.1)
                startup_log=(out/'webots.log').read_text()
                if startup_log.count('WEBEEBLOCKS_RUNTIME_V2 READY')!=1 or 'Segmentation fault' in startup_log:
                    raise RuntimeError('camera READY/liveness contradiction: '+str(out))
                record={'camera':camera_probe,'seed':seed,'side':side,
                        'configuration':layout.identifier,'ready':True,
                        'post_ready_alive':True,
                        'claim':'R2025a-native-startup-and-liveness-only'}
                (out/'camera-startup.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
                print('GP_U_CAMERA_STARTUP '+json.dumps(record,sort_keys=True),flush=True)
                return record
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
            children.append(node);node.wait(timeout=600)
            limit=time.monotonic()+30
            while time.monotonic()<limit and webots.poll() is None:
                text=(out/'webots.log').read_text()
                if tcp:text+=''.join(Path(s.name).read_text() for s in streams)
                if 'GP_U_RESULT ' in text and ('GP_U_DEADLINE ' not in text or has_native_land_completion(text)):break
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
        if result is None or any(record!=result for record in records if mode!='reset' or record['attempt']==1):raise RuntimeError('native result missing/inconsistent: '+str(out))
        second=None
        if mode=='reset':
            second=json.loads((out/'native-result-2.json').read_text())
            if (result['status']!='achieved' or second['status']!='achieved' or second['attempt']!=2 or
                second['configuration']!=layout.identifier or second['seconds']>=210 or
                any(record!=second for record in records if record['attempt']==2) or
                not any(e['event']=='reset-completed' for e in rows) or
                not any(e['event']=='second-outcome' and e['detail']['status']=='achieved' for e in rows)):
                raise RuntimeError('second identical program after native RESET failed')
        fatal=[e for e in rows if e['event'] in ('wall-timeout','transport-error')]
        errors=[e for e in rows if e['event']=='error']
        if fatal:raise RuntimeError('transport/preparation failed: '+str(out))
        if mode in ('witness','reset') and require_success and (errors or result['status']!='achieved'):
            raise RuntimeError('witness refuted: '+str(result)+' '+str(errors)+' '+str(out))
        expected={'short':'wrong-landing','wrong-landing':'wrong-landing','low-outside':'low-outside-zone'}
        if mode=='collision' and (result['status']!='not-achieved' or result['reason'] not in ('envelope-contact','device-contact')):
            raise RuntimeError('collision accepted: '+str(result))
        if mode=='reverse' and (result['status']!='not-achieved' or result['reason']!='reverse-crossing' or result['crossings']!=1):
            raise RuntimeError('reverse probe did not complete then reverse a gate: '+str(result))
        if mode=='unavailable' and (result['status']!='not-achieved' or not errors or not any(e['event']=='injected-range' for e in rows)):
            raise RuntimeError('unavailable measurement not rejected')
        if mode in expected and (result['status']!='not-achieved' or result['reason']!=expected[mode]):
            raise RuntimeError('negative accepted/wrong rejection: '+str(result))
        if mode.startswith('timeout') or result['reason']=='time-limit':
            admitted=[int(line.split('start_ms=',1)[1]) for line in text.splitlines() if line.startswith('GP_U_ADMISSION ')]
            deadline=[int(line.split('time_ms=',1)[1].split()[0]) for line in text.splitlines() if line.startswith('GP_U_DEADLINE ')]
            if len(admitted)!=1 or len(deadline)!=1 or deadline[0]-admitted[0]!=210000:
                raise RuntimeError('deadline not exactly 210 s: '+str(out))
            if 'command=LAND' not in text or not has_native_land_completion(text) or result['status']!='not-achieved' or result['reason']!='time-limit':
                raise RuntimeError('missing independent forced LAND/failure')
            if not any(e['event']=='error' and e['detail']['code']=='TIME_LIMIT' for e in rows):raise RuntimeError('program not interrupted')
            if mode.startswith('timeout'):validate_timeout_probe(rows,text)
        if result['configuration']!=layout.identifier or result['attempt']!=1:raise RuntimeError('wrong native subject')
        programs=[e['detail'] for e in rows if e['event']=='program']
        if len(programs)!=1:raise RuntimeError('missing exact shared-interpreter AST')
        if second is not None:result['second_attempt']=second
        result['ast_sha256']=hashlib.sha256(json.dumps(programs[0],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        result['claim']='native-shared-interpreter';result['webots_version']='R2025a';result['mode']=mode
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('GP_U_NATIVE '+json.dumps(result,sort_keys=True),flush=True)
        return result
    finally:
        stop_groups(children)
        if startup is not None and children:
            startup.after_cleanup(children[0].pid)
        for stream in streams:stream.close()
        runtime_state.cleanup()
        (out/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
           for p in out.iterdir() if p.is_file() and p.name!='sha256.json'},indent=2)+'\n')
        target.unlink(missing_ok=True);target.with_name('.'+target.stem+'.wbproj').unlink(missing_ok=True)

def native_container_command(cid, assets, node, command, core_options=()):
    """Enable Docker's PID 1 reaper for adopted Webots/Xvfb children.

    The previous PID 1 (timeout) retained zombies between native trials;
    this is process hygiene, not a claim to repair the Webots SIGSEGV.
    """
    return ['docker','run','--rm','--init',*core_options,'--cidfile',str(cid),'--entrypoint','/bin/bash',
            '-e','WEBOTS_HOME=/usr/local/webots',
            '-v',f'{ROOT}:/workspace','-v',f'{assets/"projects"}:/usr/local/webots/projects:ro',
            '-v',f'{Path(node).resolve()}:/usr/local/bin/node:ro','-w','/workspace',IMAGE,'-c',command]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--native',action='store_true');parser.add_argument('--tcp',action='store_true')
    parser.add_argument('--suite',choices=('short','timeout','timeout-gate','wrong-landing','low-outside','collision','reverse','unavailable','reset','witness','all','sizes','camera-contrast'),default='all')
    parser.add_argument('--seed',type=int,default=4);parser.add_argument('--side',type=float,default=2.)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    print('GP_U_ENTRY native='+str(args.native)+' suite='+args.suite,flush=True)
    if not args.native:
        if not shutil.which('docker'):raise RuntimeError('required R2025a Docker runtime unavailable')
        from tools.ci.run_grand_prix_u_core_capture import core_mount
        core_options=core_mount(os.environ.get('WEBEEBLOCKS_GP_CORE_DIR'))
        subprocess.run(['bash',str(ROOT/'tools/prepare_runtime_v2.sh')],check=True)
        # Fail before Docker if the actual pupil .wbb cannot load, preflight,
        # compile and round-trip in the pinned production Blockly.
        subprocess.run(['node',str(ROOT/'tools/grand_prix/pupil_workspace_u.js')],check=True)
        assets=ROOT/'.ci-grand-prix-u-webots'
        if not assets.exists():
            subprocess.run(['git','clone','--depth=1','--filter=blob:none','--sparse','--branch','R2025a','https://github.com/cyberbotics/webots.git',str(assets)],check=True)
            subprocess.run(['git','-C',str(assets),'sparse-checkout','set','projects/robots/bitcraze/crazyflie','projects/objects/backgrounds','projects/objects/floors','projects/appearances','projects/default'],check=True)
        if subprocess.check_output(['git','-C',str(assets),'rev-parse','HEAD'],text=True).strip()!=SOURCE:raise RuntimeError('wrong R2025a assets')
        subprocess.run(['docker','pull',IMAGE],check=True)
        node=shutil.which('node')
        if not node:raise RuntimeError('Node 22+ required for shared WWI backend')
        with tempfile.TemporaryDirectory(prefix='gp-u-native-') as tmp:
            cid=Path(os.environ['WEBEEBLOCKS_GP_CONTAINER_CIDFILE']) if core_options else Path(tmp)/'container.cid'
            command="set -eu\npython3 -u -c 'import sys; print(\"GP_U_CONTAINER_PYTHON\",sys.version,flush=True)'\ntimeout -k 2s 10s /usr/local/bin/node --version\ntimeout -k 5s 1400s python3 -u tools/ci/run_grand_prix_u_prototype.py --native --suite "+args.suite+' --seed '+str(args.seed)+' --side '+str(args.side)
            try:
                with (OUT/'docker.log').open('w') as log:
                    log.write('GP_U_CONTAINER_START '+IMAGE+'\n');log.flush()
                    try:
                        subprocess.run(native_container_command(cid,assets,node,command,core_options),
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1500)
                    except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
                        log.flush()
                        print((OUT/'docker.log').read_text()[-16000:],file=sys.stderr,flush=True)
                        raise
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
    # Native controlled contrast for #646: same seed/world/controller and pinned
    # software renderer, with only the Viewpoint follow fields differing.
    # This is diagnostic startup evidence, never an activity/mission PASS.
    if args.suite=='camera-contrast' and args.tcp:
        raise ValueError('camera contrast requires an in-process Webots controller')
    if args.suite in ('all','camera-contrast') and not args.tcp:
        contrast=[]
        # Bounded order crossover: seed 1, same controller and renderer.
        # A crash fails closed immediately with per-attempt native artifacts.
        for sequence,camera in enumerate(('static','tracking','tracking','static'),1):
            record=trial(home,1,args.side,
                         'camera-'+camera+'-crossover-'+str(sequence),
                         args.tcp,sequence_index=sequence,camera_probe=camera)
            record['sequence']=sequence
            contrast.append(record)
            (OUT/'camera-comparison.json').write_text(json.dumps(contrast,indent=2)+'\n')
        if args.suite=='camera-contrast':
            return
    cases=[(args.seed,args.side,args.suite)]
    if args.suite=='all':cases=[(4,args.side,'short'),(4,args.side,'timeout'),(0,args.side,'timeout-gate'),(1,args.side,'wrong-landing'),(0,args.side,'low-outside'),(0,args.side,'collision'),(0,args.side,'reverse'),(0,args.side,'unavailable'),(0,args.side,'witness'),(0,args.side,'reset')]+[(s,args.side,'witness') for s in (1,3,4,14,15,17)]
    if args.suite=='sizes':cases=[(4,size,'witness') for size in (2.,3.,4.,5.,6.)]
    summaries=[];digest=None
    for sequence_index,(seed,side,mode) in enumerate(cases,1):
        result=trial(home,seed,side,mode,args.tcp,require_success=args.suite!='sizes',sequence_index=sequence_index)
        if mode in ('witness','reset'):
            if digest is not None and digest!=result['ast_sha256']:raise RuntimeError('AST changed between configurations or RESET')
            digest=result['ast_sha256']
        summaries.append(result)
        (OUT/('sizes.json' if args.suite=='sizes' else 'campaign.json')).write_text(json.dumps(summaries,indent=2)+'\n')
if __name__=='__main__':main()
