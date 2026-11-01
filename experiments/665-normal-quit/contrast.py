"""One A/B native contrast, official pinned engine, same unavailable oracle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.ci import run_grand_prix_u_prototype as runner
from tools.ci.grand_prix_u_capture_seals import verify_new_capture_seals
OUT=ROOT/'ci-artifacts/665-normal-quit'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def native():
    home=Path(os.environ['WEBOTS_HOME'])
    if (home/'resources/version.txt').read_text().strip()!='R2025a':raise RuntimeError('wrong engine')
    runner.OUT=OUT/'trials';runner.OUT.mkdir(parents=True,exist_ok=False)
    subprocess.run([sys.executable,'tools/grand_prix/prepare_u_runtime.py'],cwd=ROOT,check=True)
    subprocess.run(['make','-C','controllers/grand_prix_u_flight'],cwd=ROOT,check=True)
    before={p.name for p in runner.OUT.iterdir()};expected=set();rows=[];signals=[]
    identities={str(p.relative_to(home)):digest(p) for p in [home/'bin/webots-bin',home/'lib/webots/libode.so',
        home/'lib/webots/libQt6Core.so.6',home/'lib/webots/libQt6Widgets.so.6']}
    (OUT/'engine.json').write_text(json.dumps({'image':runner.IMAGE,'source':runner.SOURCE,'sha256':identities},indent=2)+'\n')
    real_killpg=os.killpg
    def observed_killpg(pgid,sig):
        entry={'arm':arm,'pgid':pgid,'signal':int(sig),'monotonic_ns':time.monotonic_ns()}
        signals.append(entry)
        try:
            value=real_killpg(pgid,sig);entry['sent']=True;return value
        except ProcessLookupError:
            entry['sent']=False;raise
    os.killpg=observed_killpg
    try:
        for sequence,(arm,normal) in enumerate((('current',False),('normal',True)),1):
            prior=set(expected);record={'arm':arm,'normal_requested':normal}
            try:
                result=runner.trial(home,0,2.,'unavailable',sequence_index=sequence,
                                    expected_trials=expected,normal_quit=normal)
                record['result']=result;record['trial_pass']=True
            except Exception as error:
                record.update(trial_pass=False,error=type(error).__name__+': '+str(error))
            added=expected-prior
            if len(added)!=1:raise RuntimeError('ambiguous trial identity')
            trial=runner.OUT/next(iter(added));record['directory']=trial.name
            cleanup=json.loads((trial/'startup-cleanup.json').read_text()) if (trial/'startup-cleanup.json').exists() else {}
            record['wrapper_pid']=cleanup.get('wrapper_pid')
            record['residual_processes']=cleanup.get('process_group_after_cleanup')
            record['world_sha256']=digest(trial/'world.wbt')
            record['proofs']={p.name:digest(p) for p in sorted(trial.iterdir()) if p.is_file()}
            record['normal_record']=json.loads((trial/'normal-quit.json').read_text()) if (trial/'normal-quit.json').exists() else None
            rows.append(record)
            (OUT/'signals.json').write_text(json.dumps(signals,indent=2)+'\n')
            (OUT/'comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
        verify_new_capture_seals(runner.OUT,before,expected)
        if not all(r.get('trial_pass') and r['residual_processes']==[] for r in rows):raise RuntimeError('trial or retirement failed')
        a,b=rows
        same_result_keys=('configuration','attempt','status','reason','crossings','ast_sha256','claim','mode','webots_version')
        if a['world_sha256']!=b['world_sha256'] or any(a['result'].get(k)!=b['result'].get(k) for k in same_result_keys):
            raise RuntimeError('native world/semantic-result mismatch')
        if not b['normal_record']['normal_success']:raise RuntimeError('no confirmed normal exit')
        if not any(s['arm']=='current' and s['pgid']==a['wrapper_pid'] and s['signal']==signal.SIGTERM and s['sent'] for s in signals):
            raise RuntimeError('current SIGTERM path not exercised')
        if any(s['arm']=='normal' and s['pgid']==b['wrapper_pid'] for s in signals):raise RuntimeError('normal arm used signal fallback')
        outcome={'normal_exit':'PROVEN_IN_THIS_PAIR','runner_sigterm_path':'ELIMINATED_IN_NORMAL_ARM',
                 'historical_post_ready_crash':'UNPROVEN','claims_scope':'No native handler-entry probe; signal observations concern this runner only.'}
        (OUT/'qualification.json').write_text(json.dumps(outcome,indent=2)+'\n')
        print(json.dumps(outcome),flush=True)
    finally:
        os.killpg=real_killpg
        (OUT/'signals.json').write_text(json.dumps(signals,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--native',action='store_true');a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if a.native:return native()
    subprocess.run(['bash','tools/prepare_runtime_v2.sh'],cwd=ROOT,check=True)
    subprocess.run(['node','tools/grand_prix/pupil_workspace_u.js'],cwd=ROOT,check=True)
    assets=ROOT/'.ci-normal-quit-assets'
    subprocess.run(['git','clone','--depth=1','--filter=blob:none','--sparse','--branch','R2025a',
                    'https://github.com/cyberbotics/webots.git',str(assets)],check=True)
    subprocess.run(['git','-C',str(assets),'sparse-checkout','set','projects/robots/bitcraze/crazyflie',
                    'projects/objects/backgrounds','projects/objects/floors','projects/appearances','projects/default'],check=True)
    if subprocess.check_output(['git','-C',str(assets),'rev-parse','HEAD'],text=True).strip()!=runner.SOURCE:
        raise RuntimeError('wrong assets pin')
    subprocess.run(['docker','pull',runner.IMAGE],check=True)
    with tempfile.TemporaryDirectory(prefix='normal-quit-') as temp:
        cid=Path(temp)/'container.cid'
        command='set -eu\npython3 -u experiments/665-normal-quit/contrast.py --native'
        try:
            subprocess.run(runner.native_container_command(cid,assets,shutil.which('node'),command),
                           check=True,timeout=300)
        finally:
            if cid.exists():
                identity=cid.read_text().strip()
                if len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity):
                    raise RuntimeError('invalid owned container identity')
                state=subprocess.run(['docker','inspect','--format','{{.State.Running}}',identity],capture_output=True,text=True,timeout=10)
                if state.returncode==0 and state.stdout.strip()=='true':
                    subprocess.run(['docker','stop','--time','5',identity],check=True,timeout=20)

if __name__=='__main__':main()
