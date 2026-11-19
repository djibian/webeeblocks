#!/usr/bin/env python3
"""Open a Grand Prix lesson in the shared Linux R2025a Robot Window."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.grand_prix.launch_linux import (
    classroom_perspective, launch_graphical, prepare_route_native, render_route,
    webots_home,
)
from tools.grand_prix.route_courses_v2 import active_course_from_identifier

ROBOT_WINDOW = 'grand_prix_route_v2'
SETUP_TAG = '<script src="setup.js"></script>'
PROFILES = 'blockly/webeeblocks/grand_prix_progression.js'


def prepare_lesson_project(project, activity):
    """Materialize one temporary world and a profile-specific HTML entry point."""
    course = active_course_from_identifier(f'gp-progression-v1-a{activity}-v1')
    scene = render_route(course)

    plugins = ROOT / 'plugins/robot_windows'
    if not (plugins / PROFILES).is_file():
        raise RuntimeError('Profils Blockly de la progression Grand Prix introuvables')
    original = plugins / ROBOT_WINDOW
    page = original / (ROBOT_WINDOW + '.html')
    html = page.read_text(encoding='utf-8')
    if html.count(SETUP_TAG) != 1 or 'data-progression-activity' in html:
        raise RuntimeError('Point d’entrée Blockly Grand Prix incohérent')
    html = html.replace(SETUP_TAG,
        f'<script src="../{PROFILES}"></script>\n  '
        f'<script src="setup.js" data-progression-activity="{activity}"></script>')

    worlds = project / 'worlds'
    worlds.mkdir()
    world = worlds / f'grand_prix_progression_a{activity}.wbt'
    world.write_text(scene, encoding='utf-8')
    world.with_name('.' + world.stem + '.wbproj').write_text(
        classroom_perspective(ROOT), encoding='utf-8')

    (project / 'controllers').symlink_to(ROOT / 'controllers', target_is_directory=True)
    windows = project / 'plugins/robot_windows'
    selected = windows / ROBOT_WINDOW
    selected.mkdir(parents=True)
    for name in ('blockly', 'blockly_v2'):
        (windows / name).symlink_to(plugins / name, target_is_directory=True)
    for name in ('setup.js', 'fps_settings.js', 'fps_settings.css'):
        (selected / name).symlink_to(original / name)
    (selected / page.name).write_text(html, encoding='utf-8')
    return world


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Prévisualisation enseignante Linux du Grand Prix pédagogique')
    parser.add_argument('--activity', type=int, choices=(1,), default=1,
                        help='activité disponible dans ce candidat (A1)')
    parser.add_argument('--webots-home', help='installation officielle Webots R2025a')
    parser.add_argument('--preflight-only', action='store_true',
                        help='préparer le monde et le pilote sans ouvrir la simulation')
    args = parser.parse_args(argv)
    try:
        if not args.preflight_only and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            raise RuntimeError('Session graphique Linux absente')
        with tempfile.TemporaryDirectory(prefix='webeeblocks-grand-prix-') as temporary:
            world = prepare_lesson_project(Path(temporary), args.activity)
            home = webots_home(args.webots_home)
            env = prepare_route_native(home)
            if args.preflight_only:
                print('Préflight A1 terminé. Aucun vol simulé exécuté.')
                return 0
            return launch_graphical(home, world, env, mode='realtime').returncode
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Échec du lancement Grand Prix A{args.activity} : {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
