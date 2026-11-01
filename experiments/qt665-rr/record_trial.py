#!/usr/bin/env python3
"""Prepared-host, one-shot native capture. UNQUALIFIED until exercised on a PMU host.

Trace and evidence stay private; this program never uploads them.
The existing native trial owns its deadlines, oracles, SIGTERM and cleanup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
ELF_SHA = '1445efb2820d151dee40b79ef4128dca7e4a75e02630b49354e557c7e35e66eb'
QT = {
    'libQt6Core.so.6': 'ac391204135f1435ca1c97a7f92e6f94d9d369f6b12fb823923496360a272bd8',
    'libQt6Gui.so.6': 'f8396f49e2bcfb3e667ba17bd861f1f0be806153141cc3966e79f726818e24e9',
    'libQt6Widgets.so.6': '868b516dde6d020badc7243facd48f880b0d606c76e46e50427c1c744a2c1024',
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def logged(argv, prefix, *, env=None):
    with prefix.with_suffix('.stdout').open('wb') as out, prefix.with_suffix('.stderr').open('wb') as err:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=out, stderr=err)
    return {'argv': argv, 'returncode': result.returncode}


def observe_native(rr_pid, executable, subjects, digests):
    """Read identities only; no signal, attach, LD_PRELOAD or process mutation."""
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if not (proc / 'exe').samefile(executable):
                continue
            # Exclude any unrelated Webots instance running on the same host.
            ancestor = int(proc.name)
            for _ in range(64):
                status = Path(f'/proc/{ancestor}/status').read_text()
                parent = next(int(s.split()[1]) for s in status.splitlines() if s.startswith('PPid:'))
                if parent == rr_pid:
                    break
                if parent <= 1:
                    raise ValueError('not a recorded descendant')
                ancestor = parent
            else:
                continue
            maps = (proc / 'maps').read_text()
            if proc.name not in subjects:
                subjects[proc.name] = {'exe_sha256': sha(proc / 'exe'), 'snapshots': [], 'mapped_files': {}}
            subject = subjects[proc.name]
            snapshot = []
            for line in maps.splitlines():
                parts = line.split(maxsplit=5)
                if len(parts) != 6 or not parts[5].startswith('/'):
                    continue
                address, perms, offset, device, inode, name = parts
                path = Path(name)
                try:
                    stat = path.stat()
                    major, minor = [int(x, 16) for x in device.split(':')]
                    if (stat.st_ino, os.major(stat.st_dev), os.minor(stat.st_dev)) != (int(inode), major, minor):
                        raise ValueError('mapped inode no longer matches disk')
                    key = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
                    if key not in digests:
                        digests[key] = sha(path)
                    subject['mapped_files'][name] = {'sha256': digests[key], 'inode': int(inode), 'device': device}
                except (OSError, ValueError) as error:
                    subject['mapped_files'][name] = {'unproven': str(error)}
                snapshot.append(line)
            # Keep distinct library-map states, not megabytes of duplicate maps.
            if not subject['snapshots'] or subject['snapshots'][-1] != snapshot:
                subject['snapshots'].append(snapshot)
        except (OSError, ValueError, StopIteration):
            continue


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True, help='new private directory OUTSIDE the checkout')
    p.add_argument('--webots-home', type=Path, required=True)
    p.add_argument('--host-report', type=Path, required=True)
    a = p.parse_args()
    home = a.webots_home.resolve()
    out = a.out.resolve()
    if out == ROOT or ROOT in out.parents:
        p.error('--out must be outside the checkout')
    gate = json.loads(a.host_report.read_text())
    if gate['status'] != 'RR_SMOKE_RECORD_REPLAY_VALID':
        p.error('actual host record/replay gate has not passed')
    if gate['uname'] != list(platform.uname()):
        p.error('successful host gate belongs to another host/kernel')
    rr = shutil.which('rr')
    if not rr or sha(rr) != gate.get('rr_sha256'):
        p.error('rr identity differs from the successful host gate')
    native = home / 'bin/webots-bin'
    if sha(native) != ELF_SHA or (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        p.error('wrong original Webots ELF/version')
    for name, digest in QT.items():
        if sha(home / 'lib/webots' / name) != digest:
            p.error('wrong original Qt: ' + name)
    for executable in ('node', 'Xvfb', 'xvfb-run', 'make'):
        if not shutil.which(executable):
            p.error('prepared host missing ' + executable)
    node_major = int(subprocess.check_output(['node', '-p', 'Number(process.versions.node.split(".")[0])'], text=True))
    if node_major < 22:
        p.error('Node >=22 required')
    artifacts = ROOT / 'ci-artifacts/grand-prix-u'
    if artifacts.exists():
        p.error('use a fresh isolated checkout: native evidence directory already exists')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True):
        p.error('checkout must be clean; commit experimental code before capture')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    shutil.copyfile(a.host_report, out / 'host.json')
    env = os.environ.copy()
    env.update(WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true',
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    command = [rr, 'record', '-o', str(out / 'trace'), sys.executable, '-u',
               str(ROOT / 'tools/ci/run_grand_prix_u_prototype.py'),
               '--native', '--suite', 'unavailable', '--seed', '0', '--side', '2.0']
    report = {'status': 'UNQUALIFIED_CAPTURE', 'scenario': 'gp-u-v1-L2000-s0-unavailable',
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'webots_sha256': sha(native), 'rr_sha256': sha(rr),
              'python_sha256': sha(sys.executable), 'node_sha256': sha(shutil.which('node')),
              'argv': command, 'loaded_webots': {}}
    save(out / 'capture.json', report)
    digests = {}
    with (out / 'record.stdout').open('wb') as stdout, (out / 'record.stderr').open('wb') as stderr:
        recording = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        while recording.poll() is None:
            observe_native(recording.pid, native, report['loaded_webots'], digests)
            time.sleep(.05)
        report['record_returncode'] = recording.returncode
    # Keep failure evidence and traces even when the unchanged harness rejects a
    # real crash, readiness deadline or incomplete teardown. Never retry it.
    if artifacts.exists():
        shutil.copytree(artifacts, out / 'native-artifacts')
    trace = out / 'trace'
    if trace.exists() and not (trace / 'incomplete').exists():
        report['pack'] = logged([rr, 'pack', str(trace)], out / 'pack')
        report['replay'] = logged([rr, 'replay', '-a', str(trace)], out / 'replay')
        report['dump_tasks'] = logged([rr, 'dump', '-e', str(trace)], out / 'tasks')
        report['dump_maps'] = logged([rr, 'dump', '-p', str(trace)], out / 'maps')
        report['stdio_equal'] = (out / 'record.stdout').read_bytes() == (out / 'replay.stdout').read_bytes()
        # Never grant scientific RR_RECORDING_VALID automatically: the replay
        # may reproduce a failed setup or a valid trace of the wrong subject.
        if report['replay']['returncode'] == 0 and report['stdio_equal']:
            report['status'] = 'REPLAY_COMPLETED_STDOUT_MATCH_REQUIRES_NATIVE_REVIEW'
    else:
        report['status'] = 'RR_TRACE_MISSING_OR_INCOMPLETE'
    report['next_review'] = 'verify native PID/Qt maps, READY, events, SIGTERM/crash; not a root-cause verdict'
    save(out / 'capture.json', report)
    save(out / 'SHA256.json', {str(f.relative_to(out)): sha(f) for f in out.rglob('*')
                             if f.is_file() and f != out / 'SHA256.json'})
    print(json.dumps({'out': str(out), 'status': report['status']}, indent=2))


if __name__ == '__main__':
    main()
