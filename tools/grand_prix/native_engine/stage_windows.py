"""Stage a source-built R2025a engine in a private copy of the stock distribution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
BIN = Path('msys64/mingw64/bin')
PLUGINS = Path('msys64/mingw64/share/qt6/plugins')
CONTROLLER = Path('lib/controller/Controller.dll')
UPSTREAM = 'c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b'


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def checked_copy(source, dest):
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError(f'Missing built component {source}')
    shutil.copy2(source, dest)


def stage(reference, build, mingw, output):
    if output.exists():
        raise ValueError('Use a new output directory')
    if (reference / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise ValueError('Expected the stock R2025a installation')
    if subprocess.check_output(['git', '-C', str(build), 'rev-parse', 'HEAD'], text=True).strip() != UPSTREAM:
        raise ValueError('Unexpected upstream engine commit')
    shutil.copytree(reference, output, ignore=shutil.ignore_patterns('unins*.exe', 'unins*.dat'))

    for path in (BIN / 'webots-bin.exe', CONTROLLER, CONTROLLER.with_suffix('.lib'),
                 Path('include/controller/c/webots/supervisor.h')):
        checked_copy(build / path, output / path)

    # Deploy the Qt that supplied the build's headers and link libraries.
    # Remove old Qt DLLs and plugins first so no stale plugin can be loaded.
    bin_dir = output / BIN
    for dll in bin_dir.glob('Qt6*.dll'):
        dll.unlink()
    plugin_dir = output / PLUGINS
    shutil.rmtree(plugin_dir)
    tools = mingw / 'share/qt6/bin'
    deploy = next(p for p in (tools / 'windeployqt.exe', mingw / 'bin/windeployqt.exe',
                             tools / 'windeployqt6.exe', mingw / 'bin/windeployqt6.exe') if p.is_file())
    subprocess.run([str(deploy), '--release', '--no-translations', '--no-compiler-runtime',
                    '--dir', str(bin_dir), '--plugindir', str(plugin_dir),
                    str(bin_dir / 'webots-bin.exe')], check=True)
    if not (plugin_dir / 'platforms/qwindows.dll').is_file():
        raise ValueError('Qt Windows platform plugin was not deployed')

    # Resolve dependencies from the build and its MinGW sysroot before falling
    # back to the verified stock distribution or Windows system DLLs.
    objdump = mingw / 'bin/objdump.exe'
    pending = [bin_dir / 'webots-bin.exe', output / CONTROLLER, *plugin_dir.rglob('*.dll')]
    seen = set()
    import_name = re.compile(r'^\s*DLL Name:\s*(\S+)\s*$', re.M | re.I)
    while pending:
        binary = pending.pop()
        key = binary.name.lower()
        if key in seen:
            continue
        seen.add(key)
        imports = subprocess.check_output([str(objdump), '-p', str(binary)], text=True, errors='replace')
        for name in import_name.findall(imports):
            target = bin_dir / name
            for base in (build / BIN, mingw / 'bin'):
                candidate = base / name
                if candidate.is_file():
                    if not name.lower().startswith('qt6'):
                        checked_copy(candidate, target)
                    break
            if target.is_file():
                pending.append(target)

    # Keep upstream attribution and the toolchain's license texts alongside
    # the binaries copied from the MinGW environment.
    licenses = mingw / 'share/licenses'
    if not licenses.is_dir():
        raise ValueError('Missing MinGW runtime licenses')
    shutil.copytree(licenses, output / 'native-engine-mingw-licenses')
    files = (BIN / 'webots-bin.exe', CONTROLLER, PLUGINS / 'platforms/qwindows.dll')
    manifest = {'upstream': UPSTREAM, 'patches': (HERE / 'patches.lock').read_text().splitlines(),
                'assembly': subprocess.check_output(
                    ['git', '-C', str(HERE), 'rev-parse', 'HEAD'], text=True).strip(),
                'files': {path.as_posix(): digest(output / path) for path in files}}
    (output / 'native-engine.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if any(manifest['files'][path.as_posix()] == digest(reference / path)
           for path in (BIN / 'webots-bin.exe', CONTROLLER)):
        raise ValueError('Engine and Controller must both come from the source build')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'build', 'mingw', 'output'):
        parser.add_argument(name, type=lambda path: Path(path).resolve())
    args = parser.parse_args()
    stage(args.reference, args.build, args.mingw, args.output)


if __name__ == '__main__':
    main()
