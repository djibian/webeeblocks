#!/usr/bin/env python3
"""Real-Webots proof using one sensor-only AST; never a hardware checkpoint."""
from pathlib import Path
import json
import hashlib
import math
import os
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.grand_prix.layout import generate,world_text
from tools.grand_prix.timing import analyze
IMAGE='cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099'
ARTIFACTS=ROOT/'ci-artifacts/grand-prix'

def main():
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
    original=html.read_text();html.write_text(original.replace('../../../tools/grand_prix/reference_program.js','reference_program.js'))
    try:
        summaries=[];programs={}
        # Add explicit calibration observations; preserve every legacy trial.
        compact=[('gp-v3',seed,laps,True,memory) for memory,laps in ((False,2),(False,1),(True,2)) for seed in (16,12,6)]
        legacy=[('gp-v2',seed,laps,True,False) for laps in (3,1,2) for seed in (1,4)]+[('gp-v2',1,1,False,False),('gp-v2',4,1,False,False)]
        v4=[('gp-v4',seed,1,True,False) for seed in (4,1,0)]
        for version,seed,laps,efficient,memory in v4:
            layout=generate(seed,version)
            module='reference_program_v4.js' if version=='gp-v4' else ('reference_program_compact.js' if version=='gp-v3' else 'reference_program.js')
            witness.write_text((ROOT/'tools/grand_prix'/module).read_text())
            html.write_text(original.replace('../../../tools/grand_prix/reference_program.js','reference_program.js').replace('<script src="grand_prix_probe.js"></script>',f'<script>window.GP_TEST_STRATEGY_LAPS={laps};window.GP_TEST_EFFICIENT={str(efficient).lower()};window.GP_TEST_MEMORY_CHOICE={str(memory).lower()};</script><script src="grand_prix_probe.js"></script>'))
            target=ROOT/f'worlds/ci_gp_{seed}.wbt';project=ROOT/f'worlds/.ci_gp_{seed}.wbproj'
            target.write_text(world_text(layout).replace('window "grand_prix"','window "grand_prix_probe"').replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/','webots://'))
            project.write_text('Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n')
            policy='memory' if memory else ('efficient' if efficient else 'legacy')
            prefix=version+'-' if version!='gp-v2' else ''
            out=ARTIFACTS/f'{prefix}{seed}-{laps}-{policy}';out.mkdir(parents=True,exist_ok=True)
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
            with (out/'webots.log').open('w') as log:
                proc=subprocess.Popen(['docker','run','--rm','-e','LIBGL_ALWAYS_SOFTWARE=true','-e','WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true','-e',f'WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/grand-prix/{out.name}','-v',f'{ROOT}:/workspace','-v',f'{source / "projects"}:/usr/local/webots/projects:ro','-w','/workspace',IMAGE,'bash','-lc',inner],stdout=log,stderr=subprocess.STDOUT)
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
            expected_laps=(2 if len(layout.gates)==4 else 1) if memory else laps
            crossings=expected_laps*len(layout.gates)+len(layout.final_gates)-1
            if result['laps']!=expected_laps or result['crossings']!=crossings or result['configuration']!=layout.identifier or result['attempt']!=1:raise RuntimeError(f'wrong exact route result: {result}')
            threshold=180 if version=='gp-v4' else 120
            if result['candidate_points']!=5*crossings-math.ceil(max(0,result['seconds']-threshold)):raise RuntimeError('wrong candidate score')
            programme=next(e['detail'] for e in found if e.get('event')=='GP_PROGRAM')
            digest=hashlib.sha256(json.dumps(programme,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            key=(version,laps,efficient,memory)
            if key in programs and programs[key]!=digest:raise RuntimeError('programme changed between configurations')
            programs[key]=digest
            diagnostic=analyze((out/'webots.log').read_text(),result['seconds'],result['attempt'])
            (out/'timing.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
            result.update(penalty_threshold_s=threshold,ast_sha256=digest,webots_image=IMAGE,mode='realtime',strategy=policy)
            summaries.append(result);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(f'PASS real Webots {layout.identifier}: {expected_laps} freely chosen laps, {policy}, same strategy AST across configurations, {crossings} crossings, {result["seconds"]:.3f}s, {result["candidate_points"]} candidate points',flush=True)
        (ARTIFACTS/'strategies.json').write_text(json.dumps(summaries,indent=2)+'\n')
    finally:
        html.write_text(original);witness.unlink(missing_ok=True)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:print(f'FAIL Grand Prix prototype: {error}',file=sys.stderr);raise SystemExit(1)
