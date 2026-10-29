"""One living Webots consumer, allocator context only; no root-cause verdict."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import tools.ci.run_grand_prix_u_prototype as gp

IMAGE = 'cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099'
assert gp.IMAGE == IMAGE
HERE = ROOT/'experiments/qt665-signal-context'
OUT = ROOT/'ci-artifacts/qt665-signal-context'
OUT.mkdir(parents=True, exist_ok=True)

if '--native' in sys.argv:
    home = Path(os.environ['WEBOTS_HOME'])
    elf = home/'bin/webots-bin'
    digest = hashlib.sha256(elf.read_bytes()).hexdigest()
    assert digest == '1445efb2820d151dee40b79ef4128dca7e4a75e02630b49354e557c7e35e66eb'
    info = elf.stat()
    libraries = {}
    for name in ('Core', 'Gui', 'Widgets'):
        lib = home/f'lib/webots/libQt6{name}.so.6'
        libraries[str(lib.resolve())] = hashlib.sha256(lib.read_bytes()).hexdigest()
    (OUT/'identity.json').write_text(json.dumps({
        'oci': IMAGE, 'elf_sha256': digest, 'elf_device': info.st_dev,
        'elf_inode': info.st_ino, 'qt_libraries': libraries,
        'scope': 'startup loader maps; no QPA/whole environment qualification'}, indent=2)+'\n')
    # One positive/negative observer control in the SAME image/toolchain.
    # These controls qualify only context detection, never Webots behavior.
    control = OUT/'control'
    control.mkdir()
    subprocess.run(['cc', '-O0', '-rdynamic', str(HERE/'control.c'),
                    '-o', str(control/'webots-bin')], check=True)
    controls = {}
    for mode in ('signal', 'normal'):
        env = dict(os.environ, LD_PRELOAD=str(HERE/'observe.so'),
                   QT665_SIGNAL_TRACE=str(control/(mode+'.bin')),
                   QT665_SIGNAL_MAPS=str(control/(mode+'.maps')))
        subprocess.run([str(control/'webots-bin'), mode], env=env, check=True)
        data = (control/(mode+'.bin')).read_bytes()
        assert len(data) % 48 == 0 and data
        records = list(struct.iter_unpack('<6Q', data))
        assert all(r[0] == 0x5154363635534947 for r in records)
        entries = sum(r[3] == ord('E') for r in records)
        allocations = sum(r[3] == ord('M') and r[4] == 1 and r[5] == 120 for r in records)
        assert entries == allocations == int(mode == 'signal')
        controls[mode] = dict(handler_entries=entries, allocations_in_handler=allocations)
    (control/'RESULT.json').write_text(json.dumps(controls, indent=2)+'\n')
    original_launch = gp.native_webots_launch
    def observed_launch(*args):
        # Only the Webots launch gets the observer; node/runner are unmodified.
        return ['env', 'LD_PRELOAD='+str(HERE/'observe.so'),
                'QT665_SIGNAL_TRACE='+str(OUT/'trace.bin'),
                'QT665_SIGNAL_MAPS='+str(OUT/'loader-maps.txt'),
                *original_launch(*args)]
    gp.native_webots_launch = observed_launch
else:
    original_container = gp.native_container_command
    def observed_container(*args, **kwargs):
        command = original_container(*args, **kwargs)
        old = 'python3 -u tools/ci/run_grand_prix_u_prototype.py --native'
        assert command[-1].count(old) == 1
        command[-1] = (
            'cc -std=c11 -Wall -Wextra -Werror -shared -fPIC -O2 '
            'experiments/qt665-signal-context/observe.c -ldl '
            '-o experiments/qt665-signal-context/observe.so\n'
            + command[-1].replace(old,
                'python3 -u experiments/qt665-signal-context/run_probe.py --native'))
        return command
    gp.native_container_command = observed_container

sys.argv = [sys.argv[0], *(['--native'] if '--native' in sys.argv else []),
            '--suite', 'unavailable', '--seed', '0', '--side', '2.0']
gp.main()  # Same world, internal controllers, shared interpreter and native oracles.

if '--native' not in sys.argv:
    identity = json.loads((OUT/'identity.json').read_text())
    raw = (OUT/'trace.bin').read_bytes()
    assert len(raw) % 48 == 0 and raw, 'partial/missing trace'
    rows = []
    for row in struct.iter_unpack('<6Q', raw):
        magic, pid, tid, event, depth, value = row
        assert magic == 0x5154363635534947, 'corrupt trace'
        rows.append(dict(pid=pid, tid=tid, event=chr(event), depth=depth, value=value))
    assert len({r['pid'] for r in rows}) == 1, 'ambiguous Webots identity'
    assert [r['value'] for r in rows if r['event']=='I'] == [identity['elf_inode']]
    assert [r['value'] for r in rows if r['event']=='D'] == [identity['elf_device']]
    current = {}
    allocations = []
    for r in rows:
        tid = r['tid']
        if r['event']=='E':
            current[tid] = current.get(tid, 0)+1
            assert current[tid] == r['depth']
        elif r['event']=='L':
            assert current.get(tid, 0) == r['depth']
            current[tid] -= 1
        elif r['event'] in 'MCAmcaF':
            assert current.get(tid, 0) == r['depth'] and r['depth'] > 0
            if r['event'] in 'MCA': allocations.append(r)
    assert all(value == 0 for value in current.values()), 'incomplete handler'
    assert any(r['event']=='E' and r['value']==15 for r in rows), 'no real SIGTERM handler'
    assert any(r['event']=='S' and r['value']==15 for r in rows), 'no original handler registration'
    (OUT/'trace.json').write_text(json.dumps(rows, indent=2)+'\n')
    result = {'claim': 'observed allocator calls inside original Webots POSIX handler',
        'observed': bool(allocations), 'allocator_calls': allocations,
        'webots_pid': rows[0]['pid'],
        'limits': ['observer can alter timing', 'no interrupted allocator observed',
                   'no corruption or historical #665 causality established',
                   'no candidate Qt repair or full native platform qualification']}
    (OUT/'RESULT.json').write_text(json.dumps(result, indent=2)+'\n')
    print('QT665_SIGNAL_CONTEXT '+json.dumps(result), flush=True)
    # Absence is a valid negative result; missing identity/context is not.
