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
from tools.grand_prix.route_courses_v2 import (
    active_course_from_identifier, active_progression_activities,
)

ROBOT_WINDOW = 'grand_prix_route_v2'
SETUP_TAG = '<script src="setup.js"></script>'
PROFILES = 'blockly/webeeblocks/grand_prix_progression.js'

# Only the teacher-facing selection menu duplicates these presentation labels.
# Native course admission remains the authority when preparing a project.
LESSON_MENU = (
    ('Parcourir un circuit', 1),
    ('Franchir un H ouvert', 1),
    ('Répéter un trajet', 1),
    ('Observer pour adapter le déplacement', 3),
    ('Mémoriser le virage', 5),
    ('Discriminer un H ouvert', 5),
    ('Mini Grand Prix', 7),
)


def choose_lesson():
    """Optional local pre-launch chooser. Never alters a live course or .wbb."""
    if active_progression_activities() != tuple(range(1, len(LESSON_MENU) + 1)):
        raise RuntimeError('Catalogue de progression incohérent avec les cours natifs')
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as error:
        raise RuntimeError('Menu graphique indisponible : installer python3-tk') from error
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise RuntimeError('Impossible d’ouvrir le menu graphique Linux') from error

    selected = None
    root.title('WebeeBlocks — choisir une activité')
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky='nsew')
    ttk.Label(frame, text='Choisir une activité Grand Prix').grid(row=0, column=0, columnspan=2, sticky='w')
    activity = ttk.Combobox(frame, state='readonly', width=46, values=[
        f'A{number} — {label}' for number, (label, _) in enumerate(LESSON_MENU, 1)
    ])
    activity.current(0)
    activity.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(7, 10))
    ttk.Label(frame, text='Parcours :').grid(row=2, column=0, sticky='w')
    variant = ttk.Combobox(frame, state='readonly', width=8)

    def refresh_variants(_event=None):
        count = LESSON_MENU[activity.current()][1]
        variant['values'] = [str(value) for value in range(1, count + 1)]
        variant.current(0)

    activity.bind('<<ComboboxSelected>>', refresh_variants)
    refresh_variants()
    variant.grid(row=2, column=1, sticky='w')

    def launch():
        nonlocal selected
        lesson = activity.current() + 1
        choice = int(variant.get())
        if not 1 <= choice <= LESSON_MENU[lesson - 1][1]:
            return  # Fail closed; even a tampered GUI cannot select an unknown variant.
        selected = (lesson, choice)
        root.destroy()

    ttk.Button(frame, text='Lancer Webots', command=launch).grid(row=3, column=0, pady=(15, 8), sticky='w')
    ttk.Button(frame, text='Annuler', command=root.destroy).grid(row=3, column=1, pady=(15, 8), sticky='e')
    ttk.Label(frame, text='Enregistrez votre .wbb avant de fermer Webots et de changer de parcours.',
              wraplength=380).grid(row=4, column=0, columnspan=2, sticky='w')
    root.mainloop()
    return selected


def prepare_lesson_project(project, activity, variant=1):
    """Materialize one temporary world and a profile-specific HTML entry point."""
    course = active_course_from_identifier(f'gp-progression-v1-a{activity}-v{variant}')
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
    parser.add_argument('--activity', type=int, choices=active_progression_activities(), default=1,
                        help='numéro d’activité (A1 par défaut)')
    parser.add_argument('--variant', type=int, default=1,
                        help='numéro de variante choisi par l’enseignant (1 par défaut)')
    parser.add_argument('--menu', action='store_true',
                        help='choisir l’activité et la variante dans un menu graphique Linux')
    parser.add_argument('--webots-home', help='installation officielle Webots R2025a')
    parser.add_argument('--preflight-only', action='store_true',
                        help='préparer le monde et le pilote sans ouvrir la simulation')
    args = parser.parse_args(argv)
    try:
        if args.menu:
            selection = choose_lesson()
            if selection is None:
                return 0
            args.activity, args.variant = selection
        if not args.preflight_only and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            raise RuntimeError('Session graphique Linux absente')
        with tempfile.TemporaryDirectory(prefix='webeeblocks-grand-prix-') as temporary:
            world = prepare_lesson_project(Path(temporary), args.activity, args.variant)
            home = webots_home(args.webots_home)
            env = prepare_route_native(home)
            if args.preflight_only:
                print(f'Préflight A{args.activity} terminé. Aucun vol simulé exécuté.')
                return 0
            return launch_graphical(home, world, env, mode='realtime').returncode
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Échec du lancement Grand Prix A{args.activity} : {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
