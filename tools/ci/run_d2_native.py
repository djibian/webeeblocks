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
    try:
        source.write_text(instrumented)
        (evidence / 'baseline.c').write_text(original)
        (evidence / 'instrumented.c').write_text(instrumented)
        with (evidence / 'build.log').open('w') as log:
            subprocess.run(['make', '-C', str(root)], check=True,
                           stdout=log, stderr=subprocess.STDOUT, timeout=120)
        if source.read_text() != instrumented:
            raise RuntimeError('make replaced diagnostic source')
        (evidence / 'source.sha256').write_text(
            hashlib.sha256(source.read_bytes()).hexdigest() + '\n')
        failures = []
        for variant in ((1, 2, 3) if args.activity == 4 else (7,)):
            for speed in ('default', '0.35', '0.20'):
                try:
                    run_native(home, dict(os.environ, WEBEEBLOCKS_D2_DIAGNOSTIC=speed),
                               args.activity, variant)
                except (RuntimeError, OSError, subprocess.SubprocessError) as error:
                    failures.append((variant, speed, str(error)))
                    print(f'D2 INCOMPLETE {variant=} {speed=} {error}', flush=True)
        if failures:
            raise RuntimeError(f'D2 incomplete observations: {failures}')
    finally:
        source.write_text(original)
        # An instrumented executable must not survive the diagnostic.
        subprocess.run(['make', '-C', str(root), 'clean'], check=True, timeout=120)


if __name__ == '__main__':
    main()
