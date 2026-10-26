#!/usr/bin/env python3
"""Fail-closed observation of a *running* Linux Webots #665 consumer.

This never installs Webots. Successful observation proves the specific process
executable and mapped Qt closure, not a natural Qt callback or a complete suite.
Windows PE and classroom release verification require a separate native probe.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

WEBOTS_SHA256 = 'e45a90b580a00f50dc08746e6f43d1a86a83fcf1b23f55538737309154150545'
QT_SHA256 = {
    'libQt6Widgets.so.6.5.3': '868b516dde6d020badc7243facd48f880b0d606c76e46e50427c1c744a2c1024',
    'libQt6Core.so.6.5.3': 'ac391204135f1435ca1c97a7f92e6f94d9d369f6b12fb823923496360a272bd8',
}


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def starttime(proc):
    # Linux /proc/<pid>/stat: field 22 is starttime. Parenthesized comm may
    # contain spaces and closing parentheses, so split only after last ')'.
    line = (proc / 'stat').read_text()
    end = line.rfind(')')
    if end < 0:
        raise ValueError('malformed process stat')
    tail = line[end + 1:].split()
    if len(tail) < 20:
        raise ValueError('truncated process stat')
    return tail[19]


def attest(runtime_home, pid):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('only native Linux x86_64 consumers supported')
    if pid <= 0:
        raise ValueError('PID must be positive')
    home = runtime_home.resolve(strict=True)
    version = (home / 'resources/version.txt').read_text().strip()
    if version != 'R2025a':
        raise ValueError('Webots version mismatch')
    target = (home / 'bin/webots-bin').resolve(strict=True)
    if not target.is_relative_to(home):
        raise ValueError('Webots executable escaped runtime root')
    proc = Path('/proc') / str(pid)
    started = starttime(proc)
    process_executable = (proc / 'exe').resolve(strict=True)
    if process_executable != target:
        raise ValueError('process is not the installed Webots ELF')
    if sha256(target) != WEBOTS_SHA256 or sha256(proc / 'exe') != WEBOTS_SHA256:
        raise ValueError('running Webots ELF not the qualified parent-safe candidate')
    # A corrected ELF in the install tree is not enough: verify both Qt DSOs
    # actually mapped by this very process, not merely resolved by ldd.
    maps = (proc / 'maps').read_text()
    loaded = {}
    for name, expected in QT_SHA256.items():
        lib = (home / 'lib/webots' / name).resolve(strict=True)
        if not lib.is_relative_to(home):
            raise ValueError('Qt library escaped runtime root: ' + name)
        if sha256(lib) != expected:
            raise ValueError('Qt library checksum mismatch: ' + name)
        mapped = set()
        lib_stat = lib.stat()
        expected_file_id = (os.major(lib_stat.st_dev), os.minor(lib_stat.st_dev), lib_stat.st_ino)
        for line in maps.splitlines():
            # The mapping pathname alone is insufficient: an existing process
            # could still map old DSO bytes after a path was replaced. Require
            # the same kernel device + inode as the checksum-qualified file.
            fields = line.split(maxsplit=5)
            if len(fields) != 6 or not fields[5].startswith('/') or fields[5].endswith(' (deleted)'):
                continue
            path = Path(fields[5])
            if path.name == name:
                device = fields[3].split(':')
                if len(device) != 2:
                    raise ValueError('malformed Qt mapped device: ' + name)
                observed_file_id = (int(device[0], 16), int(device[1], 16), int(fields[4]))
                if observed_file_id != expected_file_id:
                    raise ValueError('Qt mapping inode differs from installed file: ' + name)
                mapped.add(path.resolve(strict=True))
        if mapped != {lib}:
            raise ValueError('Qt library not uniquely mapped from runtime: ' + name)
        loaded[name] = expected
    if starttime(proc) != started or (proc / 'exe').resolve(strict=True) != target:
        raise ValueError('process identity changed during observation')
    return {'verdict': 'PASS', 'scope': 'running-linux-process-elf-and-mapped-qt-only',
            'pid': pid, 'process_starttime_ticks': started,
            'webots_elf_sha256': WEBOTS_SHA256, 'qt_sha256': loaded,
            'runtime_home': str(home), 'executable': str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-home', type=Path, required=True)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    result = {'verdict': 'UNPROVEN', 'scope': 'running-linux-process-elf-and-mapped-qt-only'}
    try:
        result = attest(args.runtime_home, args.pid)
    except (OSError, ValueError) as error:
        result['error'] = str(error)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    if result['verdict'] != 'PASS':
        print('QT665_RUNNING_CONSUMER=UNPROVEN ' + result.get('error', ''), file=sys.stderr)
        return 1
    print('QT665_RUNNING_CONSUMER=PASS identity only')
    return 0


if __name__ == '__main__':
    sys.exit(main())
