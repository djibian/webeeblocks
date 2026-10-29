"""Exercise one compiled Webots variant; verify the actual callback's context."""
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

variant, expected_binary, observer, evidence = sys.argv[1:]
assert variant in ('baseline', 'selfpipe')
OUT = Path(evidence).resolve()/variant
OUT.mkdir(parents=True, exist_ok=False)
home = Path('/usr/local/webots')
elf = home/'bin/webots-bin'
expected_hash = hashlib.sha256(Path(expected_binary).read_bytes()).hexdigest()
assert hashlib.sha256(elf.read_bytes()).hexdigest() == expected_hash
info = elf.stat()
identity = dict(variant=variant, elf_sha256=expected_hash,
                elf_inode=info.st_ino, elf_device=info.st_dev)
identity['qt_libraries'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in [home/f'lib/webots/libQt6{name}.so.6' for name in ('Core','Gui','Widgets')]}
symbols = subprocess.check_output(['nm', '-an', '-C', str(elf)], text=True)
callbacks = re.findall(r'^([0-9a-f]+) [tT] quitApplication\(int\)$', symbols, re.M)
assert len(callbacks) == 1, 'ambiguous compiled callback identity'
identity['callback_offset'] = int(callbacks[0], 16)
(OUT/'identity.json').write_text(json.dumps(identity, indent=2)+'\n')

original = gp.native_webots_launch
def launch(*args):
    return ['env', 'LD_PRELOAD='+str(Path(observer).resolve()),
            'QT665_SIGNAL_TRACE='+str(OUT/'trace.bin'),
            'QT665_SIGNAL_MAPS='+str(OUT/'loader-maps.txt'), *original(*args)]
gp.native_webots_launch = launch
gp.OUT = OUT/'native'
os.environ['WEBOTS_HOME'] = str(home)
os.environ['LIBGL_ALWAYS_SOFTWARE'] = 'true'
sys.argv = [gp.__file__, '--native', '--suite', 'unavailable', '--seed', '0', '--side', '2.0']
gp.main()  # Existing internal controllers, AST, world, result/EOF/seal oracles.

raw = (OUT/'trace.bin').read_bytes()
assert raw and len(raw) % 48 == 0
rows = []
for magic,pid,tid,event,depth,value in struct.iter_unpack('<6Q',raw):
    assert magic == 0x5154363635534947
    rows.append(dict(pid=pid,tid=tid,event=chr(event),depth=depth,value=value))
assert len({r['pid'] for r in rows}) == 1
assert [r['value'] for r in rows if r['event']=='I'] == [info.st_ino]
assert [r['value'] for r in rows if r['event']=='D'] == [info.st_dev]
registration = [r['value'] for r in rows if r['event']=='R']
bases = [r['value'] for r in rows if r['event']=='P']
assert len(registration)==len(bases)==4
assert all(p-b == identity['callback_offset'] for p,b in zip(registration,bases))
depths = {}
for r in rows:
    tid = r['tid']
    if r['event']=='E':
        depths[tid] = depths.get(tid,0)+1
        assert depths[tid] == r['depth']
    elif r['event']=='L':
        assert depths.get(tid,0) == r['depth']
        depths[tid] -= 1
    elif r['event'] in 'MCAFmca':
        assert depths.get(tid,0) == r['depth'] and r['depth'] > 0
assert all(value==0 for value in depths.values())
entries = [r for r in rows if r['event']=='E' and r['value']==15]
assert entries, 'no actual SIGTERM delivered'
allocations = [r for r in rows if r['event'] in 'MCAF']
assert bool(allocations) == (variant=='baseline'), 'context contrast refuted'
trials = list((OUT/'native').glob('gp-u-v1-*'))
assert len(trials)==1
result = json.loads((trials[0]/'result.json').read_text())
assert result['status']=='not-achieved' and result['mode']=='unavailable'
assert result['ast_sha256']=='89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d'
text = (trials[0]/'webots.log').read_text()
for name in ('grand_prix_u_flight', 'grand_prix_u_evaluator'):
    assert f'INFO: {name}: Terminating.' in text
maps = (OUT/'loader-maps.txt').read_text()
for path in identity['qt_libraries']: assert path in maps
summary = dict(variant=variant, actual_pid=rows[0]['pid'], elf_sha256=expected_hash,
    callback_offset=identity['callback_offset'], sigterm_entries=len(entries),
    allocations_inside_handler=allocations, native_result=result,
    events_sha256=hashlib.sha256((trials[0]/'events.jsonl').read_bytes()).hexdigest(),
    world_sha256=hashlib.sha256((trials[0]/'world.wbt').read_bytes()).hexdigest(),
    claim='one compiled living Webots consumer, not full platform or historical crash repair')
(OUT/'trace.json').write_text(json.dumps(rows, indent=2)+'\n')
(OUT/'RESULT.json').write_text(json.dumps(summary, indent=2)+'\n')
print('QT665_COMPILED_CONSUMER '+json.dumps(summary), flush=True)
