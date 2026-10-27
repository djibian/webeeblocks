#!/usr/bin/env python3
"""Bounded NON-GATE Windows product startup on the disposable #665 runtime.

Uses the unchanged classroom archive from canonical run 40386450869 (source
1899293f458f6497dd1c0c024231173bb84f44fe). No flight/program is submitted.
This is neither current-main acceptance nor a distributable Webots package.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


# SHA-256 of the real corrected Windows R2025a engine built in run 40415782024.
# The digest from pe.sha256 is self-declared by its artifact and is NOT an
# authority: a matching archive/installation pair could both be unqualified.
QUALIFIED_WINDOWS_PE_SHA256 = '52b8c047047094c30f0cd358456ca5a18c73209457c2129991068f5825c8a06e'


def attest_qualified_pe(artifact, installed):
    record = (artifact / 'pe.sha256').read_text(encoding='ascii').strip().split()
    if len(record) not in (1, 2) or not re.fullmatch(r'[0-9a-f]{64}', record[0]):
        raise ValueError('Malformed corrected PE digest record')
    if record[0] != QUALIFIED_WINDOWS_PE_SHA256:
        raise ValueError('PE digest is not the independently qualified corrected Windows build')
    if sha256(artifact / 'webots-bin.exe') != QUALIFIED_WINDOWS_PE_SHA256:
        raise ValueError('Corrected PE artifact bytes differ from qualified Windows build')
    if sha256(installed) != QUALIFIED_WINDOWS_PE_SHA256:
        raise ValueError('Installed Webots PE bytes differ from qualified Windows build')
    return QUALIFIED_WINDOWS_PE_SHA256


def verify_package(root):
    entries = {}
    for line in (root / 'MANIFEST.sha256').read_text(encoding='utf-8-sig').splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  (.+)', line)
        if not match:
            raise ValueError('Malformed classroom manifest')
        digest, name = match.groups()
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or name.casefold() in entries:
            raise ValueError('Escaping or duplicate manifest entry')
        if sha256(path) != digest:
            raise ValueError(f'Wrong classroom bytes: {name}')
        entries[name.casefold()] = digest
    actual = {p.relative_to(root).as_posix().casefold() for p in root.rglob('*') if p.is_file()}
    listed = {name.replace('\\', '/') for name in entries}
    if actual != listed | {'manifest.sha256'}:
        raise ValueError('Classroom manifest inventory differs from extracted files')
    world = root / 'worlds/crazyflie_runtime_v2.wbt'
    if 'DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {' not in world.read_text(encoding='utf-8-sig'):
        raise ValueError('The untouched classroom neutral world is required')
    return {'files': len(entries), 'manifest_sha256': sha256(root / 'MANIFEST.sha256')}


def engine_environment(home, ambient):
    env = {k.upper(): v for k, v in ambient.items()}
    for key in list(env):
        if key.startswith(('QT_', 'QML', 'PYTHON', 'WEBOTS', 'WEBEEBLOCKS', 'QT665')):
            del env[key]
    system = Path(env['SYSTEMROOT'])
    env['PATH'] = os.pathsep.join(str(p) for p in (
        home / 'msys64/mingw64/bin', home / 'msys64/mingw64/bin/cpp',
        home / 'msys64/usr/bin', system / 'System32', system))
    env['WEBOTS_HOME'] = str(home)
    env['WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE'] = 'true'
    return env


def attest_modules(mapped_paths, required, sdk):
    """Check exact mapped paths and bytes; a DLL basename alone proves nothing."""
    paths = {Path(p).resolve() for p in mapped_paths}
    sdk_root = sdk.parent.parent.resolve()
    if any(p.is_relative_to(sdk_root) for p in paths):
        raise ValueError('A native process depends on the external SDK')
    result = {}
    for name, (expected, digest) in required.items():
        matches = [p for p in paths if p.name.casefold() == name.casefold()]
        if not matches:
            raise LookupError(f'Module not observed: {name}')
        if len(matches) != 1 or matches[0] != expected.resolve():
            raise ValueError(f'Wrong mapped path for {name}: {matches}')
        if sha256(matches[0]) != digest:
            raise ValueError(f'Wrong mapped bytes for {name}')
        result[name] = {'path': str(matches[0]), 'sha256': digest}
    return result


def process_role(name, command_line):
    if name == 'webots-bin.exe':
        return name
    if name == 'crazyflie_runtime_v2.exe':
        if len(command_line) == 1:
            return 'runtime'
        if len(command_line) == 2 and command_line[1] == 'sequence-evaluator-v1':
            return 'sequence-evaluator'
        raise ValueError('Unexpected classroom controller arguments')
    return None


def run(args):
    import psutil  # Host observer only. Never added to the product environment.
    if sys.platform != 'win32':
        raise RuntimeError('This probe requires genuine Windows process observations')
    home, package, artifact, sdk = (p.resolve(strict=True) for p in (
        args.home, args.package, args.pe_artifact, args.sdk))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {'claim': 'unchanged-canonical-classroom-runtime-startup-on-disposable-patched-Windows',
              'classroom_source_sha': '1899293f458f6497dd1c0c024231173bb84f44fe',
              'classroom_run': 40386450869, 'classroom_artifact': 12681442366,
              'status': 'FAIL', 'processes': {}}
    process = None
    observed = {}
    threads = []
    capture_errors = []
    try:
        report['package'] = verify_package(package)
        bin_dir = home / 'msys64/mingw64/bin'
        pe_hash = attest_qualified_pe(artifact, bin_dir / 'webots-bin.exe')
        shared = {}
        for name in ('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'libstdc++-6.dll',
                     'libgcc_s_seh-1.dll', 'libwinpthread-1.dll'):
            shared[name] = (bin_dir / name, sha256(sdk / name))
        qwindows = home / 'msys64/mingw64/share/qt6/plugins/platforms/qwindows.dll'
        plugin_source = sdk.parent / 'share/qt6/plugins/platforms/qwindows.dll'
        engine_required = dict(shared, **{'webots-bin.exe': (bin_dir / 'webots-bin.exe', pe_hash),
            'qwindows.dll': (qwindows, sha256(plugin_source)),
            'libopenal-1.dll': (bin_dir / 'libopenal-1.dll', sha256(sdk / 'libopenal-1.dll'))})
        controller = package / 'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.exe'
        controller_required = dict(shared)
        controller_required.update({'crazyflie_runtime_v2.exe': (controller, sha256(controller)),
                                   'Controller.dll': (home / 'lib/controller/Controller.dll',
                                                      sha256(home / 'lib/controller/Controller.dll'))})
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = engine_environment(home, os.environ)
        command = [str(bin_dir / 'webots.exe'), '--stdout', '--stderr', '--batch',
                   '--mode=fast', f'--port={port}', str(package / 'worlds/crazyflie_runtime_v2.wbt')]
        report.update(command=command, path=env['PATH'], sdk_excluded=str(sdk.parent.parent))

        def drain(stream, filename):
            try:
                with stream, (output / filename).open('wb') as target:
                    while chunk := stream.read1(65536):
                        target.write(chunk)
                        target.flush()
            except Exception as exc:
                capture_errors.append(str(exc))

        process = subprocess.Popen(command, cwd=package, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        root = psutil.Process(process.pid)
        root_time = root.create_time()
        report['launcher'] = {'pid': root.pid, 'create_time': root_time, 'exe': root.exe()}
        for stream, filename in ((process.stdout, 'stdout.log'), (process.stderr, 'stderr.log')):
            thread = threading.Thread(target=drain, args=(stream, filename), daemon=True)
            thread.start()
            threads.append(thread)
        deadline = time.monotonic() + 45
        stable_since = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Webots launcher exited: {process.returncode:#x}')
            if root.create_time() != root_time:
                raise RuntimeError('Launcher process identity changed')
            for child in root.children(recursive=True):
                try:
                    identity = (child.pid, child.create_time())
                    observed[identity] = child
                    name = child.name().casefold()
                    if name not in ('webots-bin.exe', 'crazyflie_runtime_v2.exe'):
                        continue
                    command_line = child.cmdline()
                    role = process_role(name, command_line)
                    expected = engine_required if name == 'webots-bin.exe' else controller_required
                    expected_exe = bin_dir / name if name == 'webots-bin.exe' else controller
                    if Path(child.exe()).resolve() != expected_exe.resolve():
                        raise ValueError('Wrong native executable path')
                    modules = attest_modules([m.path for m in child.memory_maps()], expected, sdk)
                    graphics = {m.path: sha256(Path(m.path)) for m in child.memory_maps()
                                if Path(m.path).name.casefold() in ('opengl32.dll', 'opengl32sw.dll', 'libglapi.dll')}
                    report['processes'][role] = {'pid': child.pid, 'create_time': identity[1],
                        'ppid': child.ppid(), 'exe': child.exe(), 'modules': modules,
                        'graphics_modules': graphics, 'command_line': command_line}
                except (psutil.NoSuchProcess, psutil.AccessDenied, LookupError):
                    # Incomplete startup snapshot is not evidence; never accept it.
                    continue
            logs = '\n'.join((output / f).read_text(errors='replace') if (output / f).is_file() else ''
                             for f in ('stdout.log', 'stderr.log'))
            report['ready_observed'] = bool(re.search(r'WEBEEBLOCKS_RUNTIME_V2 READY(?:\s|$)', logs))
            ready = report['ready_observed'] and set(report['processes']) == {'webots-bin.exe', 'runtime', 'sequence-evaluator'}
            if ready:
                engine = report['processes']['webots-bin.exe']
                if (engine['ppid'] != process.pid or
                        any(report['processes'][role]['ppid'] != engine['pid'] for role in ('runtime', 'sequence-evaluator'))):
                    raise RuntimeError('Unexpected launcher/engine/controller ancestry')
                for row in report['processes'].values():
                    live = psutil.Process(row['pid'])
                    if live.create_time() != row['create_time'] or not live.is_running():
                        raise RuntimeError('A qualified process exited or was replaced')
                stable_since = stable_since or time.monotonic()
                if time.monotonic() - stable_since >= 2:
                    if re.search(r'^ERROR:|Traceback \(most recent call last\)', logs, re.MULTILINE):
                        raise RuntimeError('Native startup logged an error')
                    report['status'] = 'PASS_BOUNDED_STARTUP_ONLY'
                    return
            else:
                stable_since = None
            time.sleep(.15)
        raise RuntimeError('Native classroom READY and complete loaded-module identity not established within 45 s')
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        cleanup_errors = []
        if process is not None:
            # Only the launched tree/observed same-identity descendants; no name-wide kill.
            try:
                root = psutil.Process(process.pid)
                for child in root.children(recursive=True):
                    observed[(child.pid, child.create_time())] = child
            except psutil.NoSuchProcess:
                pass
            for identity, child in reversed(list(observed.items())):
                try:
                    if child.create_time() == identity[1]:
                        child.kill()
                        child.wait(timeout=10)
                except psutil.NoSuchProcess:
                    pass
                except Exception as exc:
                    cleanup_errors.append(str(exc))
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            for thread in threads:
                thread.join(timeout=10)
            if any(t.is_alive() for t in threads):
                cleanup_errors.append('Output pipes did not close')
        report['capture_errors'] = capture_errors
        report['cleanup_errors'] = cleanup_errors
        if capture_errors or cleanup_errors:
            report['status'] = 'FAIL'
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        if capture_errors or cleanup_errors:
            raise RuntimeError('Capture or cleanup incomplete')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('home', 'package', 'pe-artifact', 'sdk', 'output'):
        parser.add_argument('--' + flag, required=True, type=Path)
    run(parser.parse_args())
    print('QT665_WINDOWS_PACKAGED_RUNTIME_STARTUP=PASS_BOUNDED_ONLY')
