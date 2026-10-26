#!/usr/bin/env python3
"""Real-Webots proof using one sensor-only AST; never a hardware checkpoint."""
from pathlib import Path
import json
import dataclasses
import argparse
import hashlib
import math
import os
import shutil
import subprocess
import sys
import time
import tempfile
import re
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.grand_prix.layout import generate,world_text
from tools.grand_prix.timing import analyze
IMAGE='ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca'
ARTIFACTS=ROOT/'ci-artifacts/grand-prix'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suite',choices=('gp-v2','gp-v3','gp-v4','gp-v4-time','all'),default='gp-v4-time')
    args=parser.parse_args()
    subprocess.run([sys.executable,str(ROOT/'tools/ci/test_grand_prix_v4.py')],check=True)
    if not shutil.which('docker'):raise RuntimeError('real Webots evidence unavailable: docker missing')
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    source=ROOT/'.ci-grand-prix-webots'
    if not source.exists():
        subprocess.run(['git','clone','--depth=1','--filter=blob:none','--sparse','--branch','R2025a','https://github.com/cyberbotics/webots.git',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'sparse-checkout','set','projects/robots/bitcraze/crazyflie','projects/objects/backgrounds','projects/objects/floors','projects/appearances','projects/default'],check=True)
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if commit!='c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b':raise RuntimeError('unexpected R2025a asset source')
    subprocess.run(['docker','pull',IMAGE],check=True)
    subprocess.run(['docker','run','--rm','-v',f'{ROOT}:/workspace','-w','/workspace/controllers/grand_prix_flight',IMAGE,'bash','-lc','make clean && make'],check=True)
    witness=ROOT/'plugins/robot_windows/grand_prix_probe/reference_program.js'
    witness.write_text((ROOT/'tools/grand_prix/reference_program.js').read_text())
    html=ROOT/'plugins/robot_windows/grand_prix_probe/grand_prix_probe.html'
    policy_asset=ROOT/'plugins/robot_windows/grand_prix_probe/reference_policy_time.js'
    policy_asset.write_text((ROOT/'tools/grand_prix/reference_policy_time.js').read_text())
    original=html.read_text();html.write_text(original.replace('../../../tools/grand_prix/reference_program.js','reference_program.js'))
    try:
        summaries=[];programs={}
        # Add explicit calibration observations; preserve every legacy trial.
        compact=[('gp-v3',seed,laps,True,memory) for memory,laps in ((False,2),(False,1),(True,2)) for seed in (16,12,6)]
        legacy=[('gp-v2',seed,laps,True,False) for laps in (3,1,2) for seed in (1,4)]+[('gp-v2',1,1,False,False),('gp-v2',4,1,False,False)]
        v4=[('gp-v4',0,1,True,False),('gp-v4',16,1,True,False),('gp-v4',16,2,True,False),('gp-v4',1,2,True,False),('gp-v4',1,1,True,False),('gp-v4',4,1,True,False),('gp-v4',16,2,True,True),('gp-v4',1,2,True,True)]
        timed=[('gp-v4',0,1,True,False,180,False),('gp-v4',4,1,True,False,180,False),('gp-v4',16,2,True,False,180,True)]
        timed += [('gp-v4',seed,laps,True,False,540,clock) for seed in (16,1) for laps,clock in ((1,False),(2,False),(2,True))]
        standard=[(*case,180 if case[0]=='gp-v4' else 120,False) for case in {'gp-v2':legacy,'gp-v3':compact,'gp-v4':v4,'all':v4+compact+legacy}.get(args.suite,[])]
        selected=timed if args.suite=='gp-v4-time' else standard
        for version,seed,laps,efficient,memory,threshold,clock in selected:
            layout=generate(seed,version)
            module='reference_program_v4.js' if version=='gp-v4' else ('reference_program_compact.js' if version=='gp-v3' else 'reference_program.js')
            witness.write_text((ROOT/'tools/grand_prix'/module).read_text())
            html.write_text(original.replace('../../../tools/grand_prix/reference_program.js','reference_program.js').replace('<script src="grand_prix_probe.js"></script>',f'<script src="reference_policy_time.js"></script><script>window.GP_TEST_STRATEGY_LAPS={laps};window.GP_TEST_EFFICIENT={str(efficient).lower()};window.GP_TEST_MEMORY_CHOICE={str(memory).lower()};window.GP_TEST_TIME_POLICY={str(clock).lower()};window.GP_TEST_THRESHOLD={threshold};window.GP_TEST_FINAL_ESTIMATE=90;</script><script src="grand_prix_probe.js"></script>'))
            target=ROOT/f'worlds/ci_gp_{seed}.wbt';project=ROOT/f'worlds/.ci_gp_{seed}.wbproj'
            target.write_text(world_text(layout,threshold if version=='gp-v4' else None).replace('window "grand_prix"','window "grand_prix_probe"').replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/','webots://'))
            project.write_text('Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n')
            policy='clock' if clock else ('memory' if memory else ('efficient' if efficient else 'legacy'))
            prefix=version+'-' if version!='gp-v2' else ''
            out=ARTIFACTS/f'{prefix}{seed}-{laps}-{policy}-T{threshold}';out.mkdir(parents=True,exist_ok=True)
            (out/'layout.json').write_text(json.dumps(dataclasses.asdict(layout),indent=2)+'\n')
            events=out/'events.jsonl';events.unlink(missing_ok=True)
            inner=f'''set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
mkdir -p /root/.config/Cyberbotics
printf '%s\\n' '[RobotWindow]' 'browser=/workspace/tools/ci/webots_runtime_v2_browser.sh' 'newBrowserWindow=false' > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py --output /workspace/ci-artifacts/grand-prix/{out.name}/events.jsonl &
trap 'kill $! 2>/dev/null || true' EXIT
xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_gp_{seed}.wbt'''
            with tempfile.TemporaryDirectory(prefix='gp-container-') as container_dir, (out/'webots.log').open('w') as log:
                cid_path=Path(container_dir)/'container.cid'
                proc=subprocess.Popen(['docker','run','--rm','--cidfile',str(cid_path),'-e','LIBGL_ALWAYS_SOFTWARE=true','-e','WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true','-e',f'WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/grand-prix/{out.name}','-v',f'{ROOT}:/workspace','-v',f'{source / "projects"}:/usr/local/webots/projects:ro','-w','/workspace',IMAGE,'bash','-lc',inner],stdout=log,stderr=subprocess.STDOUT)
                end=time.monotonic()+1100
                found=[]
                try:
                    while proc.poll() is None and time.monotonic()<end:
                        if events.exists():
                            found=[json.loads(line) for line in events.read_text().splitlines() if line.strip()]
                            if any(e.get('event') in ('GP_ERROR','GP_RANGES') for e in found):break
                        if (out/'webots.log').exists():
                            observed=(out/'webots.log').read_text()
                            if any(marker in observed for marker in ('ERROR:','Traceback (most recent call last)','WEBEEBLOCKS_GP_REJECTION')):break
                        time.sleep(.25)
                finally:
                    if proc.poll() is None and cid_path.exists():
                        cid=cid_path.read_text().strip()
                        if not re.fullmatch(r'[0-9a-f]{64}',cid):raise RuntimeError('invalid owned container identity')
                        stopped=subprocess.run(['docker','stop','--time','5',cid],capture_output=True,text=True,timeout=20)
                        if stopped.returncode:raise RuntimeError('owned container cleanup uncertain: '+stopped.stderr)
                    if proc.poll() is None:
                        proc.terminate()
                        try:proc.wait(timeout=15)
                        except subprocess.TimeoutExpired:proc.kill();proc.wait()
            target.unlink(missing_ok=True);project.unlink(missing_ok=True)
            errors=[e for e in found if e.get('event')=='GP_ERROR']
            if errors:raise RuntimeError(f'{layout.identifier}: {errors}')
            outcome=next((e['detail'] for e in found if e.get('event')=='GP_OUTCOME'),None)
            if outcome!={'status':'achieved'}:raise RuntimeError(f'{layout.identifier}: missing real success: {outcome}; see {out}')
            if 'ERROR:' in (out/'webots.log').read_text():raise RuntimeError(f'Webots errors on seed {seed}')
            measured=next((e['detail'] for e in found if e.get('event')=='GP_RANGES'),None)
            counts=[e['detail'] for e in found if e.get('event')=='GP_VARIABLES']
            if not measured or not counts or counts[-1]['portes']!=len(layout.gates):raise RuntimeError('missing raw ranges / discovered count')
            boundaries=[json.loads(line.split('WEBEEBLOCKS_GP_CLOCK_BOUNDARY ',1)[1]) for line in (out/'webots.log').read_text().splitlines() if line.startswith('WEBEEBLOCKS_GP_CLOCK_BOUNDARY ')]
            native=[json.loads(line.split('WEBEEBLOCKS_GP_RESULT ',1)[1]) for line in (out/'webots.log').read_text().splitlines() if line.startswith('WEBEEBLOCKS_GP_RESULT ')]
            if len(native)!=1:raise RuntimeError('missing or duplicate native result')
            result=native[0]
            required_boundaries=[(119.968,0),(120.0,0),(120.032,1)]
            if version=='gp-v4':required_boundaries += [(179.968,0),(180.0,0),(180.032,1)]
            if version in ('gp-v3','gp-v4'):required_boundaries=[pair for pair in required_boundaries if pair[0]<=result['seconds']]
            if [(v['seconds'],v['penalty']) for v in boundaries]!=required_boundaries:raise RuntimeError(f'missing reached native clock boundaries: {boundaries}')
            if clock:
                first=next((v for v in counts if v.get('tour')==1 and v.get('temps observé',0)>0),None)
                if first is None:raise RuntimeError('missing real first-junction clock observation')
                elapsed=first['temps observé']
                cost=max(0,2*elapsed+90-threshold)-max(0,elapsed+90-threshold)
                expected_laps=1 if cost>=5*len(layout.gates) else 2
            elif memory:
                expected_laps=(1 if len(layout.gates)>=3 else 2) if version=='gp-v4' else (2 if len(layout.gates)==4 else 1)
            else:expected_laps=laps
            crossings=expected_laps*len(layout.gates)+len(layout.final_gates)-1
            if result['laps']!=expected_laps or result['crossings']!=crossings or result['configuration']!=layout.identifier or result['attempt']!=1:raise RuntimeError(f'wrong exact route result: {result}')
            if result['candidate_points']!=5*crossings-math.ceil(max(0,result['seconds']-threshold)):raise RuntimeError('wrong candidate score')
            programme=next(e['detail'] for e in found if e.get('event')=='GP_PROGRAM')
            digest=hashlib.sha256(json.dumps(programme,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            key=(version,laps,efficient,memory,clock,threshold)
            if key in programs and programs[key]!=digest:raise RuntimeError('programme changed between configurations')
            programs[key]=digest
            diagnostic=analyze((out/'webots.log').read_text(),result['seconds'],result['attempt'])
            from tools.grand_prix.kinematics import analyze as analyze_kinematics
            kinematic=analyze_kinematics(out/'native_trace.csv',(out/'webots.log').read_text(),layout,result['seconds'],result['attempt'],measured)
            print('GP_GEOMETRY_DIAGNOSTIC '+json.dumps(dict(configuration=layout.identifier,threshold=threshold,policy=policy,min_clearance=kinematic['minimum_envelope_clearance_m'],closed_clearance=kinematic['closed_wall_clearance_at_land_ack_m'],max_speed=kinematic['maximum_horizontal_speed_m_s'],max_tilt=kinematic['maximum_tilt_deg'],min_lateral=min(v['minimum_lateral_m'] for v in kinematic['gate_margins']),min_upper=min(v['minimum_upper_m'] for v in kinematic['gate_margins']),max_after_90pct_peak=max(v['extent_after_last_90pct_peak_m'] for v in kinematic['commands'] if v['command']=='MOVE'),max_turn_drift=max(v['path_extent_from_request_m'] for v in kinematic['commands'] if v['command']=='TURN')),sort_keys=True),flush=True)
            (out/'kinematics.json').write_text(json.dumps(kinematic,indent=2)+'\n')
            (out/'timing.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
            result.update(first_junction_seconds=first['temps observé'] if clock else None,final_estimate_s=90 if clock else None,penalty_threshold_s=threshold,ast_sha256=digest,webots_image=IMAGE,mode='realtime',strategy=policy)
            summaries.append(result);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            if clock:print('GP_CLOCK_DECISION '+json.dumps(dict(configuration=layout.identifier,threshold=threshold,estimate=90,observed=first['temps observé'],marginal_penalty=cost,benefit=5*len(layout.gates),chosen_laps=expected_laps),sort_keys=True),flush=True)
            print(f'PASS real Webots {layout.identifier}: {expected_laps} freely chosen laps, {policy}, T={threshold}s, same strategy AST across configurations, {crossings} crossings, {result["seconds"]:.3f}s, {result["candidate_points"]} candidate points',flush=True)
        (ARTIFACTS/'strategies.json').write_text(json.dumps(summaries,indent=2)+'\n')
    finally:
        html.write_text(original);witness.unlink(missing_ok=True);policy_asset.unlink(missing_ok=True)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:print(f'FAIL Grand Prix prototype: {error}',file=sys.stderr);raise SystemExit(1)
