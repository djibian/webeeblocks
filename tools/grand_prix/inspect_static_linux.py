#!/usr/bin/env python3
"""Interactive inspection of a complete but inert variable Grand Prix course.

This is geometry-only: no Blockly, mission evaluator, movement, attempt,
RESET/READY, or native perception/contact qualification is provided.
"""
import argparse
import os
from pathlib import Path
import sys
import tempfile

# Direct execution from any cwd must import the checkout, not site packages.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.grand_prix.course_static_world_v2 import static_course_world
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.launch_linux import (
    ROOT, ensure_webots_assets, launch_graphical, webots_home,
)


def render_preview(index):
    """Pure host composition. No valid index authorizes a mission."""
    if type(index) is not int or not 0 <= index < 12:
        raise ValueError('indice de parcours attendu entre 0 et 11')
    course = reference_course(index)
    world = static_course_world(course)
    if (world.count('controller "<none>"') != 1 or
            world.count('window "<none>"') != 1 or
            'GP_ROUTE_EVALUATOR' in world or
            'controller "grand_prix_u_flight"' in world or
            'controller "grand_prix_route_v2"' in world):
        raise RuntimeError('le monde statique contient une autorité inattendue')
    return course.identifier, world


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='INSPECTION SEULEMENT : parcours Grand Prix variable inerte sous Webots R2025a')
    parser.add_argument('--index', type=int, choices=range(12), required=True,
                        help='parcours reproductible 0..11 (ex. 5 = GD mixte)')
    parser.add_argument('--webots-home',
                        help='installation complète officielle Webots R2025a')
    args = parser.parse_args(argv)
    try:
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            raise RuntimeError('session graphique Linux absente')
        identifier, source = render_preview(args.index)
        home = webots_home(args.webots_home)
        ensure_webots_assets(home)  # local, pinned bytes; no network fallback
        fd, name = tempfile.mkstemp(prefix='gp_v2_static_', suffix='.wbt',
                                    dir=ROOT / 'worlds')
        world = Path(name)
        project = world.with_name('.' + world.stem + '.wbproj')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                output.write(source)
            print('INSPECTION STATIQUE UNIQUEMENT : ' + identifier, flush=True)
            print('Pas de Blockly, évaluateur, mission ni vol ; aucune qualification native.',
                  flush=True)
            env = os.environ.copy()
            env['WEBOTS_HOME'] = str(home)
            return launch_graphical(home, world, env).returncode
        finally:
            world.unlink(missing_ok=True)
            project.unlink(missing_ok=True)
    except (OSError, ValueError, RuntimeError) as error:
        print('ÉCHEC inspection statique Grand Prix Linux : ' + str(error),
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
