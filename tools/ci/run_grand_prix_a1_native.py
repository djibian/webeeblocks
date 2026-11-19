"""Real R2025a A1 mission and refusals via the ordinary WWI protocol."""
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
OUT = ROOT / 'ci-artifacts/grand-prix-u-geometry/route-a1-native'


def run_native(home, env):
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('A1 requires the real R2025a engine')
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(env, WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    with tempfile.TemporaryDirectory(prefix='gp-a1-native-') as temporary:
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
        world = folder / 'worlds/a1.wbt'
        world.write_text(active_course_world(progression_course(1)), encoding='utf-8')
        (OUT / 'world.wbt').write_bytes(world.read_bytes())
        command = [str(home / 'webots'), '--batch', '--stdout',
                   '--stderr', '--mode=fast', '--minimize', '--no-rendering',
                   f'--port={port}', str(world)]
        if not env.get('DISPLAY'):
            command[:0] = ['xvfb-run', '-a', '-e', str(OUT / 'xvfb.log')]
        journal = OUT / 'webots.log'
        with journal.open('w') as native, (OUT / 'wwi.log').open('w') as wwi:
            process = subprocess.Popen(command, cwd=folder, env=env, stdout=native,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                limit = time.monotonic() + 45
                while 'WEBEEBLOCKS_RUNTIME_V2 READY' not in journal.read_text(errors='replace'):
                    if process.poll() is not None or time.monotonic() >= limit:
                        raise RuntimeError(f'Webots A1 did not start: {journal}')
                    time.sleep(.10)
                subprocess.run(['node', str(ROOT / 'tools/ci/grand_prix_a1_node_probe.js'),
                                str(port)], cwd=ROOT, env=env, stdout=wwi,
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
        raise RuntimeError('Native Webots error in A1')
    starts = re.findall(r'^GP_U_ADMISSION attempt=(\d+) start_ms=(\d+)$', log, re.M)
    deadlines = re.findall(r'^GP_U_DEADLINE time_ms=(\d+) command=LAND interrupted_id=(-?\d+)$',
                           log, re.M)
    if ([int(attempt) for attempt, _ in starts] != [1, 2, 3, 4, 5] or
            len(deadlines) != 1 or int(deadlines[0][0]) - int(starts[-1][1]) != 210000):
        raise RuntimeError('Missing exact A1 admission/RESET sequence and 210000 ms LAND')
    print('PASS native R2025a A1: finish, RESET, low flight, closed H, STOP and 210000-ms LAND')


if __name__ == '__main__':
    run_native(Path(os.environ['WEBOTS_HOME']), os.environ.copy())
