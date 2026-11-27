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
FORCED_LAND_ATTEMPTS = {1: (2, 3, 4, 5), 2: (2, 3, 4), 3: (2, 3), 4: (2, 3), 5: (2, 3), 6: (2, 3), 7: (2, 3), 8: (2, 3, 4, 5, 6)}


def run_native(home, env, activity, variant=1, pupil_project=None, *, rebound=None, rebound_height=None):
    if rebound is not None and (activity, variant) != (7, 5):
        raise ValueError('rebound experiments require A7/V5')
    if rebound_height is not None and (rebound not in ('stop', 'liveness') or
            rebound_height not in (.90, .8968, .8936, .8904)):
        raise ValueError('only the predeclared V5 phase stimuli are permitted')
    forced_attempts = FORCED_LAND_ATTEMPTS[activity]
    last_attempt = forced_attempts[-1]
    if activity == 4:
        if variant != 1:
            forced_attempts += (4,)
        last_attempt = 4 + (3 if pupil_project is not None else 0)
    if activity == 5:
        if pupil_project is None:
            raise ValueError('A5 needs a saved and reopened .wbb witness')
        forced_attempts += (6,)
        last_attempt = 6
    if activity == 7:
        last_attempt = 5 if variant in (2, 3, 7) else 4
        if last_attempt == 5:
            forced_attempts += (5,)
        if variant == 1:
            last_attempt = 6
            forced_attempts += (5, 6)
        if variant == 7:
            last_attempt = 6
            forced_attempts += (6,)
    if activity == 8:
        from tools.grand_prix.route_courses_v2 import reference_course
        course = reference_course(variant - 1)
        if pupil_project is None:
            raise ValueError('A8 needs a single saved .wbb witness')
    else:
        course = progression_course(activity, variant)
    label = f'A{activity} variant {variant}'
    if env.get('WEBEEBLOCKS_A6_SHALLOW_CONTACT_DIAGNOSTIC') == '1' and activity != 6:
        raise RuntimeError('Shallow diagnostic is restricted to Draft A6')
    suffix = '-shallow-diagnostic' if env.get('WEBEEBLOCKS_A6_SHALLOW_CONTACT_DIAGNOSTIC') == '1' else ''
    if rebound:
        suffix = f'-rebound-{rebound}'
        if rebound_height is not None:
            suffix += f'-h{round(rebound_height * 10000):04d}'
    out = OUT / ((f'route-a{activity}-v{variant}-native' if activity >= 4
                  else f'route-a{activity}-native') + suffix)
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('The progression requires the real R2025a engine')
    out.mkdir(parents=True, exist_ok=True)
    probe_args = [str(activity)]
    if activity in (4, 6, 7):
        probe_args.append(str(variant))
    if pupil_project is not None:
        project_copy = out / 'pupil-project.wbb'
        project_copy.write_bytes(pupil_project.read_bytes())
        probe_args.append(str(project_copy))
        if activity == 8:
            wrong = pupil_project.with_name('wrong-landing.wbb')
            wrong_copy = out / 'wrong-landing.wbb'
            wrong_copy.write_bytes(wrong.read_bytes())
            probe_args.append(str(wrong_copy))
    env = dict(env, WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    env.pop('WEBEEBLOCKS_A7_V5_HEIGHT', None)
    if rebound_height is not None:
        env['WEBEEBLOCKS_A7_V5_HEIGHT'] = str(rebound_height)
    if activity == 3:
        env['WEBEEBLOCKS_GP_A3_TRACE'] = str(out / 'trajectory.csv')
    if activity == 8:
        env['WEBEEBLOCKS_GP_A8_TRACE'] = str(out / 'trajectory.csv')
    if activity in (6, 7):
        env[f'WEBEEBLOCKS_A{activity}_WBB_OUT'] = str(out / f'a{activity}-witness.wbb')
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
        if rebound:
            from tools.ci import a7_native_rebound as experiment
            for raw in ('contacts.jsonl', 'result.json', 'identity.json', 'webots.log', 'wwi.log',
                        'pilot-latch', 'stop-request', 'stop-sent'):
                (out / raw).unlink(missing_ok=True)
            env.update(WEBEEBLOCKS_A7_V5_CASE=rebound, WEBEEBLOCKS_A7_V5_EVENTS=str(folder),
                       WEBEEBLOCKS_A7_V5_LATCH=str(folder / 'pilot-latch'))
            try:
                paths = experiment.build_project(folder, out, home, env)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                experiment.finish(out, rebound, error)
        else:
            for name in ('controllers', 'plugins'):
                (folder / name).symlink_to(ROOT / name, target_is_directory=True)
        world = folder / f'worlds/a{activity}.wbt'
        world.write_text(active_course_world(course), encoding='utf-8')
        (out / 'world.wbt').write_bytes(world.read_bytes())
        if rebound:
            experiment.provenance(out, {**paths, 'world.wbt': world}, home, env)
        command = [str(home / 'webots'), '--batch', '--stdout',
                   '--stderr', '--mode=fast', '--minimize', '--no-rendering',
                   f'--port={port}', str(world)]
        if not env.get('DISPLAY'):
            command[:0] = ['xvfb-run', '-a', '-e', str(out / 'xvfb.log')]
        journal = out / 'webots.log'
        with journal.open('w') as native, (out / 'wwi.log').open('w') as wwi:
            process = subprocess.Popen(command, cwd=folder, env=env, stdout=native,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            probe_error = None
            try:
                limit = time.monotonic() + 45
                while 'WEBEEBLOCKS_RUNTIME_V2 READY' not in journal.read_text(errors='replace'):
                    if process.poll() is not None or time.monotonic() >= limit:
                        raise RuntimeError(f'Webots {label} did not start: {journal}')
                    time.sleep(.10)
                subprocess.run(['node', str(ROOT / 'tools/ci/grand_prix_progression_node_probe.js'),
                                str(port), *probe_args], cwd=ROOT, env=env, stdout=wwi,
                               stderr=subprocess.STDOUT, check=True, timeout=450)
            except (RuntimeError, subprocess.SubprocessError) as error:
                if not rebound:
                    raise
                probe_error = error
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
        if rebound:
            for raw in ('contacts.jsonl', 'pilot-latch', 'stop-request', 'stop-sent'):
                if (folder / raw).is_file():
                    (out / raw).write_bytes((folder / raw).read_bytes())
            experiment.finish(out, rebound, probe_error)
            return
    log = journal.read_text(errors='replace')
    if re.search(r'^ERROR:|^Traceback \(most recent call last\)', log, re.M):
        raise RuntimeError(f'Native Webots error in {label}')
    starts = re.findall(r'^GP_U_ADMISSION attempt=(\d+) start_ms=(\d+)$', log, re.M)
    deadlines = re.findall(r'^GP_U_DEADLINE time_ms=(\d+) command=LAND interrupted_id=(-?\d+)$',
                           log, re.M)
    if ([int(attempt) for attempt, _ in starts] != list(range(1, last_attempt + 1)) or
            len(deadlines) != len(forced_attempts)):
        raise RuntimeError(f'Missing exact {label} admission/RESET and forced LAND sequence')
    origin_times = {int(attempt): int(stamp) for attempt, stamp in starts}
    elapsed = [int(stamp) - origin_times[attempt] for (stamp, _), attempt in
               zip(deadlines, forced_attempts)]
    exact_deadline = activity in (1, 5, 8) or (activity, variant) == (7, 7)
    early_landings = elapsed[:-1] if exact_deadline else elapsed
    if (not all(0 < stamp < 210000 for stamp in early_landings) or
            (exact_deadline and elapsed[-1] != 210000)):
        raise RuntimeError(f'{label} forced LAND violates the 210000 ms deadline')
    if activity in (1, 2, 3) and pupil_project is not None:
        import hashlib
        import json
        proof = [json.loads(line.removeprefix('A123_WBB_PRODUCT_PASS '))
                 for line in (out / 'wwi.log').read_text().splitlines()
                 if line.startswith('A123_WBB_PRODUCT_PASS ')]
        if (len(proof) != 1 or proof[0].get('activity') != activity or
                proof[0].get('blockly') != '13.2.1' or
                proof[0].get('sha256') != hashlib.sha256(project_copy.read_bytes()).hexdigest() or
                not re.fullmatch(r'[0-9a-f]{64}', proof[0].get('astSha256', ''))):
            raise RuntimeError(f'{label} missing saved Blockly product execution proof')
    if activity == 4 and pupil_project is not None:
        import json
        prefix = 'D2_A4_NORMAL_SPEED_PASS '
        proof = [json.loads(line.removeprefix(prefix))
                 for line in (out / 'wwi.log').read_text().splitlines()
                 if line.startswith(prefix)]
        if proof != [{'variant': variant, 'speed': 'default'},
                     {'variant': variant, 'speed': .35}]:
            raise RuntimeError('Missing exact A4 teacher normal-speed regression proof')
    if activity == 5 and (out / 'wwi.log').read_text().splitlines().count(
            'D3_A5_NORMAL_SPEED_PASS') != 1:
        raise RuntimeError(f'{label} missing exact A5 normal-speed mission proof')
    if activity == 7:
        import hashlib
        if variant == 7 and (out / 'wwi.log').read_text().splitlines().count(
                'D2_A7_NORMAL_SPEED_PREFIX_PASS') != 1:
            raise RuntimeError('Missing exact A7 teacher normal-speed prefix proof')
        project = out / 'a7-witness.wbb'
        if not project.is_file() or len(project.read_bytes()) < 100:
            raise RuntimeError(f'{label} product .wbb bytes absent')
        if not re.search(r'^A7_WBB_PRODUCT_PASS ', (out / 'wwi.log').read_text(), re.M):
            raise RuntimeError(f'{label} missing product Blockly/AST/interpreter verdict')
        retreats = re.findall(r'^GP_U_A7_RETREAT t=(\d+\.\d+) ', log, re.M)
        expected_retreats = 1 if variant == 2 else 0
        if len(retreats) != expected_retreats or (
                retreats and round(float(retreats[0]) * 1000) != int(deadlines[-1][0])):
            raise RuntimeError(f'{label} unexpected A7 retreat activation')
        if variant == 1:
            import json
            proofs = [json.loads(line.removeprefix('A7_STUDENT_STOP_PASS '))
                      for line in (out / 'wwi.log').read_text().splitlines()
                      if line.startswith('A7_STUDENT_STOP_PASS ')]
            expected = [(False, 'PROGRAM_INVALID', 3), (True, 'USER_STOPPED', 4)]
            if len(proofs) != 2 or any(
                    (proof.get('manual'), proof.get('code'), proof.get('forcedLandings')) != case or
                    any(proof.get(k) != v for k, v in {'takeoffs': 1, 'stops': 1, 'moves': 0,
                                                       'resets': 1, 'blockly': '13.2.1'}.items())
                    for proof, case in zip(proofs, expected)):
                raise RuntimeError('Missing exact native student-error STOP/RESET proof')
        print(f'PASS A7 product .wbb SHA256={hashlib.sha256(project.read_bytes()).hexdigest()}')
    if activity == 8:
        import csv
        import hashlib
        import json
        proof = [json.loads(line.removeprefix('A8_WBB_PRODUCT_PASS '))
                 for line in (out / 'wwi.log').read_text().splitlines()
                 if line.startswith('A8_WBB_PRODUCT_PASS ')]
        if len(proof) != 1 or proof[0]['sha256'] != hashlib.sha256(project_copy.read_bytes()).hexdigest():
            raise RuntimeError(f'{label} saved project not executed')
        with (out / 'trajectory.csv').open() as trace:
            samples = list(csv.DictReader(trace))
        if (not samples or samples[-1]['verdict'] != 'achieved' or
                int(samples[-1]['crossings']) != course.count or
                int(samples[-1]['terminal_ms']) - int(samples[0]['start_ms']) >= 210000 or
                any(int(b['time_ms']) - int(a['time_ms']) != 8
                    for a, b in zip(samples, samples[1:]))):
            raise RuntimeError(f'{label} missing continuous native mission proof')
    print(f'PASS native R2025a {label} mission, refusals and confirmed LAND')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--activity', type=int, choices=tuple(FORCED_LAND_ATTEMPTS), required=True)
    parser.add_argument('--variant', type=int, choices=range(1, 13), default=1)
    parser.add_argument('--rebound', choices=('stop', 'liveness'))
    parser.add_argument('--pupil-project', type=Path)
    args = parser.parse_args()
    if args.activity != 8 and args.variant > 7:
        parser.error('only A8 has twelve variants')
    if args.activity not in (4, 5, 6, 7, 8) and args.variant != 1:
        parser.error('only activities 4–8 have multiple active variants')
    run_native(Path(os.environ['WEBOTS_HOME']), os.environ.copy(), args.activity, args.variant,
               pupil_project=args.pupil_project, rebound=args.rebound)
