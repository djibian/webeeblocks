#!/usr/bin/env python3
"""Bounded native #637 diagnostics; never an integration or hardware oracle."""
import argparse
import hashlib
import json
import re
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.ci.run_progression_autonomous_mission import observed_world, validate_observer_trace
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_events(mode, rows, native_text):
    """Completion is insufficient without every retained native RESET."""
    if any(row['event'] in ('ERROR', 'RESET_FAILED', 'TRANSPORT_ERROR', 'WALL_TIMEOUT') for row in rows):
        raise ValueError('diagnostic contains a refusal/error')
    if len([row for row in rows if row['event'] == 'COMPLETE']) != 1:
        raise ValueError('incomplete diagnostic')
    requests = [re.fullmatch(r'WEBEEBLOCKS_RUNTIME_V2 REQUEST (\d+) RESET', row['detail'])
                for row in rows if row['event'] == 'request']
    ids = [match.group(1) for match in requests if match]
    responses = [row['detail'] for row in rows if row['event'] == 'response']
    expected = 7 if mode == 'baseline' else 16
    if len(ids) != expected or len(set(ids)) != expected:
        raise ValueError('missing/duplicate RESET requests')
    if any(responses.count('WEBEEBLOCKS_RUNTIME_V2 RESPONSE ' + identifier + ' OK') != 1 for identifier in ids):
        raise ValueError('missing/ambiguous RESET acknowledgements')
    if native_text.count('WEBEEBLOCKS_RUNTIME_V2 TRACE RESET ') != expected or 'RESET_TIMEOUT' in native_text:
        raise ValueError('native RESET evidence incomplete/refuted')
    if mode == 'sweep':
        observed = [row['detail']['input']['id'] for row in rows if row['event'] == 'CASE']
        accepted = [row['detail']['id'] for row in rows if row['event'] == 'RESET_OK']
        if observed != list(range(1, 17)) or accepted != observed:
            raise ValueError('missing/duplicate synthetic cases')
    else:
        outcomes = {row['event']: row['detail'] for row in rows}
        for index in range(4):
            if outcomes.get('integrated-' + str(index)) != {'status': 'achieved'}:
                raise ValueError('historical positive case missing')
        for name in ('fixed-negative', 'memory-negative', 'front-negative'):
            if outcomes.get(name, {}).get('status') != 'not-achieved':
                raise ValueError('historical negative case missing')
    return {'mode': mode, 'reset_acknowledgements': expected,
            'collision_attempt7_observed': 'WEBEEBLOCKS_AUTONOMOUS_COLLISION attempt=7 ' in native_text,
            'scope': 'diagnostic-only; no historical failure reproduction or main-health claim'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--webots-home', required=True, type=Path)
    parser.add_argument('--assets-root', required=True, type=Path,
                        help='Exact R2025a Webots source checkout, including projects')
    parser.add_argument('--output', required=True, type=Path, help='Must not exist')
    parser.add_argument('--mode', required=True, choices=('baseline', 'sweep'))
    parser.add_argument('--xvfb', default=shutil.which('Xvfb'))
    args = parser.parse_args()
    home, assets, out = (p.resolve() for p in (args.webots_home, args.assets_root, args.output))
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('Webots R2025a required')
    asset_sha = subprocess.check_output(['git', '-C', str(assets), 'rev-parse', 'HEAD'], text=True).strip()
    if asset_sha != 'c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b':
        raise RuntimeError('exact R2025a assets required')
    if not args.xvfb:
        raise RuntimeError('Xvfb required (TCP display is used when local sockets are unavailable)')
    out.mkdir(parents=True, exist_ok=False)
    # No stale output reuse, no injected state in the passive baseline world.
    world = observed_world((ROOT / 'worlds/crazyflie_runtime_v2.wbt').read_text())
    world = world.replace('window "autonomous_probe"', 'window "<none>"')
    world = world.replace('controller "crazyflie_runtime_v2"', 'controller "<extern>"')
    world = world.replace('controller "ci_autonomous_reset_observer"', 'controller "<extern>"')
    world = world.replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', str(assets) + '/')
    (out / 'worlds').mkdir()
    target = out / 'worlds/replay.wbt'
    target.write_text(world)
    env = os.environ.copy()
    # Qt interprets ALL_PROXY as a server proxy, which prevents localhost listen.
    # All Webots assets here are local. This process performs no external fetch.
    env = {key: value for key, value in env.items() if not key.lower().endswith('_proxy')}
    env.update(WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true', LP_NUM_THREADS='1',
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
               WEBEEBLOCKS_CI_ARTIFACT_DIR=str(out))
    env['LD_LIBRARY_PATH'] = str(home / 'lib/webots') + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    # Set Xvfb and Webots to fresh available TCP ports; no persistent reservation.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        display = probe.getsockname()[1] - 6000
    if display < 0:
        raise RuntimeError('invalid ephemeral X display')
    env['DISPLAY'] = '127.0.0.1:' + str(display)
    runtime = ROOT / 'controllers/crazyflie_runtime_v2'
    with (out / 'build.log').open('w') as log:
        subprocess.run(['make', 'clean'], cwd=runtime, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['make', '-j4'], cwd=runtime, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    executable = runtime / 'crazyflie_runtime_v2'
    observer = (ROOT / 'tools/ci/fixtures/autonomous_reset_observer.py'
                if args.mode == 'baseline' else HERE / 'contact_observer.py')
    paths = [ROOT / 'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c', executable,
             ROOT / 'plugins/robot_windows/autonomous_probe/autonomous_probe.js',
             ROOT / 'plugins/robot_windows/blockly/webeeblocks/wwi_backend.js',
             ROOT / 'plugins/robot_windows/blockly/webeeblocks/interpreter.js',
             HERE / 'probe.js', HERE / 'cases.json', HERE / 'run.py', observer, target, home / 'bin/webots-bin']
    (out / 'tracked.diff').write_bytes(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--binary', 'HEAD']))
    paths.append(out / 'tracked.diff')
    (out / 'provenance.json').write_text(json.dumps({
        'scope': 'diagnostic-only-not-canonical-CI', 'mode': args.mode,
        'git_head': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'assets_sha': asset_sha, 'sha256': {str(path): digest(path) for path in paths}}, indent=2) + '\n')
    children, streams = [], []

    def launch(command, filename):
        stream = (out / filename).open('w')
        streams.append(stream)
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        children.append(child)
        return child

    def wait_for(predicate, seconds, label):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            if any(child.poll() is not None for child in children):
                raise RuntimeError('child exited before ' + label)
            time.sleep(.1)
        raise RuntimeError(label + ' missing; inspect retained logs')

    try:
        launch([args.xvfb, ':' + str(display), '-ac', '-nolisten', 'unix', '-nolisten', 'local',
                '-listen', 'tcp', '-screen', '0', '1280x1024x24'], 'xvfb.log')
        time.sleep(1)
        launch([str(home / 'webots'), '--stdout', '--stderr', '--batch', '--no-rendering',
                '--mode=fast', '--port=' + str(port), str(target)], 'webots.log')
        wait_for(lambda: (out / 'webots.log').read_text().count('Waiting for local or remote connection') >= 9,
                 60, 'nine extern controller listeners')
        cases = [('Crazyflie WebeeBlocks', executable, [])]
        for label, tag in [('sequence', 'sequence'), ('precise movement', 'precise'), ('repeat', 'repeat'),
                           ('simple decision', 'simple-decision'), ('reactive', 'reactive'),
                           ('combined decisions', 'combined-decisions'), ('autonomous strategy', 'autonomous')]:
            cases.append(('Progression ' + label + ' evaluator', executable, [tag + '-evaluator-v1']))
        cases.append(('CI autonomous read-only state observer', observer, []))
        for index, (name, script, arguments) in enumerate(cases):
            launch([str(home / 'webots-controller'), '--protocol=tcp', '--ip-address=127.0.0.1',
                    '--port=' + str(port), '--robot-name=' + name, str(script), *arguments],
                   'controller-' + str(index) + '.log')
        wait_for(lambda: 'WEBEEBLOCKS_RUNTIME_V2 READY' in (out / 'controller-0.log').read_text(),
                 35, 'runtime READY')
        child = launch(['node', str(HERE / 'probe.js'), str(port), args.mode, str(out)], 'node.log')
        result = child.wait(timeout=350)
        (out / 'exit-code.txt').write_text(str(result) + '\n')
        if result:
            raise RuntimeError('diagnostic refused; preserve logs and first refusal without retry')
        rows = [json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()]
        text = ''.join((out / ('controller-' + str(index) + '.log')).read_text() for index in range(8))
        summary = validate_events(args.mode, rows, text)
        if args.mode == 'baseline':
            validate_observer_trace(out / 'native-reset-state.jsonl', required_attempts=(7, 8))
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print('DIAGNOSTIC COMPLETED; historical RESET_TIMEOUT cause remains unproven')
    finally:
        for child in reversed(children):
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
        for stream in streams:
            stream.close()
        # Preserve successful and failed evidence, including partial traces.
        (out / 'sha256.json').write_text(json.dumps({str(path.relative_to(out)): digest(path)
            for path in out.rglob('*') if path.is_file() and path.name != 'sha256.json'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
