#!/usr/bin/env python3
"""Private kernel cores for the unchanged CI campaign; post-mortem text only.

The host kernel setting is changed only on an explicitly disposable GitHub
runner, restored before post-mortem analysis, and never changed by the product.
No debugger is attached to a running Webots process. No raw core is uploaded.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.ci.run_grand_prix_u_geometry import IMAGE

CORE_LIMIT = 1024 * 1024 * 1024
TEXT_LIMIT = 65536
LIBRARY_ROOTS = (Path('/lib/x86_64-linux-gnu'), Path('/usr/lib/x86_64-linux-gnu'),
                 Path('/usr/local/webots/lib/webots'))
PATTERN_FILE = Path('/proc/sys/kernel/core_pattern')
OUT = ROOT / 'ci-artifacts/grand-prix-u'


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def core_mount(directory):
    """Additional Docker arguments only for the explicit host capture context."""
    if not directory:
        return []
    path = Path(directory)
    if (not path.is_absolute() or path != path.resolve() or
            path.parent != Path('/tmp') or
            not re.fullmatch(r'gp-u-core-[a-z0-9_]+', path.name) or
            path.stat().st_mode & 0o777 != 0o700):
        raise ValueError('invalid private core directory')
    return ['--ulimit', 'core=%d' % CORE_LIMIT, '-v', f'{path}:{path}']


def set_pattern(value):
    subprocess.run(['sudo', '-n', 'sysctl', '-q', '-w',
                    'kernel.core_pattern=' + value], check=True, timeout=10)


@contextmanager
def kernel_capture(directory, record):
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        raise RuntimeError('core routing requires a disposable GitHub-hosted runner')
    core_mount(str(directory))
    original = PATTERN_FILE.read_text().strip()
    selected = str(directory / 'core.%e.%p.%t')
    record.update(original_core_pattern=original, capture_core_pattern=selected,
                  core_limit_bytes=CORE_LIMIT, restored=False)
    # Establish cleanup before attempting a write: a transport failure may still
    # have changed the setting. Never blindly overwrite an unexpected value.
    try:
        set_pattern(selected)
        if PATTERN_FILE.read_text().strip() != selected:
            raise RuntimeError('core routing not established')
        yield
    finally:
        observed = PATTERN_FILE.read_text().strip()
        if observed == selected:
            set_pattern(original)
        elif observed != original:
            raise RuntimeError('core routing changed externally; restoration unproven')
        record['restored'] = PATTERN_FILE.read_text().strip() == original
        if not record['restored']:
            raise RuntimeError('original core routing not restored')


def cores(directory, executable):
    found = []
    pattern = re.compile(r'core\.' + re.escape(executable) + r'\.\d+\.\d+')
    for path in directory.iterdir():
        if pattern.fullmatch(path.name) and path.is_file() and not path.is_symlink():
            if not 0 < path.stat().st_size <= CORE_LIMIT:
                raise RuntimeError('empty or oversized core')
            found.append(path)
    return sorted(found)


def package_versions():
    result = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n'],
                            check=True, capture_output=True, text=True, timeout=10)
    return dict(line.split('\t', 1) for line in result.stdout.splitlines())


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def snapshot_inputs(binary, root):
    """Copy original ELF libraries before apt; never retain escaping symlinks."""
    files = {binary}
    loader = Path('/lib64/ld-linux-x86-64.so.2')
    if loader.is_file():
        files.add(loader)
    for directory in LIBRARY_ROOTS:
        # rglob does not recurse into directory symlinks. File symlinks are
        # dereferenced while copying, so an absolute target cannot escape the
        # debugger's sysroot later and silently select an upgraded library.
        for path in directory.rglob('*'):
            if '.so' in path.name and path.is_file():
                with path.open('rb') as stream:
                    if stream.read(4) == b'\x7fELF':
                        files.add(path)
    manifest = {}
    for source in sorted(files):
        relative = source.relative_to('/')
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        checksum = hashlib.sha256()
        with source.open('rb') as original, target.open('xb') as copy:
            for block in iter(lambda: original.read(1024 * 1024), b''):
                copy.write(block)
                checksum.update(block)
        manifest[str(relative)] = checksum.hexdigest()
    return manifest


def verify_snapshot(root, manifest):
    for relative, checksum in manifest.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or digest(path) != checksum:
            raise RuntimeError('original debugger sysroot changed: ' + relative)


def container_backtrace(core, binary, output):
    """Runs in a NEW disposable copy of IMAGE, only after the subject exited.

    GDB dependencies may differ from the subject, but every subject ELF input
    is copied and hashed BEFORE apt, then verified and selected by --sysroot.
    The subject container, native binary and its original launch are untouched.
    """
    versions = package_versions()
    binary_hash = digest(binary)
    result = dict(image=IMAGE, binary_sha256=binary_hash, raw_core_uploaded=False,
                  status='UNPROVEN', core_bytes=core.stat().st_size)
    with tempfile.TemporaryDirectory(prefix='gp-u-sysroot-') as temporary:
        try:
            sysroot = Path(temporary)
            manifest = snapshot_inputs(binary, sysroot)
            result['sysroot_manifest_sha256'] = hashlib.sha256(
                json.dumps(manifest, sort_keys=True).encode()).hexdigest()
            result['sysroot_files'] = len(manifest)
            write_json(output.with_suffix('.sysroot.json'),
                       dict(image=IMAGE, sha256=manifest,
                            claim='original ELF inputs before debugger preparation'))
            with tempfile.TemporaryFile() as preparation:
                for command in (['apt-get', 'update'],
                                ['apt-get', 'install', '-y', '--no-install-recommends',
                                 '--no-remove', 'gdb']):
                    subprocess.run(command, stdout=preparation, stderr=subprocess.STDOUT,
                                   check=True, timeout=90,
                                   env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})
            after = package_versions()
            changed = sorted(name for name, version in versions.items()
                             if after.get(name) != version)
            result['debugger_changed_packages'] = changed
            verify_snapshot(sysroot, manifest)
            result['original_sysroot_verified'] = True
            # Only frame names/addresses and loaded-library provenance: never locals,
            # arguments, environment, arbitrary memory, raw cores or auto-loaded code.
            command = ['gdb', '-q', '-nx', '-batch',
                       '-iex', 'set auto-load off',
                       '-iex', 'set debuginfod enabled off',
                       '-iex', 'set sysroot ' + str(sysroot),
                       '-iex', 'set debug-file-directory ' + str(sysroot / 'usr/lib/debug'),
                       '-ex', 'set print frame-arguments none',
                       '-ex', 'set print entry-values no',
                       '-ex', 'thread apply all bt 24',
                       '-ex', 'info sharedlibrary', str(sysroot / binary.relative_to('/')), str(core)]
            with tempfile.TemporaryFile() as text:
                proc = subprocess.run(command, stdout=text, stderr=subprocess.STDOUT,
                                      timeout=15, check=False)
                text.seek(0)
                payload = text.read(TEXT_LIMIT + 1)
            output.with_suffix('.txt').write_bytes(payload[:TEXT_LIMIT])
            incomplete = any(marker in payload for marker in (
                b'core file may not match', b'is truncated',
                b'Could not load shared library symbols', b'Cannot access memory'))
            result.update(gdb_returncode=proc.returncode,
                          text_truncated=len(payload) > TEXT_LIMIT,
                          stack_incomplete=incomplete,
                          status='CAPTURED' if proc.returncode == 0 and
                          b'#0 ' in payload and not incomplete else 'UNPROVEN')
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            result['reason'] = type(error).__name__ + ': ' + str(error)[:500]
    write_json(output.with_suffix('.json'), result)
    return 0 if result['status'] == 'CAPTURED' else 1


def analyse(core, binary, label):
    output = OUT / label
    cid = core.parent / (label + '.cid')
    command = ['docker', 'run', '--rm', '--cidfile', str(cid),
               '-v', f'{ROOT}:/workspace:ro',
               '-v', f'{OUT}:{OUT}', '-v', f'{core.parent}:{core.parent}:ro',
               '--entrypoint', 'python3', IMAGE,
               '/workspace/tools/ci/run_grand_prix_u_core_capture.py',
               '--container-backtrace', str(core), str(binary), str(output)]
    try:
        result = subprocess.run(command, timeout=220, check=False)
        return result.returncode
    finally:
        retire_container(cid)


def retire_container(cid):
    """Only retire the container whose creation returned this exact identity."""
    if not cid.exists():
        return
    identity = cid.read_text().strip()
    if not re.fullmatch('[0-9a-f]{64}', identity):
        raise RuntimeError('invalid capture container identity')
    state = subprocess.run(['docker', 'inspect', '--format', '{{.State.Running}}', identity],
                           capture_output=True, text=True, timeout=10, check=False)
    if state.returncode == 0:
        if state.stdout.strip() == 'true':
            subprocess.run(['docker', 'stop', '--time', '5', identity],
                           stdout=subprocess.DEVNULL, check=True, timeout=20)
        elif state.stdout.strip() != 'false':
            raise RuntimeError('capture container state unknown')
    elif 'No such object' not in state.stderr and 'No such container' not in state.stderr:
        raise RuntimeError('capture container retirement unproven')


def preflight(directory):
    # An intentional tiny crash qualifies kernel routing and post-mortem tools;
    # it is not a Webots retry, a student attempt, or a mission success oracle.
    source = directory / 'probe.c'
    binary = directory / 'gp-core-probe'
    source.write_text('void wbb_expected_crash(void) { *(volatile int *)0 = 1; }\n'
                      'int main(void) { wbb_expected_crash(); return 0; }\n')
    subprocess.run(['cc', '-g', '-O0', str(source), '-o', str(binary)],
                   check=True, timeout=15)
    cid = directory / 'preflight.cid'
    try:
        result = subprocess.run(['docker', 'run', '--rm', '--cidfile', str(cid),
                                 *core_mount(str(directory)),
                                 '--entrypoint', str(binary), IMAGE],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30, check=False)
    finally:
        retire_container(cid)
    found = cores(directory, 'gp-core-probe')
    if result.returncode != 139 or len(found) != 1:
        raise RuntimeError('intentional SIGSEGV did not produce exactly one private core')
    return found[0], binary


def attribute(core):
    """Do not call a post-READY fault a reproduction of startup SIGSEGV."""
    pid = int(core.name.split('.')[2])
    matches = []
    for path in OUT.glob('*/startup-failure.json'):
        data = json.loads(path.read_text())
        if pid in data.get('core', {}).get('native_sigsegv_pids_in_log', []):
            matches.append(dict(trial=path.parent.name, phase='BEFORE_READY',
                                sequence_index=data['sequence_index']))
    if not matches:
        for path in OUT.glob('*/startup-ready.json'):
            data = json.loads(path.read_text())
            if any(p['pid'] == pid and p['comm'] == 'webots-bin'
                   for sample in data['process_samples'] for p in sample['processes']):
                matches.append(dict(trial=path.parent.name, phase='AFTER_READY',
                                    sequence_index=data['sequence_index']))
    return matches[0] if len(matches) == 1 else dict(phase='UNPROVEN', matches=len(matches))


def host_main():
    OUT.mkdir(parents=True, exist_ok=True)
    record = dict(schema=1, status='UNPROVEN', raw_core_uploaded=False,
                  subject_returncode=None)
    old_handlers = {}
    def interrupted(signum, frame):
        raise InterruptedError('capture interrupted by signal %d' % signum)
    for sig in (signal.SIGTERM, signal.SIGINT):
        old_handlers[sig] = signal.signal(sig, interrupted)
    try:
        with tempfile.TemporaryDirectory(prefix='gp-u-core-', dir='/tmp') as tmp:
            directory = Path(tmp)
            subprocess.run(['docker', 'pull', IMAGE], check=True, timeout=180)
            # The preflight uses the same private core route but a separate
            # container; restore the host before apt/GDB post-mortem work.
            with kernel_capture(directory, record):
                core, binary = preflight(directory)
            if analyse(core, binary, 'core-capture-preflight') != 0:
                raise RuntimeError('core-capture preflight stack unavailable')
            if 'wbb_expected_crash' not in (OUT / 'core-capture-preflight.txt').read_text():
                raise RuntimeError('preflight stack did not identify known crash site')
            core.unlink()
            cid = directory / 'subject.cid'
            with kernel_capture(directory, record):
                try:
                    run = subprocess.run([sys.executable,
                                          str(ROOT / 'tools/ci/run_grand_prix_u_prototype.py')],
                                         env={**os.environ,
                                              'WEBEEBLOCKS_GP_CORE_DIR': str(directory),
                                              'WEBEEBLOCKS_GP_CONTAINER_CIDFILE': str(cid)},
                                         check=False)
                    record['subject_returncode'] = run.returncode
                finally:
                    retire_container(cid)
            # All kernel routing is restored before installing debugger packages.
            found = cores(directory, 'webots-bin')
            if len(found) > 1:
                raise RuntimeError('multiple native cores; exact attribution unproven')
            if found:
                record['core_attribution'] = attribute(found[0])
                record['backtrace_returncode'] = analyse(
                    found[0], Path('/usr/local/webots/bin/webots-bin'),
                    'startup-host-backtrace')
            record.update(status='COMPLETE', native_core_count=len(found))
            # The unchanged campaign's failure is preserved even if GDB succeeds.
            return run.returncode
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        record['reason'] = type(error).__name__ + ': ' + str(error)[:500]
        return record['subject_returncode'] or 1
    finally:
        write_json(OUT / 'core-capture-host.json', record)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--container-backtrace', nargs=3, type=Path)
    args = parser.parse_args()
    raise SystemExit(container_backtrace(*args.container_backtrace)
                     if args.container_backtrace else host_main())
