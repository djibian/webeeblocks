"""Start one paired Windows route measurement with the bundled engine."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent


def require_robot_window_project(world):
    """Refuse partial/filtered extraction that would silently hide Blockly."""
    if not world.is_file():
        raise ValueError(f'Monde Grand Prix manquant : {world.name}')
    perspective = world.with_name('.' + world.stem + '.wbproj')
    if not perspective.is_file():
        raise ValueError(f'Perspective Webots manquante : {perspective.name}. Re-extraire le ZIP complet.')
    if 'robotWindow: Crazyflie WebeeBlocks' not in perspective.read_text(encoding='utf-8').splitlines():
        raise ValueError(f'Fenêtre Blockly non configurée dans {perspective.name}.')
    if not (ROOT / 'plugins/robot_windows/grand_prix_route_v2/grand_prix_route_v2.html').is_file():
        raise ValueError('Plugin de fenêtre Blockly du Grand Prix manquant.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course', type=int, choices=(0, 5, 11), default=5)
    parser.add_argument('--fps', type=int, choices=(25, 30, 60), default=60)
    parser.add_argument('--arm', choices=('A', 'B', 'budget'), default='A')
    args = parser.parse_args()
    home = ROOT.parent / 'Webots-R2025a-experimental'
    engine = home / 'msys64/mingw64/bin/webots-bin.exe'
    if not engine.is_file():
        parser.error('Extraire le moteur Windows dans le dossier voisin Webots-R2025a-experimental.')
    manifest = (ROOT / 'native-engine.json').read_bytes()
    if manifest != (home / 'native-engine.json').read_bytes():
        parser.error('Le moteur et le projet doivent provenir de la même construction.')
    for name, expected in json.loads(manifest)['files'].items():
        with (home / name).open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != expected:
                parser.error(f'Empreinte du moteur différente pour {name}.')
    world = ROOT / f'worlds/route-{args.course}-{args.fps}.wbt'
    try:
        require_robot_window_project(world)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    trace = ROOT / 'traces' / f'{args.course}-{args.fps}-{args.arm}-{time.time_ns()}'
    trace.mkdir(parents=True)
    env = {key.upper(): value for key, value in os.environ.items()}
    system = Path(env['SYSTEMROOT'])
    env['PATH'] = os.pathsep.join(str(path) for path in (
        engine.parent, engine.parent / 'cpp', home / 'msys64/usr/bin',
        system / 'System32', system))
    env.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
    env.update(WEBOTS_HOME=str(home), QT_ENABLE_HIGHDPI_SCALING='1',
               WEBEEBLOCKS_GP_PYTHON_DIR=str(ROOT / 'runtime/python'),
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
               WEBEEBLOCKS_GP_STEP_WALL_PROBE='1', WEBOTS_RENDER_TRACE='1',
               WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE='100' if args.arm == 'A' else '50',
               WEBOTS_EXPERIMENT_RENDER_DUTY='35' if args.arm == 'budget' else '0')
    command = [str(engine), '--mode=realtime', '--stdout', '--stderr',
               f'--log-performance={trace / "native.log"},0', str(world)]
    print(f'Journaux dans {trace}', flush=True)
    (trace / 'trial.json').write_text(json.dumps({
        'assembly': json.loads(manifest)['assembly'], 'arm': args.arm, 'course': args.course,
        'render_fps_cap': args.fps, 'command': command,
    }, indent=2) + '\n', encoding='utf-8')
    # Webots R2025a needs pipe handles for redirected controller logs on Windows.
    with (trace / 'webots.log').open('wb') as log, subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as child:
        for chunk in iter(child.stdout.read1, b''):
            log.write(chunk)
            log.flush()
        return child.wait()


if __name__ == '__main__':
    raise SystemExit(main())
