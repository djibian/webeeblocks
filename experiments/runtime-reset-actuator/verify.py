"""Revalidate raw bytes and bounded claims; never infer historical causality."""
import hashlib,importlib.util,json,math,re,tarfile
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
  with tarfile.open(path) as tar:
   files={str(Path(m.name).relative_to(name)):tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
  manifest=json.loads(files['sha256.json']);assert set(manifest)==set(files)-{'sha256.json'}
  assert all(hashlib.sha256(files[n]).hexdigest()==d for n,d in manifest.items())
  if entry['kind']=='preparation-error':
   assert 'controller-0.log' not in files;print(name,'preparation only; no native verdict');continue
  log=files['controller-0.log'].decode();analysis=phase.summarize(log)
  assert analysis==json.loads(files['phase-analysis.json'])
  assert [{k:v for k,v in row.items() if k!='first_three_samples'} for row in analysis['resets']]==entry['resets']
  rows=[json.loads(line) for line in files['events.jsonl'].splitlines()]
  provenance=json.loads(files['provenance.json'])
  assert provenance['git_head']==result['main']
  c_hash=[v for k,v in provenance['sha256'].items() if k.endswith('/crazyflie_runtime_v2.c')]
  assert c_hash==[hashlib.sha256(files['runtime-instrumented.c']).hexdigest()]
  if name=='actuator-collision-baseline':
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
