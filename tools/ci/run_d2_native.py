"""D2 only: trace a generated, instrumented route pilot on teacher stimuli.

No production source or oracle is edited; never use this evidence as CI Gate.
Run in a disposable checkout with the pinned R2025a assets already installed.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

from tools.ci.run_grand_prix_progression_native import ROOT, OUT, run_native

MOTOR_ANCHOR = '      wb_motor_set_velocity(m1, -motor_power(power.m1));'
TRACE = r'''      printf("GP_D2_SAMPLE t=%.9f dt=%.9f cmd=%d id=%d speed=%.9f pos=%.9f,%.9f,%.9f origin_z=%.9f target=%.9f,%.9f,%.9f ref_z=%.9f vel=%.9f,%.9f,%.9f attitude=%.9f,%.9f,%.9f desired=%.9f,%.9f,%.9f,%.9f raw=%.9f,%.9f,%.9f,%.9f applied=%.9f,%.9f,%.9f,%.9f\n",
             now, dt, command, active_id, move_speed_limit, x, y, z, origin_z,
             target_x, target_y, target_z, desired.altitude,
             actual.vx, actual.vy, vz, actual.roll, actual.pitch, yaw,
             desired.vx, desired.vy, desired.roll, desired.pitch,
             power.m1, power.m2, power.m3, power.m4,
             motor_power(power.m1), motor_power(power.m2),
             motor_power(power.m3), motor_power(power.m4));
      fflush(stdout);
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--activity', type=int, choices=(4, 7), required=True)
    args = parser.parse_args()
    home = Path(os.environ['WEBOTS_HOME'])
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('wrong engine')
    root = ROOT / 'controllers/grand_prix_route_flight'
    source = root / 'build/runtime_u.c'
    evidence = OUT / f'd2-a{args.activity}-build'
    evidence.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, 'tools/grand_prix/prepare_route_runtime.py'],
                   cwd=ROOT, check=True)
    original = source.read_text()
    if original.count(MOTOR_ANCHOR) != 1:
        raise RuntimeError('native motor anchor drift')
    instrumented = original.replace(MOTOR_ANCHOR, TRACE + MOTOR_ANCHOR, 1)
    # Single-factor interventions, generated source only. Neither changes
    # velocity admission, trajectory, safety, or any vertical/attitude gains.
    cadence = 'if (transition || fast || elapsed >= 0.015999)'
    derivative = 'gains.kd_vel_xy = 0.5;'
    for anchor in (cadence, derivative):
        if instrumented.count(anchor) != 1:
            raise RuntimeError('D2 intervention anchor drift')
    cases = {
        'baseline': instrumented,
        'xy8': instrumented.replace(cadence, 'if (1)', 1),
        'xy32': instrumented.replace(cadence, 'if (transition || fast || elapsed >= 0.031999)', 1),
        'half-kd': instrumented.replace(derivative, 'gains.kd_vel_xy = 0.25;', 1),
    }
    try:
        (evidence / 'baseline.c').write_text(original)
        failures = []
        for intervention, candidate in cases.items():
            # Paired A4/V1 and V2 are discriminating: V1 forced LAND succeeded
            # while V2 failed in the prior baseline. A7 is a bounded regression
            # prefix, not evidence that the Windows symptom was fixed.
            folder = evidence / intervention
            folder.mkdir(exist_ok=True)
            source.write_text(candidate)
            (folder / 'instrumented.c').write_text(candidate)
            with (folder / 'build.log').open('w') as log:
                subprocess.run(['make', '-C', str(root)], check=True,
                               stdout=log, stderr=subprocess.STDOUT, timeout=120)
            if source.read_text() != candidate:
                raise RuntimeError('make replaced diagnostic source')
            (folder / 'source.sha256').write_text(
                hashlib.sha256(source.read_bytes()).hexdigest() + '\n')
            executable = root / 'grand_prix_route_flight'
            (folder / 'binary.sha256').write_text(
                hashlib.sha256(executable.read_bytes()).hexdigest() + '\n')
            for variant in ((1, 2) if args.activity == 4 else (7,)):
                try:
                    run_native(home, dict(os.environ, WEBEEBLOCKS_D2_DIAGNOSTIC='0.35',
                                          WEBEEBLOCKS_D2_INTERVENTION=intervention),
                               args.activity, variant)
                except (RuntimeError, OSError, subprocess.SubprocessError) as error:
                    failures.append((intervention, variant, str(error)))
                    print(f'D2 INCOMPLETE {intervention=} {variant=} {error}', flush=True)
        if failures:
            raise RuntimeError(f'D2 incomplete observations: {failures}')
    finally:
        source.write_text(original)
        # An instrumented executable must not survive the diagnostic.
        subprocess.run(['make', '-C', str(root), 'clean'], check=True, timeout=120)


if __name__ == '__main__':
    main()
