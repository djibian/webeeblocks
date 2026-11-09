"""Compose the variable-route diagnostic project for the staged Windows engine."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from tools.grand_prix.launch_linux import configure_render_fps, ensure_webots_assets, render_route
from tools.grand_prix.route_courses_v2 import reference_course

ENGINE_EXE = 'msys64/mingw64/bin/webots-bin.exe'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package(engine, python_runtime, output):
    manifest = json.loads((engine / 'native-engine.json').read_text(encoding='utf-8'))
    sha = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if manifest['assembly'] != sha or digest(engine / ENGINE_EXE) != manifest['files'][ENGINE_EXE]:
        raise ValueError('Engine and route project must belong to the same assembly')
    ensure_webots_assets(engine)

    output.mkdir(parents=True)
    shutil.copytree(python_runtime, output / 'runtime/python')
    windows = ROOT / 'plugins/robot_windows'
    target = output / 'plugins/robot_windows'
    if (windows / 'blockly_v2/vendor/VERSION').read_text(encoding='utf-8').strip() != '13.2.1':
        raise ValueError('Expected prepared Blockly 13.2.1')
    for directory in ('blockly_v2', 'blockly/webeeblocks', 'grand_prix_route_v2'):
        shutil.copytree(windows / directory, target / directory,
                        ignore=shutil.ignore_patterns('node_modules', 'package*.json'))

    flight = output / 'controllers/grand_prix_route_flight'
    flight.mkdir(parents=True)
    shutil.copy2(ROOT / 'controllers/grand_prix_route_flight/grand_prix_route_flight.exe', flight)
    (flight / 'runtime.ini').write_text(
        '[environment variables with paths]\n'
        'WEBOTS_LIBRARY_PATH = $(WEBOTS_HOME)/lib/controller:$(WEBOTS_HOME)/msys64/mingw64/bin\n'
        'QT_PLUGIN_PATH = $(WEBOTS_HOME)/msys64/mingw64/share/qt6/plugins\n', encoding='utf-8')

    evaluator = output / 'controllers/grand_prix_route_evaluator'
    evaluator.mkdir()
    shutil.copy2(ROOT / 'controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py',
                 evaluator / 'evaluator_impl.py')
    shutil.copy2(HERE / 'route_evaluator_bootstrap.py', evaluator / 'grand_prix_route_evaluator.py')
    (evaluator / 'runtime.ini').write_text(
        '[python]\nCOMMAND = $(WEBEEBLOCKS_GP_PYTHON_DIR)/webeeblocks-gp-python.exe\n'
        'OPTIONS = -I -B\n', encoding='utf-8')
    runtime_tools = output / 'tools/grand_prix'
    runtime_tools.mkdir(parents=True)
    for module in (ROOT / 'tools/grand_prix').glob('*.py'):
        shutil.copy2(module, runtime_tools)
    # Preserve the existing read-only Windows A/B inventory and CPU/RAM
    # instruments in the standalone ZIP; no repository checkout is needed.
    for script in ('windows_host_inventory.ps1', 'capture_windows_host.ps1'):
        shutil.copy2(ROOT / 'tools/grand_prix' / script, runtime_tools / script)

    worlds = output / 'worlds'
    worlds.mkdir()
    for index in (0, 5, 11):
        scene = render_route(reference_course(index))
        for fps in (25, 30, 60):
            name = f'route-{index}-{fps}'
            (worlds / f'{name}.wbt').write_text(configure_render_fps(scene, fps), encoding='utf-8')
            (worlds / f'.{name}.wbproj').write_text(
                'Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n', encoding='utf-8')

    shutil.copy2(HERE / 'launch_route_windows.py', output)
    shutil.copy2(HERE / 'WINDOWS_ROUTE.md', output / 'README.md')
    shutil.copy2(ROOT / 'packaging/windows/grand_prix_python_lock.json', output / 'PYTHON-SOURCE.json')
    shutil.copy2(ROOT / 'packaging/windows/THIRD_PARTY_NOTICES.md', output)
    (output / 'Lancer-Grand-Prix.cmd').write_bytes(
        b'@echo off\r\nsetlocal\r\n'
        b'"%~dp0runtime\\python\\webeeblocks-gp-python.exe" -I -B "%~dp0launch_route_windows.py" %*\r\n'
        b'if errorlevel 1 pause\r\n')
    (output / 'SOURCE_SHA').write_text(sha + '\n', encoding='utf-8')
    (output / 'TARGET_SHA.txt').write_text(sha + '\n', encoding='utf-8')
    shutil.copy2(engine / 'native-engine.json', output)
    (output / 'MANIFEST.sha256').write_text(''.join(
        f'{digest(p)}  {p.relative_to(output).as_posix()}\n'
        for p in sorted(output.rglob('*')) if p.is_file()), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('engine', 'python-runtime', 'output'):
        parser.add_argument('--' + field, required=True, type=lambda value: Path(value).resolve())
    args = parser.parse_args()
    package(args.engine, args.python_runtime, args.output)


if __name__ == '__main__':
    main()
