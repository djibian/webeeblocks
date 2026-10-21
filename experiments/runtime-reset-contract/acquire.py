"""Four preregistered small native processes; no replacement or CI Gate."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
IMAGE='cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099'
SOURCE='c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    if sys.argv[1:]!=['--remaining']:raise ValueError('original series stopped; only the three unstarted cases remain eligible')
    out=ROOT/'ci-artifacts/reset-contract-remaining'
    out.mkdir(parents=True,exist_ok=False)
    engine=ROOT/'engine'
    if subprocess.check_output(['git','-C',engine,'rev-parse','HEAD'],text=True).strip()!=SOURCE:
        raise ValueError('wrong R2025a source/assets')
    original=ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'
    before=sha(original)
    controller=ROOT/'controllers/reset_contract'
    controller.mkdir(exist_ok=False)
    robot=(ROOT/'worlds/crazyflie_runtime_v2.wbt').read_text().split('\nCrazyflie {\n',1)[1].split('\n# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN',1)[0]
    robot='DEF CONTRACT_DRONE Crazyflie {\n'+robot
    robot=robot.replace('controller "crazyflie_runtime_v2"','controller "reset_contract"').replace('window "blockly_v2"','window "<none>"')
    world='''#VRML_SIM R2025a utf8
EXTERNPROTO "/engine/projects/robots/bitcraze/crazyflie/protos/Crazyflie.proto"
DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo {
  basicTimeStep 32
  randomSeed 1
  optimalThreadCount 1
}
Viewpoint { position 2 2 2 orientation -0.4 0.8 0.4 2 }
Background { skyColor [ 0.5 0.5 0.5 ] }
DirectionalLight { direction 0 0 -1 }
Solid {
  children [ Shape { appearance PBRAppearance { baseColor 0.5 0.5 0.5 } geometry Plane { size 20 20 } } ]
  boundingObject Plane { size 20 20 }
}
'''+robot
    target=ROOT/'worlds/ci_reset_contract.wbt';target.write_text(world)
    (out/'world.wbt').write_text(world)
    command='''set -eu
test "$(cat /usr/local/webots/resources/version.txt)" = R2025a
g++ -std=c++17 -O2 -I/usr/local/webots/include/controller/c -I/workspace/controllers/crazyflie_square \
 /workspace/experiments/runtime-reset-contract/fixture.cpp \
 /workspace/controllers/crazyflie_runtime_v2/activity_scene.cpp \
 /workspace/controllers/crazyflie_square/pid_controller.c \
 -L/usr/local/webots/lib/controller -Wl,-rpath,/usr/local/webots/lib/controller -lController -lm \
 -o /workspace/controllers/reset_contract/reset_contract
sha256sum /usr/local/webots/bin/webots-bin /workspace/controllers/reset_contract/reset_contract
'''
    def docker(script,env=None):
        argv=['docker','run','--rm','-v',f'{ROOT}:/workspace','-v',f'{engine}:/engine:ro','-w','/workspace']
        for key,value in (env or {}).items():argv+=['-e',key+'='+value]
        return subprocess.run([*argv,IMAGE,'bash','-lc',script],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=200)
    (out/'build-command.sh').write_text(command)
    result=docker(command);(out/'build.log').write_text(result.stdout)
    if result.returncode:raise RuntimeError('build preparation refused')
    native='''set -eu
export WEBOTS_HOME=/usr/local/webots LIBGL_ALWAYS_SOFTWARE=true
export WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true
timeout -k 5s 90s xvfb-run -a webots --stdout --stderr --batch --no-rendering --mode=fast /workspace/worlds/ci_reset_contract.wbt
'''
    (out/'native-command.sh').write_text(native)
    try:
        for mode,variants in (('idle',('B',)),('takeoff',('A','B'))):
            for variant in variants:
                name=variant+'-'+mode
                result=docker(native,{'RESET_CONTRACT_VARIANT':variant,'RESET_CONTRACT_MODE':mode,
                                     'RESET_CONTRACT_JOURNAL':'/workspace/ci-artifacts/reset-contract-remaining/'+name+'.events.jsonl'})
                (out/(name+'.log')).write_text(result.stdout)
                (out/(name+'.exit')).write_text(str(result.returncode)+'\n')
                from analyze import analyze
                journal=[json.loads(line) for line in (out/(name+'.events.jsonl')).read_text().splitlines()]
                summary=analyze(result.stdout,mode,journal)
                (out/(name+'.json')).write_text(json.dumps(summary,indent=2)+'\n')
                if result.returncode or not summary['completed']:raise RuntimeError('first refusal: '+name)
    finally:
        (out/'provenance.json').write_text(json.dumps({
            'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'base_main':'b478f9dd1854d83345abe13ed20fcf7baeffaca5','image':IMAGE,'engine_source':SOURCE,
            'production_unchanged':sha(original)==before,'production_sha256':before,
            'scope':'minimal fixture, no historical attribution or CI Gate',
            'sha256':{str(p.relative_to(ROOT)):sha(p) for p in [HERE/'fixture.cpp',HERE/'PROTOCOL.md',HERE/'acquire.py',HERE/'analyze.py',controller/'reset_contract']}
        },indent=2)+'\n')
        (out/'manifest.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
