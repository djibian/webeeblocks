#!/usr/bin/env python3
"""Compile the real composed Runtime twice against controlled Webots fixtures.

This checks observation semantics; it is not native physics or timing evidence.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from instrument import EXPECTED, patch


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference_root', type=Path)
    args = parser.parse_args()
    root = args.reference_root.resolve()
    spec = importlib.util.spec_from_file_location('pose_reference', root/'tools/ci/test_grand_prix_u_pose.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = ('no-fault', 'deadline-error', 'early-error', 'timeout', 'land-timeout',
             'land', 'flight-yaw-infinite-loss', 'flight-yaw-deadline-recover')
    with tempfile.TemporaryDirectory(prefix='gp655-observation-') as tmp:
        base = Path(tmp)
        (base/'webots/plugins/robot_window').mkdir(parents=True)
        header = (root/'tools/ci/fixtures/gp_u_pose_webots.h').read_text()
        for name in ('robot','motor','gps','gyro','inertial_unit','distance_sensor','led','supervisor'):
            (base/'webots'/f'{name}.h').write_text(header)
        (base/'webots/plugins/robot_window/default.h').write_text('#include <webots/robot.h>\n')
        module.instrument(base)
        composed = (root/'controllers/grand_prix_u_flight/build/runtime_u.c').read_bytes()
        require(hashlib.sha256(composed).hexdigest() == EXPECTED, 'reference source changed')
        baseline = (base/'runtime.c').read_text()
        # The reference fixture adds only a same-tick control-applied marker.
        # Both variants preserve it and run the same broker/hook/driver.
        (base/'observed.c').write_text(patch(baseline))
        driver = (root/'tools/ci/fixtures/gp_u_pose_driver.cpp').read_text()
        driver = ('extern "C" { double pastAltitudeError,pastPitchError,pastRollError,pastYawRateError; '
                  'double pastVxError,pastVyError,altitudeIntegrator; }\n')+driver
        anchor = 'extern "C" void wb_motor_set_velocity(int,double value){assert(std::isfinite(value));}'
        require(driver.count(anchor) == 1, 'fixture motor anchor')
        driver = driver.replace(anchor, 'extern "C" void wb_motor_set_velocity(int tag,double value){assert(std::isfinite(value));std::printf("GP655_EFFECT tag=%d value=%.17g\\n",tag,value);}')
        anchor = ' std::memset(p,0,sizeof(*p));'
        require(driver.count(anchor) == 1, 'fixture PID anchor')
        driver = driver.replace(anchor, ' p->m1=-2; p->m2=1000; p->m3=37; p->m4=42;')
        anchor = ' imu[0]=rot[3];'
        require(driver.count(anchor) == 1, 'fixture attitude anchor')
        driver = driver.replace(anchor, ' if(std::getenv("GP655_PITCH_FIXTURE")){imu[0]=0;imu[1]=rot[3];}else{imu[0]=rot[3];}')
        (base/'driver.cpp').write_text(driver)
        includes = ['-I'+str(base), '-I'+str(root/'tools/ci/fixtures'),
                    '-I'+str(root/'controllers/crazyflie_runtime_v2'),
                    '-I'+str(root/'controllers/crazyflie_square'),
                    '-I'+str(root/'controllers/grand_prix_u_flight')]
        binaries = []
        for name in ('runtime','observed'):
            obj = base/(name+'.o')
            subprocess.run(['gcc','-std=c11',*includes,'-include',
                            str(root/'controllers/grand_prix_u_flight/grand_prix_u_hook.h'),
                            '-c',str(base/(name+'.c')),'-o',str(obj)],check=True)
            binary = base/name
            subprocess.run(['c++','-std=c++17','-DNDEBUG',*includes,str(obj),str(base/'driver.cpp'),
                            str(base/'broker.cpp'),str(base/'deadline.cpp'),
                            str(root/'controllers/crazyflie_runtime_v2/file_broker.cpp'),
                            str(root/'controllers/crazyflie_runtime_v2/activity_scene.cpp'),
                            '-pthread','-o',str(binary)],check=True)
            binaries.append(binary)
        results = []
        for case,pitch_fixture in [(case,False) for case in cases]+[('deadline-error',True)]:
            env={**os.environ,'GP_U_POSE_CASE':case}
            if pitch_fixture:env['GP655_PITCH_FIXTURE']='1'
            runs = [subprocess.run([str(binary)],env=env,
                                   capture_output=True,text=True,timeout=10) for binary in binaries]
            a,b = runs
            require(a.returncode == b.returncode == 0, 'fixture refused: '+case+' '+a.stderr+b.stderr)
            require(a.stdout == b.stdout, 'motor effects/protocol differ: '+case)
            diagnostic = [line for line in b.stderr.splitlines() if line.startswith('GP655_')]
            require(a.stderr == '\n'.join(line for line in b.stderr.splitlines() if not line.startswith('GP655_'))+
                    ('\n' if a.stderr else ''), 'non-diagnostic stderr differs: '+case)
            guards = [line for line in diagnostic if line.startswith('GP655_GUARD')]
            if case in ('deadline-error','early-error'):
                axis='pitch' if pitch_fixture else 'roll'
                require(any(axis+'_guard=1' in line and 'timeout_guard=0' in line for line in guards), 'attitude attribution')
            if case in ('timeout','land-timeout'):
                require(any('timeout_guard=1' in line for line in guards), 'timeout attribution')
            if case.startswith('flight-yaw-'):
                require(any('invalid_sample=1' in line for line in guards), 'sample attribution')
                require(any(line.startswith('GP655_RAW_INVALID') and 'inf' in line for line in diagnostic), 'raw invalid sample lost')
            outputs = [line for line in diagnostic if line.startswith('GP655_LAND_OUTPUT')]
            if outputs:
                require(all('raw_power=-2,1000,37,42 signed_targets=-0,600,-37,42' in line for line in outputs), 'post-clamp trace')
            require(any(line.startswith('GP655_ZERO_TARGETS') for line in diagnostic), 'zero targets absent')
            results.append({'case':case,'pitch_fixture':pitch_fixture,'identical_effects_and_protocol':True,'guards':guards,
                            'land_output_samples':len(outputs)})
        print(json.dumps({'claim':'controlled fixture equivalence; no native physics/timing evidence',
                          'cases':results},indent=2))


if __name__ == '__main__':
    main()
