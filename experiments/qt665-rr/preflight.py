#!/usr/bin/env python3
"""Non-Gate rr host feasibility. Never labels this as a Webots replay."""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess


def command(args, timeout=20):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return dict(argv=args, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
    except (OSError, subprocess.TimeoutExpired) as e:
        return dict(argv=args, error=str(e))


def read(path):
    try:
        return Path(path).read_text()
    except OSError as e:
        return str(e)


def perf_probe(event_type, config):
    # perf_event_attr v0, disabled + exclude_kernel + exclude_hv.
    # Raw Intel 0x1c4 is BR_INST_RETIRED.CONDITIONAL, not a portability oracle.
    attr = ctypes.create_string_buffer(64)
    struct.pack_into('IIQQQQQ', attr, 0, event_type, 64, config, 0, 0, 0, 1 | 32 | 64)
    libc = ctypes.CDLL(None, use_errno=True)
    ctypes.set_errno(0)
    fd = libc.syscall(ctypes.c_long(298), ctypes.byref(attr), ctypes.c_int(0),
                      ctypes.c_int(-1), ctypes.c_int(-1), ctypes.c_ulong(0))
    error = ctypes.get_errno() if fd < 0 else 0
    if fd >= 0:
        os.close(fd)
    return dict(type=event_type, config=hex(config), fd_opened=fd >= 0,
                errno=error, error=errno.errorcode.get(error, 'OK'))


def ptrace_probe():
    pid = os.fork()
    if pid == 0:
        libc = ctypes.CDLL(None, use_errno=True)
        result = libc.ptrace(0, 0, None, None)  # PTRACE_TRACEME; exits, no stop.
        os._exit(ctypes.get_errno() if result == -1 else 0)
    _, status = os.waitpid(pid, 0)
    code = os.waitstatus_to_exitcode(status)
    return dict(child_exitcode=code, error=errno.errorcode.get(code, 'OK'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    os.chmod(args.out, 0o700)
    report = dict(scope='host-only; NOT Webots recording feasibility',
                  uname=list(platform.uname()), lscpu=command(['lscpu']),
                  cpuinfo=read('/proc/cpuinfo'), process_status=read('/proc/self/status'),
                  perf_event_paranoid=read('/proc/sys/kernel/perf_event_paranoid'),
                  ptrace_scope=read('/proc/sys/kernel/yama/ptrace_scope'),
                  pmu_devices=sorted(p.name for p in Path('/sys/bus/event_source/devices').iterdir()),
                  ptrace_child=ptrace_probe(),
                  executable_paths={k: shutil.which(k) for k in ('rr', 'gdb', 'docker', 'Xvfb')})
    if platform.machine() == 'x86_64':
        report['perf_event_open'] = [perf_probe(0, 4), perf_probe(4, 0x1c4), perf_probe(1, 0)]
    else:
        report['perf_event_open'] = 'not attempted: syscall number is x86_64 only'
    rr = shutil.which('rr')
    if rr:
        report['rr_sha256'] = hashlib.sha256(Path(rr).resolve().read_bytes()).hexdigest()
        report['rr_version'] = command([rr, '--version'])
        trace = args.out.resolve() / 'true-trace'
        report['rr_record'] = command([rr, 'record', '-o', str(trace), '/bin/true'])
        if report['rr_record'].get('returncode') == 0:
            report['rr_replay'] = command([rr, 'replay', '-a', str(trace)])
            report['status'] = ('RR_SMOKE_RECORD_REPLAY_VALID' if
                                report['rr_replay'].get('returncode') == 0 else 'RR_SMOKE_REPLAY_FAILED')
        else:
            report['status'] = 'RR_SMOKE_RECORD_FAILED'
    else:
        report['status'] = 'RR_NOT_INSTALLED'
    report['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    destination = args.out / 'host.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
