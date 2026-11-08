"""Run a paired Webots R2025a physics-frame diagnostic on one host."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent


def distribution(root):
    if os.name == 'nt':
        executable = root / 'msys64/mingw64/bin/webots.exe'
        if not executable.is_file():
            executable = root / 'msys64/mingw64/bin/webotsw.exe'
        return executable, executable.with_name('webots-bin.exe'), root / 'lib/controller/Controller.dll'
    return root / 'webots', root / 'bin/webots-bin', root / 'lib/controller/libController.so'


def fingerprint(root):
    if (root / 'resources/version.txt').read_text(encoding='utf-8').strip() != 'R2025a':
        raise ValueError(f'{root} is not Webots R2025a')
    launch, binary, controller = distribution(root)
    if not launch.is_file():
        raise FileNotFoundError(launch)
    digests = {}
    for file in (binary, controller):
        with file.open('rb') as source:
            digests[file.name] = hashlib.file_digest(source, 'sha256').hexdigest()
    return digests


def compare(reference, candidate, label):
    for key in ('steps', 'start_sim_ms', 'supervisor_id', 'target_id', 'child_id', 'descendant_contacts'):
        if reference[key] != candidate[key]:
            raise ValueError(f'{label}: mismatched {key}')
    for index, (expected, actual) in enumerate(zip(reference['observations'], candidate['observations'], strict=True)):
        vectors = zip(expected[:3], actual[:3], strict=True)
        expected_contacts, actual_contacts = expected[3], actual[3]
        same_vectors = all(math.isclose(x, y, abs_tol=1e-8, rel_tol=1e-8)
                           for a, b in vectors for x, y in zip(a, b, strict=True))
        same_contacts = len(expected_contacts) == len(actual_contacts) and all(
            a_id == b_id and all(math.isclose(x, y, abs_tol=1e-8, rel_tol=1e-8)
                                 for x, y in zip(a, b, strict=True))
            for (a, a_id), (b, b_id) in zip(expected_contacts, actual_contacts, strict=True)
        )
        if not (same_vectors and same_contacts):
            raise ValueError(f'{label}: physics mismatch at sample {index + 1}')


def summarize(records, warmup):
    measured = records['timings_ns'][warmup:]
    wall_ns = measured[-1][2] - measured[0][0]
    cycle = [following[0] - previous[0] for previous, following in zip(measured, measured[1:])]
    ordered = sorted(cycle)
    read = sorted(row[2] - row[1] for row in measured)
    return {
        'speed_x': len(measured) * 8_000_000 / wall_ns,
        'cycle_p50_ms': ordered[math.ceil(0.50 * len(ordered)) - 1] / 1e6,
        'cycle_p95_ms': ordered[math.ceil(0.95 * len(ordered)) - 1] / 1e6,
        'cycle_p99_ms': ordered[math.ceil(0.99 * len(ordered)) - 1] / 1e6,
        'cycle_max_ms': ordered[-1] / 1e6,
        'step_mean_ms': sum(row[1] - row[0] for row in measured) / len(measured) / 1e6,
        'read_mean_ms': sum(read) / len(read) / 1e6,
        'read_p99_ms': read[math.ceil(0.99 * len(read)) - 1] / 1e6,
    }


def run_external(command, root, directory, controller, env, settings, log):
    env.update(WEBOTS_HOME=str(root), WEBOTS_CONTROLLER_URL=(
        f'tcp://127.0.0.1:{settings.tcp_port}/physics-frame-probe'))
    env['PYTHONPATH'] = str(root / 'lib/controller/python')
    controller_process = None
    with subprocess.Popen(command, env=env, cwd=directory, stdout=log, stderr=log) as engine:
        try:
            deadline = time.monotonic() + settings.timeout
            while 'Waiting for local or remote connection' not in (
                    directory / 'webots.log').read_text(encoding='utf-8', errors='replace'):
                if engine.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError(f'Webots external controller startup failed: {directory}')
                time.sleep(0.05)
            with (directory / 'controller.log').open('wb') as controller_log:
                controller_process = subprocess.Popen(
                    [sys.executable, str(controller)], env=env, cwd=controller.parent,
                    stdout=controller_log, stderr=controller_log)
                remaining = max(0.1, deadline - time.monotonic())
                if controller_process.wait(timeout=remaining) != 0:
                    raise RuntimeError(f'external controller failed: {directory}')
                if engine.wait(timeout=max(0.1, deadline - time.monotonic())) != 0:
                    raise RuntimeError(f'Webots failed: {directory}')
        finally:
            if controller_process is not None and controller_process.poll() is None:
                controller_process.kill()
                controller_process.wait()
            if engine.poll() is None:
                engine.kill()
                engine.wait()


def run(root, directory, lane, settings):
    controller = directory / 'controllers/observe'
    worlds = directory / 'worlds'
    controller.mkdir(parents=True)
    worlds.mkdir()
    shutil.copyfile(HERE / 'probe.py', controller / 'observe.py')
    world = worlds / 'observation.wbt'
    source = (HERE / 'observation.wbt').read_text(encoding='utf-8')
    source = source.replace('  basicTimeStep 8', f'  basicTimeStep 8\n  FPS {settings.fps}')
    if settings.tcp_port is not None:
        source = source.replace('controller "observe"', 'controller "<extern>"')
    world.write_text(source, encoding='utf-8')
    trace = directory / 'trace.json'
    env = {name: value for name, value in os.environ.items()
           if name.lower() not in {'http_proxy', 'https_proxy', 'all_proxy', 'webots_home'}}
    env.update(WEEBEE_FRAME_MODE=lane, WEEBEE_FRAME_STEPS=str(settings.steps),
               WEEBEE_FRAME_RESULT=str(trace))
    executable, _, _ = distribution(root)
    command = [str(executable), '--batch', '--stdout', '--stderr', f'--mode={settings.mode}']
    if not settings.render:
        command.append('--no-rendering')
    if settings.tcp_port is not None:
        command += ['--extern-urls', f'--port={settings.tcp_port}']
    command.append(str(world))
    with (directory / 'webots.log').open('wb') as log:
        if settings.tcp_port is not None:
            run_external(command, root, directory, controller / 'observe.py', env, settings, log)
        else:
            subprocess.run(command, env=env, cwd=directory, stdout=log, stderr=log,
                           timeout=settings.timeout, check=True)
    result = json.loads(trace.read_text(encoding='utf-8'))
    if (result['mode'] != lane or result['steps'] != settings.steps or
            len(result['timings_ns']) != settings.steps or len(result['observations']) != settings.steps):
        raise ValueError(f'incomplete trace: {trace}')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official', type=Path, required=True)
    parser.add_argument('--patched', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--steps', type=int, default=600)
    parser.add_argument('--warmup', type=int, default=125)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--tcp-port', type=int, help='run the probe as an external loopback controller')
    parser.add_argument('--mode', choices=('fast', 'realtime'))
    parser.add_argument('--fps', type=int, choices=(25, 30, 60), default=25)
    settings = parser.parse_args()
    if not (125 <= settings.steps and 0 <= settings.warmup <= settings.steps - 2 and settings.repeats >= 1):
        parser.error('need at least 125 steps, two measured cycles and a positive repeat count')
    if settings.tcp_port is not None and not 1024 <= settings.tcp_port <= 65535:
        parser.error('TCP port must be 1024..65535')
    settings.mode = settings.mode or ('realtime' if settings.render else 'fast')
    official, patched, output = (path.resolve() for path in (settings.official, settings.patched, settings.output))
    fingerprints = {'official': fingerprint(official), 'patched': fingerprint(patched)}
    if fingerprints['official'] == fingerprints['patched']:
        parser.error('official and patched engine/library must be distinct builds')
    output.mkdir(parents=True, exist_ok=False)
    reference = run(official, output / 'official', 'baseline', settings)
    shadow = run(patched, output / 'shadow', 'shadow', settings)
    compare(reference, shadow, 'official vs patched shadow')
    summary = {
        'engine_fingerprints': fingerprints, 'host': platform.platform(),
        'mode': settings.mode, 'render': settings.render, 'fps_setting': settings.fps,
        'transport': 'tcp-loopback' if settings.tcp_port is not None else 'local',
        'steps': settings.steps, 'warmup_steps': settings.warmup,
        'shadow_equal_steps': shadow['steps'], 'descendant_contacts': shadow['descendant_contacts'],
        'runs': [],
    }
    for index in range(settings.repeats):
        # Both timed arms use the same patched executable. Only the observation
        # strategy changes. The official run is a separate physics control.
        lanes = ('baseline', 'compact') if index % 2 == 0 else ('compact', 'baseline')
        for lane in lanes:
            result = run(patched, output / f'{index + 1}-{lane}', lane, settings)
            compare(reference, result, lane)
            summary['runs'].append({'pair': index + 1, 'lane': lane, **summarize(result, settings.warmup)})
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
