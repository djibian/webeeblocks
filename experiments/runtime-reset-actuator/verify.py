"""Revalidate raw bytes and bounded claims; never infer historical causality."""
import hashlib,importlib.util,json,math,re,tarfile,zipfile,tempfile,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
phase=module('phase_analyzer',ROOT/'experiments/runtime-reset-phase/analyze.py')
import sys
sys.path.insert(0,str(ROOT))
contact=module('contact',ROOT/'experiments/runtime-reset-contact/run.py')
def verify():
 result=json.loads((HERE/'RESULTS.json').read_text())
 for name,entry in result['experiments'].items():
  path=HERE/entry['archive'];assert path.stat().st_size==entry['bytes'];assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
  if entry.get('format')=='zip':
   with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
  else:
   with tarfile.open(path) as tar:
    files={str(Path(m.name).relative_to(name)):tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
  manifest=json.loads(files['sha256.json']);assert set(manifest)==set(files)-{'sha256.json'}
  assert all(hashlib.sha256(files[n]).hexdigest()==d for n,d in manifest.items())
  if entry['kind']=='preparation-error':
   assert 'controller-0.log' not in files;print(name,'preparation only; no native verdict');continue
  log=files['webots.log' if entry['kind']=='native-browser' else 'controller-0.log'].decode();analysis=phase.summarize(log)
  assert analysis==json.loads(files['reset-phase-summary.json' if entry['kind']=='native-browser' else 'phase-analysis.json'])
  assert [{k:v for k,v in row.items() if k!='first_three_samples'} for row in analysis['resets']]==entry['resets']
  rows=[json.loads(line) for line in files['browser-events.jsonl' if entry['kind']=='native-browser' else 'events.jsonl'].splitlines()]
  provenance=json.loads(files['reset-phase-provenance.json' if entry['kind']=='native-browser' else 'provenance.json'])
  assert provenance['git_head']==entry.get('git_head',result['main'])
  c_hash=[v for k,v in provenance['sha256'].items() if k.endswith('/crazyflie_runtime_v2.c') or k=='runtime-instrumented.c']
  assert c_hash==[hashlib.sha256(files['runtime-instrumented.c']).hexdigest()]
  if entry['kind']=='native-browser':
   assert len(analysis['resets'])==14 and all(r['terminal'].endswith(' OK') for r in analysis['resets'])
   assert 'WEBEEBLOCKS_AUTONOMOUS_COLLISION attempt=7 ' in log and 'WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=7 status=not-achieved' in log
   assert any(r['event']=='AUTONOMOUS_MISSION_TEST_COMPLETE' for r in rows)
   with tempfile.TemporaryDirectory() as tmp:
    for name_,content in files.items():
     assert '/' not in name_ and name_ not in ('.','..')
     (Path(tmp)/name_).write_bytes(content)
    compared=json.loads(subprocess.check_output([sys.executable,str(HERE/'compare_phase.py'),tmp],text=True))
   assert compared==json.loads((HERE/'BROWSER_COMPARISON.json').read_text())
   assert sum(r['compared'] for r in compared['resets'])==135
   assert all(not r['runtime_false_native_true'] and not r['runtime_true_native_false'] for r in compared['resets'])
  elif entry['kind']=='native-early-reset':
   assert len(analysis['resets'])==7 and all(r['terminal'].endswith(' OK') for r in analysis['resets'])
   assert any(r['event']=='FAST_RESET_ACK' for r in rows) and any(r['event']=='FAST_FRESH' for r in rows)
   native=''.join(files[f'controller-{i}.log'].decode() for i in range(8))
   assert 'WEBEEBLOCKS_AUTONOMOUS_COLLISION attempt=7 ' in native
   for i in range(4):assert any(r['event']=='integrated-'+str(i) and r['detail']=={'status':'achieved'} for r in rows)
   for key in ('fixed-negative','memory-negative'):assert any(r['event']==key and r['detail']['status']=='not-achieved' for r in rows)
   resets=[i for i,r in enumerate(rows) if r['event']=='request' and re.fullmatch(r'WEBEEBLOCKS_RUNTIME_V2 REQUEST \d+ RESET',r['detail'])]
   assert len(resets)==7
   previous_ack=next(i for i,r in enumerate(rows) if r['event']=='response' and r['detail']==f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE {analysis['resets'][5]['id']} OK")
   unsafe=[i for i,r in enumerate(rows) if previous_ack<i<resets[-1] and r['event']=='response' and ' ERR UNSAFE_OR_TIMEOUT' in r['detail']]
   assert len(unsafe)==1 and not any(r['event']=='request' for r in rows[unsafe[0]+1:resets[-1]])
  elif name=='actuator-collision-baseline':
   native=''.join(files[f'controller-{i}.log'].decode() for i in range(8))
   assert contact.validate_events('baseline',rows,native)['reset_acknowledgements']==7
   assert 'ACTUATOR_COMMAND' in log
  else:
   assert len(analysis['resets'])==1
   targets=re.findall(r'ACTUATOR_TARGET .*? motors=([^\n]+)',log)
   assert len(targets)==analysis['resets'][0]['samples']
   assert all(all(float(x)==0 for x in values.split(',')) for values in targets)
   terminal=analysis['resets'][0]['terminal'];case=json.loads(files['actuator-case.json'])
   if name=='actuator600-prepared':
    assert terminal.endswith('ERR RESET_TIMEOUT') and case['speed']==600
    assert 'elapsed=5.024000' in log
    # The long false predicates correspond to real native body movement.
    begin=analysis['resets'][0]['begin_time']
    native=[json.loads(l) for l in files['native-reset-state.jsonl'].splitlines()[1:]]
    during=[r for r in native if begin+.128<=r['time']<begin+5.]
    assert len(during)>140 and all(r['position'][2]>.05 and r['velocity'][2]>.15 for r in during)
   else:
    assert terminal.endswith(' OK') and math.isclose(analysis['resets'][0]['final_stable_span'],.256,abs_tol=1e-8)
  print(name,'verified;',len(analysis['resets']),'native RESET records')
if __name__=='__main__':verify()
