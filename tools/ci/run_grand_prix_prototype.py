#!/usr/bin/env python3
"""Real-Webots proof using one sensor-only AST; never a hardware checkpoint."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.grand_prix.layout import generate,world_text
IMAGE='cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099'
ARTIFACTS=ROOT/'ci-artifacts/grand-prix'

def main():
    if not shutil.which('docker'):raise RuntimeError('real Webots evidence unavailable: docker missing')
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    source=ROOT/'.ci-grand-prix-webots'
    if not source.exists():
        subprocess.run(['git','clone','--depth=1','--filter=blob:none','--sparse','--branch','R2025a','https://github.com/cyberbotics/webots.git',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'sparse-checkout','set','projects/robots/bitcraze/crazyflie','projects/objects/backgrounds','projects/objects/floors','projects/appearances'],check=True)
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if commit!='c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b':raise RuntimeError('unexpected R2025a asset source')
    subprocess.run(['docker','pull',IMAGE],check=True)
    subprocess.run(['docker','run','--rm','-v',f'{ROOT}:/workspace','-w','/workspace/controllers/grand_prix_flight',IMAGE,'bash','-lc','make clean && make'],check=True)
    witness=ROOT/'plugins/robot_windows/grand_prix_probe/reference_program.js'
    witness.write_text((ROOT/'tools/grand_prix/reference_program.js').read_text())
    html=ROOT/'plugins/robot_windows/grand_prix_probe/grand_prix_probe.html'
    original=html.read_text();html.write_text(original.replace('../../../tools/grand_prix/reference_program.js','reference_program.js'))
    try:
        for seed in (1,3):
            target=ROOT/f'worlds/ci_gp_{seed}.wbt';project=ROOT/f'worlds/.ci_gp_{seed}.wbproj'
            target.write_text(world_text(generate(seed)).replace('window "grand_prix"','window "grand_prix_probe"').replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/','webots://'))
            project.write_text('Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n')
            out=ARTIFACTS/str(seed);out.mkdir(parents=True,exist_ok=True)
            events=out/'events.jsonl';events.unlink(missing_ok=True)
            inner=f'''set -e
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
mkdir -p /root/.config/Cyberbotics
printf '%s\\n' '[RobotWindow]' 'browser=/workspace/tools/ci/webots_runtime_v2_browser.sh' 'newBrowserWindow=false' > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/runtime_wwi_event_server.py --output /workspace/ci-artifacts/grand-prix/{seed}/events.jsonl &
trap 'kill $! 2>/dev/null || true' EXIT
xvfb-run -a webots --stdout --stderr --batch --mode=realtime /workspace/worlds/ci_gp_{seed}.wbt'''
            with (out/'webots.log').open('w') as log:
                proc=subprocess.Popen(['docker','run','--rm','-e','LIBGL_ALWAYS_SOFTWARE=true','-e','WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true','-e',f'WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/grand-prix/{seed}','-v',f'{ROOT}:/workspace','-v',f'{source / "projects"}:/usr/local/webots/projects:ro','-w','/workspace',IMAGE,'bash','-lc',inner],stdout=log,stderr=subprocess.STDOUT)
                end=time.monotonic()+1100
                found=[]
                try:
                    while proc.poll() is None and time.monotonic()<end:
                        if events.exists():
                            found=[json.loads(line) for line in events.read_text().splitlines() if line.strip()]
                            if any(e.get('event') in ('GP_ERROR','GP_RANGES') for e in found):break
                        if (out/'webots.log').exists() and any(marker in (out/'webots.log').read_text() for marker in ('ERROR:','Traceback (most recent call last)')):break
                        time.sleep(.25)
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        try:proc.wait(timeout=15)
                        except subprocess.TimeoutExpired:proc.kill();proc.wait()
            target.unlink(missing_ok=True);project.unlink(missing_ok=True)
            errors=[e for e in found if e.get('event')=='GP_ERROR']
            if errors:raise RuntimeError(f'gp-v2-{seed}: {errors}')
            outcome=next((e['detail'] for e in found if e.get('event')=='GP_OUTCOME'),None)
            if outcome!={'status':'achieved'}:raise RuntimeError(f'gp-v2-{seed}: missing real success: {outcome}; see {out}')
            if 'ERROR:' in (out/'webots.log').read_text():raise RuntimeError(f'Webots errors on seed {seed}')
            measured=next((e['detail'] for e in found if e.get('event')=='GP_RANGES'),None)
            counts=[e['detail'] for e in found if e.get('event')=='GP_VARIABLES']
            if not measured or not counts or counts[-1]['portes']!=len(generate(seed).gates):raise RuntimeError('missing raw ranges / discovered count')
            print(f'PASS real Webots {generate(seed).identifier}: same AST, discovered gate count, three laps, terminal closed gate and simulation-clock outcome',flush=True)
    finally:
        html.write_text(original);witness.unlink(missing_ok=True)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:print(f'FAIL Grand Prix prototype: {error}',file=sys.stderr);raise SystemExit(1)
