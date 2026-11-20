"""Run the extracted Windows U assembly in real Webots, without a GUI claim.

This is test tooling, not a pupil launcher. No package byte, world, controller,
oracle or timeout is changed. Retain native traces and the exact ordinary AST.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.layout_u import generate
from tools.ci.test_grand_prix_windows_project import verify


def read(path):
    return path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''


def validate(directory, seed):
    rows = [json.loads(line) for line in read(directory / 'events.jsonl').splitlines()]
    if any(row['event'] in ('error', 'wall-timeout', 'transport-error') for row in rows):
        raise ValueError('Installed witness reported an execution/transport failure')
    programs = [row['detail'] for row in rows if row['event'] == 'program']
    outcomes = [row['detail'] for row in rows if row['event'] == 'outcome']
    if len(programs) != 1 or len(outcomes) != 1 or outcomes[0].get('status') != 'achieved':
        raise ValueError('Exactly one program and successful shared-backend outcome required')
    text = read(directory / 'webots.stdout.log') + '\n' + read(directory / 'webots.stderr.log')
    if any(line.startswith('ERROR:') for line in text.splitlines()) or 'Traceback (most recent call last)' in text:
        raise ValueError('Native Webots/controller error')
    records = [json.loads(line.split('GP_U_RESULT ', 1)[1]) for line in text.splitlines()
               if line.startswith('GP_U_RESULT ')]
    result = json.loads((directory / 'native-result-1.json').read_text(encoding='utf-8'))
    layout = generate(seed)
    if (len(records) != 1 or records[0] != result or result['status'] != 'achieved' or
            result['configuration'] != layout.identifier or result['attempt'] != 1 or
            result['crossings'] != len(layout.gates) or
            not isinstance(result['seconds'], (int, float)) or isinstance(result['seconds'], bool) or
            not math.isfinite(result['seconds']) or not 0 < result['seconds'] < 210):
        raise ValueError('Missing, inconsistent or failed exact native outcome')
    # The unchanged world oracle checks route, altitude, crossings and pose. Keep
    # its actual trace/diagnostic too, rather than treating a Node exit as PASS.
    diagnostic = json.loads((directory / 'native-diagnostic-1.json').read_text(encoding='utf-8'))
    if diagnostic['crossings'] != len(layout.gates) or diagnostic['landing_target'] != list(layout.landing_target(len(layout.gates))):
        raise ValueError('Wrong native crossing/landing subject')
    trace = directory / 'native_trace.csv'
    if not trace.is_file() or trace.stat().st_size < 100:
        raise ValueError('Native trajectory evidence missing')
    result['ast_sha256'] = hashlib.sha256(json.dumps(programs[0], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result


def _filter_windows_tree(rows, root_pid, watched=()):
    """Bounded process-identity evidence; NEVER a successful-cleanup oracle."""
    if (not isinstance(rows, list) or len(rows) > 4096 or len(watched) > 64 or
            type(root_pid) is not int or root_pid <= 0 or
            any(type(pid) is not int or pid <= 0 for pid in watched)):
        raise ValueError('Windows process snapshot is malformed or too large')
    by_pid = {}
    system_idle_excluded = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Malformed process row')
        pid, parent = row.get('ProcessId'), row.get('ParentProcessId')
        # Win32_Process includes the reserved System Idle Process (PID 0).
        # It can never belong to a launched positive-PID tree. Its parent is
        # commonly 0 or null; reject any purported positive parent instead.
        # Only this well-defined system row may be omitted. A malformed
        # positive-PID row remains UNAVAILABLE, never evidence of cleanup.
        if type(pid) is int and pid == 0:
            if parent is not None and (type(parent) is not int or parent != 0):
                raise ValueError('Malformed System Idle Process parent')
            system_idle_excluded += 1
            if system_idle_excluded > 1:
                raise ValueError('Duplicate System Idle Process rows')
            continue
        if type(pid) is not int or type(parent) is not int or pid <= 0 or parent < 0:
            raise ValueError('Malformed process identifiers')
        created = row.get('CreationDate')
        if created is not None and not isinstance(created, str):
            raise ValueError('Malformed process creation identity')
        by_pid[pid] = dict(pid=pid, parent=parent, created=created,
                           name=str(row.get('Name', ''))[:128])
    owned = {root_pid}
    for _ in range(65):
        new = owned | {r['pid'] for r in by_pid.values() if r['parent'] in owned}
        if len(new) > 64:
            raise ValueError('Windows process tree exceeds diagnostic bound')
        if new == owned:
            break
        owned = new
    else:
        raise ValueError('Windows process tree did not converge')
    return dict(available=True, root_present=root_pid in by_pid,
                excluded_system_idle_rows=system_idle_excluded,
                owned=[by_pid[pid] for pid in sorted(owned) if pid in by_pid],
                watched=[by_pid[pid] for pid in sorted(set(watched))
                         if pid in by_pid])


def _windows_process_snapshot(root_pid, watched=()):
    """Observe process parent PID and creation identity via native Windows CIM.

    A Toolhelp/CIM snapshot can race child creation and is NOT proof of total
    extinction. Preserve both snapshots; never use them to excuse taskkill.
    """
    if sys.platform != 'win32':
        return {'available': False, 'error': 'Windows-only observation'}
    try:
        command = ("$ErrorActionPreference='Stop'; "
                   "Get-CimInstance Win32_Process | "
                   "Select-Object ProcessId,ParentProcessId,CreationDate,Name | "
                   "ConvertTo-Json -Compress -Depth 3")
        result = subprocess.run(
            ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
             '-Command', command], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True, timeout=15)
        if len(result.stdout) > 512000:
            raise ValueError('Process inventory exceeds diagnostic byte bound')
        rows = json.loads(result.stdout.decode('utf-8-sig', errors='replace'))
        if isinstance(rows, dict):
            rows = [rows]
        return _filter_windows_tree(rows, root_pid, watched)
    except (OSError, subprocess.SubprocessError, ValueError, UnicodeError) as error:
        return {'available': False,
                'error': (type(error).__name__ + ': ' + str(error))[:512]}


def stop(process, diagnostic_path=None):
    if process is None:
        return
    status = process.poll()
    if status is not None:
        if status != 0:
            raise RuntimeError(
                f'Owned Windows PID {process.pid} exited unexpectedly: '
                f'process={status!r}'
            )
        return
    # Diagnostic only. Unchanged decision: taskkill failure with nonzero exit
    # must still FAIL, regardless of textual SUCCESS or a vanishing PID.
    evidence = {'schema': 'webeeblocks-windows-owned-cleanup-v1',
                'root_pid': process.pid,
                'snapshot_limitations': 'Not an exhaustive process-lifetime monitor'}
    if diagnostic_path is not None:
        evidence['before'] = _windows_process_snapshot(process.pid)
    try:
        try:
            result = subprocess.run(
                ['taskkill', '/PID', str(process.pid), '/T', '/F'], check=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
            evidence['taskkill_returncode'] = result.returncode
            output = result.stdout or b''
        except subprocess.CalledProcessError as failure:
            evidence['taskkill_returncode'] = failure.returncode
            output = failure.output or b''
            evidence['taskkill_output'] = (
                output.decode('utf-8', errors='replace') if isinstance(output, bytes)
                else str(output))[:16384]
            evidence['taskkill_output_truncated'] = len(output) > 16384
            status = process.poll()
            if status is None:
                try:
                    status = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    status = None
            evidence['process_after_taskkill'] = status
            if status != 0:
                detail = output.decode('utf-8', errors='replace') if isinstance(
                    output, bytes) else str(output)
                raise RuntimeError(
                    f'Owned Windows PID {process.pid} cleanup unproven: '
                    f'taskkill={failure.returncode}, process={status!r}, '
                    f'output={detail[-512:]!r}'
                ) from failure
        if diagnostic_path is not None and 'taskkill_output' not in evidence:
            evidence['taskkill_output'] = (
                output.decode('utf-8', errors='replace') if isinstance(output, bytes)
                else str(output))[:16384]
            evidence['taskkill_output_truncated'] = len(output) > 16384
        evidence['wait_returncode'] = process.wait(timeout=20)
    except Exception as error:
        evidence['exception'] = (type(error).__name__ + ': ' + str(error))[:750]
        raise
    finally:
        if diagnostic_path is not None:
            before = evidence.get('before', {})
            watched = [x['pid'] for x in before.get('owned', [])]
            after = _windows_process_snapshot(process.pid, watched)
            evidence['after'] = after
            if before.get('available') and after.get('available'):
                old = {(p['pid'], p['created']) for p in before['owned']
                       if p['created'] is not None}
                evidence['still_present_same_pid_and_creation'] = [
                    p for p in after['watched']
                    if (p['pid'], p['created']) in old]
                evidence['identity_unproven'] = [
                    p['pid'] for p in before['owned'] if p['created'] is None]
            # Positive evidence of a surviving child is a veto. Missing
            # before/after CIM evidence or a missing creation identity is
            # independently inconclusive: do not report a safe retirement.
            # Neither two snapshots nor taskkill's SUCCESS text prove full
            # process-lifetime monitoring; keep that limitation explicit.
            survivors = evidence.get('still_present_same_pid_and_creation', [])
            gaps = []
            if not before.get('available'):
                gaps.append('before-snapshot-unavailable')
            else:
                # A syntactically valid CIM inventory can still omit the
                # process known live at the initial poll. Without its identity
                # we cannot attribute descendants or prove their retirement.
                # Fallback only supports older tests supplying owned rows.
                root_seen = before.get('root_present')
                if root_seen is None:
                    root_seen = any(p.get('pid') == process.pid
                                    for p in before.get('owned', []))
                if root_seen is not True:
                    gaps.append('before-root-identity-unavailable')
            if not after.get('available'):
                gaps.append('after-snapshot-unavailable')
            if evidence.get('identity_unproven'):
                gaps.append('creation-identity-unavailable')
            evidence['cleanup_observation_gaps'] = gaps
            no_prior_error = sys.exc_info()[0] is None
            survivor_veto = bool(survivors) and no_prior_error
            observation_veto = bool(gaps) and no_prior_error
            if survivor_veto:
                evidence['exception'] = (
                    'RuntimeError: observed same-identity owned descendants survived cleanup')
            elif observation_veto:
                evidence['exception'] = (
                    'RuntimeError: owned process cleanup observation unavailable')
            diagnostic_path.write_text(
                json.dumps(evidence, sort_keys=True, indent=2) + '\n',
                encoding='utf-8')
            if survivor_veto:
                raise RuntimeError(
                    f'Owned Windows PID {process.pid} cleanup unproven: '
                    f'{len(survivors)} same-identity descendants survived')
            if observation_veto:
                raise RuntimeError(
                    f'Owned Windows PID {process.pid} cleanup observation unavailable: '
                    + ', '.join(gaps))


def engine_environment(home, ambient):
    # os.environ is case-insensitive on Windows; its plain copied dict is not.
    env = {key.upper(): value for key, value in ambient.items()}
    if not env.get('SYSTEMROOT'):
        raise ValueError('Windows SYSTEMROOT is required for native DLL lookup')
    system = Path(env['SYSTEMROOT'])
    env['PATH'] = os.pathsep.join(str(p) for p in (
        home / 'msys64/mingw64/bin', home / 'msys64/mingw64/bin/cpp',
        home / 'msys64/usr/bin', system / 'System32', system))
    env['QT_ENABLE_HIGHDPI_SCALING'] = '1'
    env.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
    return env


@contextmanager
def captured_engine(command, cwd, env, stdout_path, stderr_path):
    # R2025a gui/main.cpp RedirectIOToConsole retains redirected handles only
    # for FILE_TYPE_PIPE. A disk handle makes it reopen CONOUT$, losing logs.
    # Drain both pipes concurrently, including while waiting for READY/results.
    errors = []
    def drain(source, target):
        try:
            with source:
                while chunk := source.read1(65536):
                    target.write(chunk)
                    target.flush()
        except Exception as error:
            errors.append(error)

    with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        threads = [threading.Thread(target=drain, args=(source, target), daemon=True)
                   for source, target in ((process.stdout, stdout), (process.stderr, stderr))]
        for thread in threads:
            thread.start()
        try:
            yield process
        finally:
            try:
                stop(process, diagnostic_path=stdout_path.parent / 'webots-process-cleanup.json')
            finally:
                for thread in threads:
                    thread.join(timeout=20)
                if any(thread.is_alive() for thread in threads):
                    raise RuntimeError('Native output pipes did not close after process cleanup')
                if errors:
                    raise RuntimeError('Native output capture failed') from errors[0]


def trial(package, home, output, seed):
    directory = output / f'seed-{seed}'
    directory.mkdir()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = engine_environment(home, os.environ)
    node_exe = shutil.which('node')
    # Reproduce R2025a launcher.c's DLL environment, then start its exact
    # engine directly so redirected handles and the exit code remain ours.
    # Bound PATH as in the other Windows native probes; no ambient Python/DLL
    # installation is a dependency of the extracted project.
    env.update(WEBOTS_HOME=str(home), WEBEEBLOCKS_GP_PYTHON_DIR=str(package / 'runtime/python'),
               WEBEEBLOCKS_CI_ARTIFACT_DIR=str(directory),
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    # Prove selection of the embedded interpreter, not ambient Python lookup.
    env['PYTHONHOME'] = str(directory / 'absent ambient Python')
    env['PYTHONPATH'] = env['PYTHONHOME']
    engine = str(home / 'msys64/mingw64/bin/webots-bin.exe')
    command = [engine, '--stdout', '--stderr', '--batch', '--mode=fast',
               '--no-rendering', f'--port={port}',
               str(package / f'worlds/grand_prix_u_seed{seed}.wbt')]
    metadata = dict(command=command, cwd=str(package), path=env['PATH'],
                    source_sha=(package / 'SOURCE_SHA').read_text().strip(),
                    node_executable=node_exe, webots_exit=None, node_exit=None,
                    mesa_gl_version=env.get('MESA_GL_VERSION_OVERRIDE'),
                    software_gl=env.get('LIBGL_ALWAYS_SOFTWARE'))
    webots = node = None
    try:
        try:
            diagnostic = subprocess.run([engine, '--sysinfo'], cwd=package,
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
            metadata['sysinfo_exit'] = diagnostic.returncode
            (directory / 'sysinfo.log').write_bytes(diagnostic.stdout)
        except subprocess.TimeoutExpired as error:
            metadata['sysinfo_timeout'] = True
            (directory / 'sysinfo.log').write_bytes(error.output or b'')
        with captured_engine(command, package, env,
                directory / 'webots.stdout.log', directory / 'webots.stderr.log') as webots, \
                (directory / 'node.log').open('w', encoding='utf-8') as node_log:
            deadline = time.monotonic() + 60
            while True:
                logs = read(directory / 'webots.stdout.log') + read(directory / 'webots.stderr.log')
                if webots.poll() is not None:
                    raise RuntimeError(f'Installed Webots exited before native readiness: {webots.returncode} (0x{webots.returncode & 0xffffffff:08x})')
                if 'WEBEEBLOCKS_RUNTIME_V2 READY' in logs:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('Installed native readiness not established')
                time.sleep(.1)
            node = subprocess.Popen([node_exe, str(ROOT / 'tools/ci/grand_prix_u_node_probe.js'),
                str(port), 'witness', str(directory / 'events.jsonl'), str(package)],
                cwd=ROOT, env=env, stdout=node_log, stderr=subprocess.STDOUT)
            if node.wait(timeout=600) != 0:
                raise RuntimeError('Installed shared-runtime probe failed')
            deadline = time.monotonic() + 10
            while (not (directory / 'native-result-1.json').exists() or
                   'GP_U_RESULT ' not in read(directory / 'webots.stdout.log') + read(directory / 'webots.stderr.log')):
                if webots.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Native evaluator did not retain its result')
                time.sleep(.1)
    finally:
        try:
            metadata['node_exit'] = node.poll() if node else None
            metadata['webots_exit'] = webots.poll() if webots else None
            stop(node)
        finally:
            # captured_engine already retired Webots once. Do not reinterpret
            # an intentional taskkill exit as a spontaneous crash on retry.
            (directory / 'launch.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    result = validate(directory, seed)
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--webots-home', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32' or not shutil.which('node'):
        raise RuntimeError('Real Windows Webots R2025a and Node 22+ required')
    package, home, output = (p.resolve() for p in (args.package, args.webots_home, args.output))
    if (home / 'resources/version.txt').read_text(encoding='utf-8').strip() != 'R2025a':
        raise ValueError('Wrong Webots version')
    sha = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if (package / 'SOURCE_SHA').read_text(encoding='utf-8').strip() != sha:
        raise ValueError('Wrong installed source SHA')
    verify(package)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    try:
        for seed in (0, 1, 4):
            result = trial(package, home, output, seed)
            if results and result['ast_sha256'] != results[0]['ast_sha256']:
                raise ValueError('Student AST changed between installed configurations')
            results.append(result)
            (output / 'campaign.json').write_text(json.dumps({'source_sha': sha, 'results': results}, indent=2) + '\n', encoding='utf-8')
        print('PASS real Windows R2025a installed assembly, same Blockly AST across 1/2/3 H; GUI workflow/pedagogical acceptance not established')
    finally:
        files = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in output.rglob('*') if p.is_file() and p.name != 'sha256.json'}
        (output / 'sha256.json').write_text(json.dumps(files, sort_keys=True, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
