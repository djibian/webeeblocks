"""Real R2025a Grand Prix lesson missions and refusals via the ordinary WWI protocol."""
import argparse
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import tempfile
import time

from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.progression_courses import progression_course

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'ci-artifacts/grand-prix-u-geometry'
FORCED_LAND_ATTEMPTS = {1: (2, 3, 4, 5), 2: (2, 3, 4), 3: (2, 3), 4: (2, 3), 5: (2, 3), 6: (2, 3), 7: (2, 3)}


def run_native(home, env, activity, variant=1):
    forced_attempts = FORCED_LAND_ATTEMPTS[activity]
    course = progression_course(activity, variant)
    label = f'A{activity} variant {variant}'
    if env.get('WEBEEBLOCKS_A6_SHALLOW_CONTACT_DIAGNOSTIC') == '1' and activity != 6:
        raise RuntimeError('Shallow diagnostic is restricted to Draft A6')
    suffix = '-shallow-diagnostic' if env.get('WEBEEBLOCKS_A6_SHALLOW_CONTACT_DIAGNOSTIC') == '1' else ''
    out = OUT / ((f'route-a{activity}-v{variant}-native' if activity >= 4
                  else f'route-a{activity}-native') + suffix)
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('The progression requires the real R2025a engine')
    out.mkdir(parents=True, exist_ok=True)
    env = dict(env, WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    with tempfile.TemporaryDirectory(prefix='gp-progression-native-') as temporary:
        folder = Path(temporary)
        for key, name in (('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'),
                          ('XDG_RUNTIME_DIR', 'runtime')):
            directory = folder / name
            directory.mkdir(mode=0o700)
            env[key] = str(directory)
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        (folder / 'worlds').mkdir()
        for name in ('controllers', 'plugins'):
            (folder / name).symlink_to(ROOT / name, target_is_directory=True)
        world = folder / f'worlds/a{activity}.wbt'
        world.write_text(active_course_world(course), encoding='utf-8')
        (out / 'world.wbt').write_bytes(world.read_bytes())
        command = [str(home / 'webots'), '--batch', '--stdout',
                   '--stderr', '--mode=fast', '--minimize', '--no-rendering',
                   f'--port={port}', str(world)]
        if not env.get('DISPLAY'):
            command[:0] = ['xvfb-run', '-a', '-e', str(out / 'xvfb.log')]
        journal = out / 'webots.log'
        with journal.open('w') as native, (out / 'wwi.log').open('w') as wwi:
            process = subprocess.Popen(command, cwd=folder, env=env, stdout=native,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                limit = time.monotonic() + 45
                while 'WEBEEBLOCKS_RUNTIME_V2 READY' not in journal.read_text(errors='replace'):
                    if process.poll() is not None or time.monotonic() >= limit:
                        raise RuntimeError(f'Webots {label} did not start: {journal}')
                    time.sleep(.10)
                subprocess.run(['node', str(ROOT / 'tools/ci/grand_prix_progression_node_probe.js'),
                                str(port), str(activity), str(variant)], cwd=ROOT,
                                env=dict(env, WEBEEBLOCKS_A6_WBB_OUT=str(out / 'a6-witness.wbb'),
                                         WEBEEBLOCKS_A7_WBB_OUT=str(out / 'a7-witness.wbb')),
                                stdout=wwi,
                               stderr=subprocess.STDOUT, check=True, timeout=450)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
    log = journal.read_text(errors='replace')
    if re.search(r'^ERROR:|^Traceback \(most recent call last\)', log, re.M):
        raise RuntimeError(f'Native Webots error in {label}')
    starts = re.findall(r'^GP_U_ADMISSION attempt=(\d+) start_ms=(\d+)$', log, re.M)
    deadlines = re.findall(r'^GP_U_DEADLINE time_ms=(\d+) command=LAND interrupted_id=(-?\d+)$',
                           log, re.M)
    expected_last_attempt = 4 if activity == 7 else forced_attempts[-1]
    if ([int(attempt) for attempt, _ in starts] != list(range(1, expected_last_attempt + 1)) or
            len(deadlines) != len(forced_attempts)):
        raise RuntimeError(f'Missing exact {label} admission/RESET and forced LAND sequence')
    origin_times = {int(attempt): int(stamp) for attempt, stamp in starts}
    elapsed = [int(stamp) - origin_times[attempt] for (stamp, _), attempt in
               zip(deadlines, forced_attempts)]
    early_landings = elapsed[:-1] if activity == 1 else elapsed
    if (not all(0 < stamp < 210000 for stamp in early_landings) or
            (activity == 1 and elapsed[-1] != 210000)):
        raise RuntimeError(f'{label} forced LAND violates the 210000 ms deadline')
    if activity == 7:
        import hashlib
        project = out / 'a7-witness.wbb'
        if not project.is_file() or len(project.read_bytes()) < 100:
            raise RuntimeError(f'{label} product .wbb bytes absent')
        if not re.search(r'^A7_WBB_PRODUCT_PASS ', (out / 'wwi.log').read_text(), re.M):
            raise RuntimeError(f'{label} missing product Blockly/AST/interpreter verdict')
        print(f'PASS A7 product .wbb SHA256={hashlib.sha256(project.read_bytes()).hexdigest()}')
    print(f'PASS native R2025a {label} mission, refusals and confirmed LAND')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--activity', type=int, choices=tuple(FORCED_LAND_ATTEMPTS), required=True)
    parser.add_argument('--variant', type=int, default=1)
    args = parser.parse_args()
    try:
        progression_course(args.activity, args.variant)
    except ValueError as error:
        parser.error(str(error))
    run_native(Path(os.environ['WEBOTS_HOME']), os.environ.copy(), args.activity, args.variant)
