"""Attest one FULL Webots R2025a composed Qt-lifetime+POSIX-signal native consumer.

Deliberately one unchanged negative, no CI Gate or product distribution.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import tools.ci.run_grand_prix_u_prototype as gp
P=ROOT/'experiments/qt665-composed'
OUT=ROOT/'ci-artifacts/qt665-composed'
ELF=Path('/usr/local/webots/bin/webots-bin')
TARGET=OUT/'webots-bin'
assert os.environ['WEBOTS_HOME']=='/usr/local/webots'
assert ELF.is_file() and TARGET.is_file()
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda:f.read(1<<20),b''):h.update(buf)
    return h.hexdigest()
expected=sha(TARGET)
assert sha(ELF)==expected, 'installed Webots does not match built composed ELF'
assert sha(P/'selfpipe.patch')=='e9a6d9365011e55fe853fea1026d9b83be097feb4ba9a4759639fe75796f54b8'
assert (Path('/usr/local/webots/resources/version.txt').read_text().strip()=='R2025a')
stat=ELF.stat()
nm=subprocess.check_output(['nm','-an','-C',str(ELF)],text=True)
symbols=re.findall(r'^([0-9a-f]+) [tT] quitApplication\(int\)$',nm,re.M)
assert len(symbols)==1, 'patched callback not uniquely identifiable in real Webots ELF'
offset=int(symbols[0],16)
observer=OUT/'observe.so'
subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC','-O2',
                str(P/'observe.c'),'-ldl','-o',str(observer)],check=True)
original=gp.native_webots_launch
def observed_launch(*args):
    return ['env','LD_PRELOAD='+str(observer),
        'QT665_SIGNAL_TRACE='+str(OUT/'trace.bin'),
        'QT665_SIGNAL_MAPS='+str(OUT/'loader-maps.txt'),
        *original(*args)]
gp.native_webots_launch=observed_launch
gp.OUT=OUT/'native'
os.environ['LIBGL_ALWAYS_SOFTWARE']='true'
sys.argv=[gp.__file__,'--native','--suite','unavailable','--seed','0','--side','2.0']
gp.main()
raw=(OUT/'trace.bin').read_bytes()
assert raw and len(raw)%48==0,'missing/partial true native signal trace'
rows=[]
for row in struct.iter_unpack('<6Q',raw):
    magic,pid,tid,event,depth,value=row
    assert magic==0x5154363635534947, 'corrupt native signal trace'
    rows.append(dict(pid=pid,tid=tid,event=chr(event),depth=depth,value=value))
assert len({r['pid'] for r in rows})==1, 'ambiguous Webots PID'
assert [r['value'] for r in rows if r['event']=='I']==[stat.st_ino]
assert [r['value'] for r in rows if r['event']=='D']==[stat.st_dev]
registered=[r for r in rows if r['event']=='R']
bases=[r for r in rows if r['event']=='P']
assert len(registered)==len(bases)==4
assert all(r['value']-b['value']==offset for r,b in zip(registered,bases)), 'wrong mapped callback'
current={}
for r in rows:
    tid=r['tid'];e=r['event']
    if e=='E':
        current[tid]=current.get(tid,0)+1
        assert current[tid]==r['depth']
    elif e=='L':
        assert current.get(tid,0)==r['depth']
        current[tid]-=1
    elif e in 'MCAmcaF':
        assert current.get(tid,0)==r['depth'] and r['depth']>0, 'allocator observed in signal handler'
assert all(v==0 for v in current.values()), 'unbalanced native handler'
signals=[r for r in rows if r['event']=='E' and r['value']==15]
assert signals, 'no native Webots SIGTERM handled'
assert len(signals)==len([r for r in rows if r['event']=='L' and r['value']==15])
trials=[p for p in (OUT/'native').iterdir() if p.name.startswith('gp-u-v1-') and p.is_dir()]
assert len(trials)==1, 'not exactly one sealed trial'
trial=trials[0]
result=json.loads((trial/'result.json').read_text())
assert result['status']=='not-achieved' and result['reason']=='runtime' and result['mode']=='unavailable',result
assert result['ast_sha256']=='89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d'
text=(trial/'webots.log').read_text()
for control in ('grand_prix_u_flight','grand_prix_u_evaluator'):
    assert f'INFO: {control}: Terminating.' in text
qm=(OUT/'loader-maps.txt').read_text()
libhashes={}
for component, expected_hash in (
    ('Core','ac391204135f1435ca1c97a7f92e6f94d9d369f6b12fb823923496360a272bd8'),
    ('Gui','f8396f49e2bcfb3e667ba17bd861f1f0be806153141cc3966e79f726818e24e9'),
    ('Widgets','868b516dde6d020badc7243facd48f880b0d606c76e46e50427c1c744a2c1024')):
    lib=Path(f'/usr/local/webots/lib/webots/libQt6{component}.so.6')
    assert str(lib) in qm, 'runtime Qt DSO absent from maps: '+component
    assert sha(lib)==expected_hash, 'Qt DSO mismatch '+component
    libhashes[component]=expected_hash
check={'status':'PASS_BOUND_COMPOSED_NATIVE','source_qt_sha':'79370071ff99b871da0e3a9b4c0be6104074783e',
    'source_posix_patch_sha256':'e9a6d9365011e55fe853fea1026d9b83be097feb4ba9a4759639fe75796f54b8',
    'composed_loaded_elf_sha256':expected,'pid':rows[0]['pid'],'elf_device':stat.st_dev,'elf_inode':stat.st_ino,
    'native_callback_offset':hex(offset),'signal_entries':len(signals),
    'allocator_events_in_signal':0,'native_result':result,
    'world_sha256':sha(trial/'world.wbt'),'events_sha256':sha(trial/'events.jsonl'),
    'qt_dso_sha256':libhashes,
    'limits':['one unavailable negative only; no universal #665 crash repair',
        'no complete native suites or #637 RESET recovery qualification',
        'not shipped to OCI/installer/Windows; no Ready HEAD/CI Gate/GO']}
(OUT/'trace.json').write_text(json.dumps(rows,indent=2)+'\n')
(OUT/'RESULT.json').write_text(json.dumps(check,indent=2)+'\n')
print('QT665_COMPOSED_ACTUAL_WEBOTS '+json.dumps(check,sort_keys=True),flush=True)
