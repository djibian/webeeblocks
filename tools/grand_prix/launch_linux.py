#!/usr/bin/env python3
"""Graphical Linux launcher for historical gp-u-v1, NOT variable #808 routes."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.layout_u import generate, world_text
VERSION = 'R2025a'
PREFIX = 'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/'


def find_home(explicit, environment):
    if explicit:
        return Path(explicit).expanduser().resolve()
    if environment.get('WEBOTS_HOME'):
        return Path(environment['WEBOTS_HOME']).expanduser().resolve()
    binary = shutil.which('webots')
    if binary:
        return Path(binary).resolve().parent
    raise RuntimeError('Webots introuvable : définir WEBOTS_HOME ou --webots-home')


def verify_install(home):
    version_file = home/'resources/version.txt'
    version = version_file.read_text().strip() if version_file.is_file() else 'absent'
    if version != VERSION:
        raise RuntimeError(f'Webots {VERSION} requis, trouvé : {version}')
    binary = home/'webots'
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f'Exécutable Webots non disponible : {binary}')
    if not (home/'resources/Makefile.include').is_file():
        raise RuntimeError('Makefile.include manquant dans Webots')
    for command in ('make', 'g++'):
        if not shutil.which(command):
            raise RuntimeError(f'Outil de compilation manquant : {command}')
    for name in ('controllers/grand_prix_u_flight/Makefile',
                 'controllers/grand_prix_u_evaluator/grand_prix_u_evaluator.py',
                 'plugins/robot_windows/grand_prix_u/grand_prix_u.html',
                 'worlds/.crazyflie_runtime_v2.wbproj'):
        if not (ROOT/name).is_file():
            raise RuntimeError(f'Source WebeeBlocks manquante : {name}')
    return binary


def render(seed):
    layout = generate(seed, 2.)
    content = world_text(layout, controller='grand_prix_u_flight',
                         window='grand_prix_u', evaluator=True)
    if content.count(PREFIX) != 4:
        raise RuntimeError('EXTERNPROTO R2025a incomplets')
    content = content.replace(PREFIX, 'webots://')
    if ('window "grand_prix_u"' not in content or
            'controller "grand_prix_u_evaluator"' not in content or
            'basicTimeStep 8' not in content):
        raise RuntimeError('Monde Grand Prix U incomplet')
    return content


def create_once(path, content):
    """Existing or concurrent world is reused only if byte-identical."""
    if path.is_symlink():
        raise RuntimeError(f'Lien symbolique refusé : {path}')
    try:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(content)
    except FileExistsError:
        if (path.is_symlink() or not path.is_file() or
                path.read_text(encoding='utf-8') != content):
            raise RuntimeError(f'Fichier déjà modifié, non écrasé : {path}')


def world_for(seed):
    world = ROOT/'worlds'/f'grand_prix_u_teacher_seed{seed}.wbt'
    perspective = ROOT/'worlds'/f'.grand_prix_u_teacher_seed{seed}.wbproj'
    create_once(world, render(seed))
    if perspective.is_symlink():
        raise RuntimeError('Perspective symbolique refusée')
    if not perspective.exists():
        create_once(perspective, (ROOT/'worlds/.crazyflie_runtime_v2.wbproj').read_text())
    elif not perspective.is_file():
        raise RuntimeError('Perspective Webots non régulière')
    return world


def main(argv=None):
    parser = argparse.ArgumentParser(description='Grand Prix U historique Linux/Webots GUI')
    parser.add_argument('--seed', type=int, default=4)
    parser.add_argument('--webots-home', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        generate(args.seed, 2.)  # reject before side effects
        home = find_home(args.webots_home, os.environ)
        binary = verify_install(home)
        print(f'Grand Prix U historique, seed {args.seed}, Webots {VERSION} : {home}', flush=True)
        if args.check_only:
            print('Préflight OK ; aucune interface Webots ouverte ou testée.', flush=True)
            return 0
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            raise RuntimeError('Session graphique DISPLAY/WAYLAND_DISPLAY absente')
        env = os.environ.copy()
        env['WEBOTS_HOME'] = str(home)
        subprocess.run(['make', '-C', str(ROOT/'controllers/grand_prix_u_flight')],
                       env=env, check=True)
        target = world_for(args.seed)
        print('Ouverture Webots GUI + Blockly ; vérifier le parcours utilisateur : '+str(target), flush=True)
        return subprocess.run([str(binary), '--stdout', '--stderr', '--mode=run', str(target)],
                              cwd=ROOT, env=env, check=False).returncode
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Grand Prix U : ERREUR : {exc}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
