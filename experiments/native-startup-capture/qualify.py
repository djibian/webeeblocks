#!/usr/bin/env python3
"""Qualify diagnostic prerequisites off simulation; never starts Webots.

Exit 0 establishes only the listed host prerequisites. The actual launch/exec
capture backend must still be qualified separately before Webots. Exit 77
means a necessary host prerequisite failed.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

from support import digest, identity, observe, own_tree, proc_record, seal, snapshot_process, write_json

HERE = Path(__file__).resolve().parent


def qualify_snapshot(fixture, out):
    """No ptrace required: the controlled fixture stops itself for inspection."""
    self_id = identity(proc_record(int(os.readlink('/proc/self'))))
    with (out / 'snapshot-fixture.log').open('w') as stream:
        child = subprocess.Popen([str(fixture), 'snapshot'], stdout=stream, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 2
            record = None
            while time.monotonic() < deadline:
                rows = own_tree({self_id})
                matches = [r for r in rows if r['nspid'] and r['nspid'][-1] == child.pid
                           and r['proc_ppid'] == self_id[0] and r['state'] in ('T', 't')]
                if len(matches) == 1:
                    record = matches[0]
                    break
                time.sleep(.02)
            if record is None:
                raise RuntimeError('stopped fixture identity unavailable')
            objects = snapshot_process(record['proc_pid'], record['start_ticks'], digest(fixture), out / 'stopped-snapshot')
            refused = False
            try:
                snapshot_process(record['proc_pid'], record['start_ticks'] + 1, digest(fixture), out / 'wrong-identity')
            except ProcessLookupError:
                refused = True
            os.kill(child.pid, signal.SIGCONT)
            code = child.wait(timeout=2)
            return {
                'stopped_native_snapshot': code == 0,
                'mapped_objects_fingerprinted': bool(objects) and all('sha256' in o for o in objects.values()),
                'some_build_ids_available': any(o.get('build_id_lines') for o in objects.values()),
                'wrong_starttime_refused': refused,
            }
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gdb', default='gdb')
    parser.add_argument('--gdb-data-directory', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = out / 'fixture'
    compile_result = subprocess.run(['cc', '-g', '-O0', '-fno-omit-frame-pointer',
                                     str(HERE / 'fixture.c'), '-o', str(fixture)],
                                    capture_output=True, text=True, timeout=30)
    (out / 'compile.log').write_text(compile_result.stdout + compile_result.stderr)
    compile_result.check_returncode()
    compiler = subprocess.run(['cc', '--version'], capture_output=True, text=True, timeout=5)
    (out / 'compiler-version.log').write_text(compiler.stdout + compiler.stderr)
    packages = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n',
                               '*mesa*', '*xvfb*', '*xserver*', '*libgl*', '*gdb*'],
                              capture_output=True, text=True, timeout=5)
    (out / 'graphics-packages.log').write_text(packages.stdout + packages.stderr)
    results = {}
    for mode in ('exit42', 'segv', 'wrapper', 'ptrace'):
        results[mode] = observe([str(fixture), mode], out / mode)
    assertions = {
        'normal_exit42': results['exit42']['launcher_returncode'] == 42,
        'direct_sigsegv': results['segv']['launcher_returncode'] == -11,
        'wrapper_exit_zero': results['wrapper']['launcher_returncode'] == 0,
        'wrapper_wait_identifies_child_signal': 'signaled=1 signal=11' in (out / 'wrapper/process.log').read_text(),
    }
    assertions.update(qualify_snapshot(fixture, out))
    wrapper = results['wrapper']
    log = (out / 'wrapper/process.log').read_text()
    child_pid = int(re.search(r'WAIT child=(\d+)', log)[1])
    matching = [r for r in wrapper['process_births'].values()
                if r['nspid'] and r['nspid'][-1] == child_pid and
                r['cmdline'].strip().endswith(' segv')]
    assertions['native_child_identity_observed'] = len(matching) == 1
    assertions['live_wrapper_after_child_gone'] = bool(matching) and any(
        any(r['nspid'] and r['nspid'][-1] == wrapper['launcher_syscall_pid'] and r['state'] != 'Z'
            for r in tick['processes']) and not any(
                r['proc_pid'] == matching[0]['proc_pid'] and r['start_ticks'] == matching[0]['start_ticks']
                for r in tick['processes']) for tick in wrapper['timeline'])
    assertions['no_fixture_timeout'] = not any(r['termination_requested_by_capture'] for r in results.values())
    gdb = shutil.which(args.gdb)
    if gdb:
        command = [gdb, '--nx', '--nh', '--batch']
        if args.gdb_data_directory:
            command += ['--data-directory=' + str(args.gdb_data_directory.resolve())]
        command += ['-ex', 'set pagination off', '-ex', 'set disable-randomization off',
                    '-ex', 'set debuginfod enabled off',
                    '-ex', 'handle SIGSEGV stop print nopass',
                    '-ex', 'show version', '-ex', 'run', '-ex', 'info inferiors',
                    '-ex', 'info registers', '-ex', 'info sharedlibrary',
                    '-ex', 'info proc mappings', '-ex', 'thread apply all bt full',
                    '--args', str(fixture), 'segv']
        results['gdb'] = observe(command, out / 'gdb', timeout=15)
        trace = (out / 'gdb/process.log').read_text()
        assertions['gdb_real_sigsegv_stack'] = (
            'received signal SIGSEGV' in trace and
            re.search(r'#\d+.*intentional_fixture_segv', trace) is not None and
            'Operation not permitted' not in trace and
            not results['gdb']['termination_requested_by_capture'])
    else:
        assertions['gdb_real_sigsegv_stack'] = False
    summary = {
        'assertions': assertions, 'host_prerequisites_passed': all(assertions.values()),
        'acquisition_allowed': False,
        'fixture_sha256': digest(fixture),
        'support_sha256': {p.name: digest(p) for p in (HERE / 'fixture.c', HERE / 'support.py', HERE / 'qualify.py')},
        'gdb': {'path': gdb, 'sha256': digest(gdb) if gdb else None},
        'ptrace_probe_returncode': results['ptrace']['launcher_returncode'],
        'scope': 'host prerequisite qualification only; no Webots run or READY result',
        'native_capture_backend_qualified': False,
        'remaining': 'A direct-fixture stack is necessary but not sufficient: validate the wrapper/fork/exec GDB recipe before Webots.',
    }
    write_json(out / 'qualification.json', summary)
    archive = out.with_suffix('.zip')
    sha = seal(out, archive)
    print(json.dumps({'qualification': summary, 'archive_sha256': sha}, indent=2))
    # This command is a prerequisite check, never an acquisition launcher.
    return 0 if summary['host_prerequisites_passed'] else 77


if __name__ == '__main__':
    sys.exit(main())
