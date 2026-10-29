"""Existing full mission suite on one exact combined Webots ELF, NON-GATE."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import tools.ci.run_grand_prix_u_prototype as gp


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    expected, observer, destination = sys.argv[1:]
    out = Path(destination).resolve()
    out.mkdir(parents=True, exist_ok=False)
    elf = Path('/usr/local/webots/bin/webots-bin')
    assert sha(elf) == expected, 'installed ELF differs from qualified build'
    identity = elf.stat()
    symbols = subprocess.check_output(['nm', '-an', '-C', str(elf)], text=True)
    offsets = re.findall(r'^([0-9a-f]+) [tT] quitApplication\(int\)$', symbols, re.M)
    assert len(offsets) == 1, 'ambiguous callback identity'
    offset = int(offsets[0], 16)
    qt = {str(p): sha(p) for p in sorted(elf.parents[1].glob('lib/webots/libQt6*.so.6.5.3'))}
    assert qt, 'Qt runtime absent'
    launches = []
    original = gp.native_webots_launch

    def launch(*args):
        capture = out / ('consumer-%02d' % (len(launches) + 1))
        capture.mkdir()
        launches.append(capture)
        return ['env', 'LD_PRELOAD=' + str(Path(observer).resolve()),
                'QT665_SIGNAL_TRACE=' + str(capture / 'trace.bin'),
                'QT665_SIGNAL_MAPS=' + str(capture / 'loader-maps.txt'),
                *original(*args)]

    gp.native_webots_launch = launch
    gp.OUT = out / 'native'
    sys.argv = [gp.__file__, '--native', '--suite', 'all', '--side', '2.0']
    gp.main()  # Original complete suite, fatal guards, cleanup and seal audit.
    assert len(launches) == 20, 'incomplete existing all suite'
    consumers = []
    pids = set()
    for capture in launches:
        raw = (capture / 'trace.bin').read_bytes()
        assert raw and len(raw) % 48 == 0, 'incomplete trace'
        rows = []
        for magic, pid, tid, event, depth, value in struct.iter_unpack('<6Q', raw):
            assert magic == 0x5154363635534947
            rows.append(dict(pid=pid, tid=tid, event=chr(event), depth=depth, value=value))
        subjects = {r['pid'] for r in rows}
        assert len(subjects) == 1 and not (subjects & pids), 'ambiguous/reused subject'
        pids.update(subjects)
        assert [r['value'] for r in rows if r['event'] == 'I'] == [identity.st_ino]
        assert [r['value'] for r in rows if r['event'] == 'D'] == [identity.st_dev]
        callbacks = [r['value'] for r in rows if r['event'] == 'R']
        bases = [r['value'] for r in rows if r['event'] == 'P']
        assert len(callbacks) == len(bases) == 4
        assert all(p - b == offset for p, b in zip(callbacks, bases))
        depths = {}
        for row in rows:
            tid = row['tid']
            if row['event'] == 'E':
                depths[tid] = depths.get(tid, 0) + 1
                assert depths[tid] == row['depth']
            elif row['event'] == 'L':
                assert depths.get(tid, 0) == row['depth']
                depths[tid] -= 1
            elif row['event'] in 'MCAFmca':
                raise AssertionError('allocator observed in actual handler')
        assert all(d == 0 for d in depths.values()), 'unbalanced signal trace'
        maps = (capture / 'loader-maps.txt').read_text()
        for module in ('Core', 'Gui', 'Widgets'):
            assert '/usr/local/webots/lib/webots/libQt6' + module + '.so' in maps
        (capture / 'trace.json').write_text(json.dumps(rows, indent=2) + '\n')
        consumers.append(dict(pid=next(iter(subjects)),
                              signal_entries=sum(r['event'] == 'E' for r in rows),
                              allocations_observed=0, trace_sha256=sha(capture / 'trace.bin')))
    assert sum(c['signal_entries'] for c in consumers) > 0, 'no live signal exercised'
    assert sha(elf) == expected and all(sha(p) == digest for p, digest in qt.items())
    result = dict(scope='combined parent-safe + e9 POSIX self-pipe; existing all native suite',
                  verdict='PASS', elf_sha256=expected, callback_offset=offset,
                  qt_sha256=qt, consumers=consumers,
                  campaign=json.loads((gp.OUT / 'campaign.json').read_text()),
                  limits=['not a historical crash attribution', 'observer may alter timing',
                          'no Windows/distribution/OCI adoption or Ready CI Gate'])
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    print('QT665_COMBINED_NATIVE_SUITE=PASS ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
