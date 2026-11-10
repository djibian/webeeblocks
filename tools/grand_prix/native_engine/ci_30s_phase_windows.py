#!/usr/bin/env python3
"""CI-only native R2025a phase acquisition: 30 simulated seconds, no GUI claim.

The engine and project are the already staged exact same-HEAD Windows artifacts.
This control deliberately disables rendering and does not submit pupil Blockly.
Never replace product safety authority or classify this as Windows acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.analyze_evaluator_phase import PREFIX, parse_windows, analyze


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_launcher(project):
    spec = importlib.util.spec_from_file_location('qualify_route_launcher',
                                                   project / 'launch_route_windows.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT.resolve() != project.resolve():
        raise ValueError('launcher is not bound to the exact project')
    return module


def run(engine, project, destination, *, max_wall_seconds, assembly):
    if platform.system() != 'Windows' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('automated native Windows GitHub runner required')
    engine = engine.resolve(strict=True)
    project = project.resolve(strict=True)
    destination.mkdir(parents=True, exist_ok=False)
    log = destination / 'webots.log'
    report = {'schema': 1, 'status': 'UNPROVEN', 'purpose': 'diagnostic-only',
              'display': 'disabled', 'visual_acceptance': 'UNPROVEN',
              'physical_timestep_ms': 8, 'required_simulated_ms': 30000,
              'scenario': 'route-5 normal pilot and evaluator, no Blockly submission',
              'assembly': assembly}
    try:
        launcher = load_launcher(project)
        manifest = (project / 'native-engine.json').read_bytes()
        if manifest != (engine / 'native-engine.json').read_bytes():
            raise ValueError('unpaired native engine and project')
        metadata = json.loads(manifest)
        if metadata.get('assembly') != assembly or (
                project / 'TARGET_SHA.txt').read_text(encoding='utf-8').strip() != assembly:
            raise ValueError('exact CI candidate mismatch')
        launcher.require_engine_archive_integrity(engine, metadata)
        world = project / 'worlds/route-5-30.wbt'
        launcher.require_robot_window_project(world)
        launcher.require_project_world_integrity(world)
        launcher.require_robot_window_archive_integrity()
        launcher.require_project_code_archive_integrity()
        executable = engine / 'msys64/mingw64/bin/webots-bin.exe'
        report.update(engine_sha256=sha256(executable), world_sha256=sha256(world))
        system = Path(os.environ['SYSTEMROOT'])
        env = dict(os.environ)
        env['PATH'] = os.pathsep.join(str(p) for p in (
            executable.parent, executable.parent / 'cpp',
            engine / 'msys64/usr/bin', system / 'System32', system))
        env.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
        env.update(WEBOTS_HOME=str(engine), WEBEEBLOCKS_GP_PYTHON_DIR=str(project / 'runtime/python'),
                   WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
                   WEBEEBLOCKS_GP_STEP_WALL_PROBE='1',
                   WEBEEBLOCKS_GP_EVALUATOR_PHASE_PROBE='1',
                   WEBOTS_RENDER_TRACE='0', WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE='100',
                   WEBOTS_EXPERIMENT_RENDER_DUTY='0')
        cmd = [str(executable), '--batch', '--mode=fast', '--no-rendering',
               '--stdout', '--stderr', str(world)]
        report['native_command_options'] = cmd[1:-1]
        course = 'gp-route-v2-L2000-2500-3000-TGD-s105-H2'
        begin = time.monotonic()
        with log.open('wb') as stream:
            child = subprocess.Popen(cmd, cwd=project, env=env, stdout=stream,
                                     stderr=subprocess.STDOUT)
            try:
                while time.monotonic() - begin < max_wall_seconds:
                    if child.poll() is not None:
                        raise RuntimeError('Webots exited before the 30-second observation')
                    time.sleep(1.0)
                    observed = log.read_text(encoding='utf-8', errors='replace')
                    if observed.count(PREFIX) < 30:
                        continue
                    raw = parse_windows(observed.splitlines())
                    selected = raw[:30]
                    result = analyze(selected, course, minimum_sim_ms=30000)
                    if result['status'] != 'MEASURED_ONLY':
                        raise RuntimeError('native observation insufficient')
                    report.update(status='MEASURED_ONLY', evaluator=result,
                                  native_complete_windows=30)
                    break
                else:
                    raise RuntimeError('timeout before 30 contiguous native phase windows')
            finally:
                # Terminate the whole child tree; a deliberately killed batch
                # process is not mistaken for a clean simulator completion.
                if child.poll() is None:
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                   capture_output=True, timeout=20, check=False)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
        report['log_sha256'] = sha256(log)
        report['limitations'] = ('Batch and rendering disabled, no Blockly submission: '
                                 'does not cover active mission oracle, OpenGL, GUI or target Lenovo.')
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        (destination / 'summary.json').write_text(
            json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0 if report['status'] == 'MEASURED_ONLY' else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'project', 'destination'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--assembly', required=True)
    p.add_argument('--max-wall-seconds', type=int, default=360)
    args = p.parse_args()
    if not 30 <= args.max_wall_seconds <= 600:
        p.error('unsupported diagnostic wall budget')
    return run(args.engine, args.project, args.destination,
               assembly=args.assembly, max_wall_seconds=args.max_wall_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
