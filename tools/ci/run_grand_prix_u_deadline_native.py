"""Real R2025a clock/field interleavings plus composed flight compilation.
No dynamic landing/trajectory claim; those belong to the later #591 composition.
"""
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ci-artifacts/grand-prix-u-geometry'

def run_native(home):
    if (home/'resources/version.txt').read_text().strip()!='R2025a':
        raise RuntimeError('R2025a required')
    env=os.environ.copy()
    env.update(WEBOTS_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='true',
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'deadline-build.log').open('w') as log:
        for controller in ('grand_prix_u_flight','grand_prix_u_deadline_probe'):
            subprocess.run(['make','-C',str(ROOT/'controllers'/controller)],env=env,
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    target=ROOT/'worlds/ci_gp_u_deadline.wbt'
    try:
        for case in range(5):
            target.write_text('#VRML_SIM R2025a utf8\n'
                'WorldInfo { basicTimeStep 8 }\n'
                'DEF GP_U_EVALUATOR Robot { name "Évaluateur échéance" controller "<none>" }\n'
                'Robot { name "Probe échéance" supervisor TRUE controller "grand_prix_u_deadline_probe" window "<none>" '
                f'controllerArgs [ "{case}" ] }}\n')
            logpath=OUT/f'deadline-{case}.log'
            with logpath.open('w') as log:
                subprocess.run([str(home/'webots'),'--batch','--mode=fast','--stdout','--stderr',str(target)],
                               cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=45,check=True)
            text=logpath.read_text()
            expected=f'GP_U_NATIVE_DEADLINE case={case} triggers={0 if case==0 else 1} trigger_ms={-1 if case==0 else 210000} claim=time-fields-only'
            if text.count(expected)!=1 or 'GP_U_NATIVE_FAIL' in text or any(line.startswith('ERROR:') for line in text.splitlines()):
                raise RuntimeError('native deadline evidence failed: '+str(logpath))
            print('PASS real R2025a time/fields '+expected,flush=True)
    finally:
        target.unlink(missing_ok=True)
        target.with_name('.ci_gp_u_deadline.wbproj').unlink(missing_ok=True)
