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
            record=OUT/f'deadline-{case}-native.txt'
            record.unlink(missing_ok=True)
            env['GP_U_DEADLINE_OUT']=str(record)
            with logpath.open('w') as log:
                subprocess.run([str(home/'webots'),'--batch','--mode=fast','--stdout','--stderr',str(target)],
                               cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=45,check=True)
            text=logpath.read_text()
            expected=f'GP_U_NATIVE_DEADLINE case={case} triggers={0 if case==0 else 1} trigger_ms={-1 if case==0 else 210000} claim=time-fields-only'
            observed=record.read_text().strip() if record.exists() else None
            markers=[line for line in text.splitlines() if line.startswith('GP_U_NATIVE_DEADLINE ')]
            if observed!=expected or any(line!=expected for line in markers) or 'GP_U_NATIVE_FAIL' in text or any(line.startswith('ERROR:') for line in text.splitlines()):
                raise RuntimeError('native deadline evidence failed: '+str(logpath))
            print('PASS real R2025a time/fields '+expected,flush=True)
    finally:
        target.unlink(missing_ok=True)
        target.with_name('.ci_gp_u_deadline.wbproj').unlink(missing_ok=True)
    run_pose_native(home,env)

def run_pose_native(home,env):
    from test_grand_prix_u_pose import instrument, CASES, expected_reset, expected_teleports
    build=ROOT/'controllers/grand_prix_u_pose_probe/build'
    build.mkdir(parents=True,exist_ok=True)
    instrument(build)
    with (OUT/'pose-build.log').open('w') as log:
        subprocess.run(['make','-C',str(build.parent)],env=env,
                       stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    source=(ROOT/'worlds/crazyflie_runtime_v2.wbt').read_text()
    robot=source[source.index('Crazyflie {'):source.index('# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN')]
    # The initial native reset fields must match the imposed startup pose.
    robot=robot.replace('Crazyflie {','Crazyflie {\n  translation 0 0 0.023\n  rotation 1 0 0 0',1)
    robot=robot.replace('controller "crazyflie_runtime_v2"','controller "grand_prix_u_pose_probe"')
    robot=robot.replace('window "blockly_v2"','window "<none>"')
    externs='\n'.join(line.replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/','webots://')
                      for line in source.splitlines() if line.startswith('EXTERNPROTO '))
    target=ROOT/'worlds/ci_gp_u_pose.wbt'
    try:
        target.write_text('#VRML_SIM R2025a utf8\n'+externs+'\n'
            'WorldInfo { basicTimeStep 8 gravity 0 }\n'+robot+'\n'
            'DEF GP_U_EVALUATOR Robot { name "Évaluateur pose" controller "<none>" }\n')
        for case in CASES:
            record=OUT/f'pose-{case}-native.txt';record.unlink(missing_ok=True)
            env.update(GP_U_POSE_CASE=case,GP_U_POSE_OUT=str(record))
            logpath=OUT/f'pose-{case}.log'
            with logpath.open('w') as log:
                subprocess.run([str(home/'webots'),'--batch','--mode=fast','--stdout','--stderr',str(target)],
                               cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=45,check=True)
            text=logpath.read_text()
            expected=f'GP_U_POSE_PASS case={case} teleports={int(expected_teleports(case))} reset_ok={int(expected_reset(case))} claim=controlled-pose-composition'
            if not record.exists() or record.read_text().strip()!=expected:
                raise RuntimeError('missing exact composed native pose evidence: '+str(logpath))
            # Webots may drop the final stdout, but the exact persisted record
            # follows every assertion. LAND is earlier and must also be observed.
            deadlines=[line for line in text.splitlines() if line.startswith('GP_U_DEADLINE ')]
            if (len(deadlines)!=1 or 'time_ms=212048 command=LAND' not in deadlines[0] or
                    any(line.startswith('ERROR:') for line in text.splitlines()) or 'Assertion' in text):
                raise RuntimeError('native composed pose/LAND failed: '+str(logpath))
            print('PASS real R2025a composed '+expected,flush=True)
    finally:
        target.unlink(missing_ok=True)
        target.with_name('.ci_gp_u_pose.wbproj').unlink(missing_ok=True)
