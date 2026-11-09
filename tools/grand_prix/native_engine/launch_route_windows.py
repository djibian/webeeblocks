"""Start one paired Windows route measurement with the bundled engine."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit
import subprocess
import time

ROOT = Path(__file__).resolve().parent


class _RobotWindowDependencies(HTMLParser):
    """Collect static local JS/CSS references from the actual Robot Window."""
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'script' and values.get('src'):
            self.references.append(values['src'])
        elif tag == 'link' and values.get('rel') == 'stylesheet' and values.get('href'):
            self.references.append(values['href'])


def require_blockly_assets(plugin):
    """Refuse a partial ZIP before a seemingly valid GUI/runtime benchmark."""
    parser = _RobotWindowDependencies()
    parser.feed(plugin.read_text(encoding='utf-8'))
    if not parser.references or not any(
            urlsplit(ref).path == '../blockly/webeeblocks/activity_contract.js'
            for ref in parser.references):
        raise ValueError('Dépendance Blockly activity_contract.js absente de la fenêtre.')
    for reference in parser.references:
        url = urlsplit(reference)
        if url.scheme or url.netloc or not url.path or url.path.startswith('/'):
            raise ValueError(f'Ressource Blockly non locale : {reference}')
        path = (plugin.parent / url.path).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            raise ValueError(f'Ressource Blockly locale manquante : {reference}')


def require_robot_window_project(world):
    """Refuse partial/filtered extraction that would silently hide Blockly."""
    if not world.is_file():
        raise ValueError(f'Monde Grand Prix manquant : {world.name}')
    perspective = world.with_name('.' + world.stem + '.wbproj')
    if not perspective.is_file():
        raise ValueError(f'Perspective Webots manquante : {perspective.name}. Re-extraire le ZIP complet.')
    if 'robotWindow: Crazyflie WebeeBlocks' not in perspective.read_text(encoding='utf-8').splitlines():
        raise ValueError(f'Fenêtre Blockly non configurée dans {perspective.name}.')
    plugin = ROOT / 'plugins/robot_windows/grand_prix_route_v2/grand_prix_route_v2.html'
    if not plugin.is_file():
        raise ValueError('Plugin de fenêtre Blockly du Grand Prix manquant.')
    require_blockly_assets(plugin)



def require_project_world_integrity(world):
    """Verify the selected A/B world against the archive's immutable file inventory."""
    try:
        manifest = (ROOT / 'MANIFEST.sha256').read_text(encoding='utf-8')
    except OSError as error:
        raise ValueError('Manifeste SHA-256 du projet absent ou illisible.') from error
    key = world.relative_to(ROOT).as_posix()
    expected = None
    for row in manifest.splitlines():
        pieces = row.split('  ', 1)
        if (len(pieces) != 2 or len(pieces[0]) != 64 or not pieces[1] or
                any(c not in '0123456789abcdef' for c in pieces[0])):
            raise ValueError('Manifeste SHA-256 du projet malformé.')
        digest, path = pieces
        if path == key:
            if expected is not None:
                raise ValueError('Entrée du monde dupliquée dans le manifeste.')
            expected = digest
    if expected is None:
        raise ValueError('Monde choisi absent du manifeste SHA-256.')
    try:
        with world.open('rb') as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
            actual = digest.hexdigest()
    except OSError as error:
        raise ValueError('Impossible de lire le monde sélectionné.') from error
    if actual != expected:
        raise ValueError('Monde modifié depuis le conditionnement : re-extraire le ZIP.')


def require_robot_window_archive_integrity():
    """Attest static HTML/JS/CSS bytes used by the packaged Blockly window.

    A present dependency is not sufficient for a comparable native A/B run:
    after extraction it must still match the package's immutable inventory.
    This cannot attest actual GUI loading or mutable pupil .wbb projects.
    """
    plugin = ROOT / 'plugins/robot_windows/grand_prix_route_v2/grand_prix_route_v2.html'
    try:
        inventory = (ROOT / 'MANIFEST.sha256').read_text(encoding='utf-8').splitlines()
        document = plugin.read_text(encoding='utf-8')
    except OSError as error:
        raise ValueError('Manifeste ou fenêtre Blockly absent.') from error
    expected = {}
    for row in inventory:
        fields = row.split('  ', 1)
        if (len(fields) != 2 or len(fields[0]) != 64 or not fields[1] or
                any(c not in '0123456789abcdef' for c in fields[0]) or
                fields[1] in expected):
            raise ValueError('Inventaire SHA-256 Blockly malformé ou dupliqué.')
        expected[fields[1]] = fields[0]
    parser = _RobotWindowDependencies()
    parser.feed(document)
    targets = [plugin]
    root = ROOT.resolve()
    for reference in parser.references:
        url = urlsplit(reference)
        if (url.scheme or url.netloc or not url.path or url.path.startswith('/') or
                '\\' in url.path or '%' in url.path or url.fragment):
            raise ValueError('Référence Blockly non locale.')
        targets.append((plugin.parent / url.path).resolve())
    for target in targets:
        try:
            relative = target.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError('Ressource Blockly hors du projet.') from error
        if relative not in expected:
            raise ValueError('Ressource Blockly absente du manifeste : ' + relative)
        try:
            with target.open('rb') as stream:
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
                actual = digest.hexdigest()
        except OSError as error:
            raise ValueError('Ressource Blockly inaccessible : ' + relative) from error
        if actual != expected[relative]:
            raise ValueError('Ressource Blockly modifiée : ' + relative)

def require_project_code_archive_integrity():
    """Refuse altered packaged controller/evaluator/Blockly code before an A/B trace.

    The package manifest detects accidental post-extraction changes, not a
    malicious rewrite of both a file and its manifest. Editable .wbb files and
    Webots .wbproj user preferences are intentionally excluded.
    """
    try:
        rows = (ROOT / 'MANIFEST.sha256').read_text(encoding='utf-8').splitlines()
    except OSError as error:
        raise ValueError('Manifeste SHA-256 du projet absent ou illisible.') from error
    expected = {}
    for row in rows:
        fields = row.split('  ', 1)
        if (len(fields) != 2 or len(fields[0]) != 64 or not fields[1] or
                any(c not in '0123456789abcdef' for c in fields[0]) or
                fields[1] in expected):
            raise ValueError('Inventaire SHA-256 du projet malformé ou dupliqué.')
        key = fields[1]
        if ('\\' in key or key.startswith('/') or
                any(component in ('', '.', '..') for component in key.split('/'))):
            raise ValueError('Chemin non sûr dans le manifeste du projet.')
        expected[key] = fields[0]

    required = {
        'controllers/grand_prix_route_flight/grand_prix_route_flight.exe',
        'controllers/grand_prix_route_flight/runtime.ini',
        'controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py',
        'controllers/grand_prix_route_evaluator/evaluator_impl.py',
        'controllers/grand_prix_route_evaluator/runtime.ini',
        'runtime/python/webeeblocks-gp-python.exe',
        'tools/grand_prix/route_courses_v2.py',
        'plugins/robot_windows/grand_prix_route_v2/grand_prix_route_v2.html',
        'launch_route_windows.py',
    }
    # Include all code and assets actually shipped under these immutable roots,
    # including indirectly loaded JS/CSS missed by an HTML-only dependency scan.
    selected = required | {
        key for key in expected
        if key.startswith(('controllers/', 'tools/grand_prix/',
                           'plugins/robot_windows/'))
    }
    root = ROOT.resolve()
    for key in sorted(selected):
        if key not in expected:
            raise ValueError('Composant Grand Prix absent du manifeste : ' + key)
        path = (ROOT / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Composant Grand Prix hors du projet : ' + key)
        try:
            with path.open('rb') as stream:
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
                actual = digest.hexdigest()
        except OSError as error:
            raise ValueError('Composant Grand Prix inaccessible : ' + key) from error
        if actual != expected[key]:
            raise ValueError('Composant Grand Prix modifié : ' + key)


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
        require_project_world_integrity(world)
        require_robot_window_archive_integrity()
        require_project_code_archive_integrity()
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
