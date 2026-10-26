"""Verify archived bytes and scoped results; never launches Webots."""
import hashlib,json,tarfile,tempfile
from pathlib import Path
from verify_native import verify
HERE=Path(__file__).resolve().parent
items=json.loads((HERE/'evidence/archives.json').read_text());by_name={}
for item in items:
 p=HERE/'evidence'/item['name'];assert p.stat().st_size==item['size']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
 with tarfile.open(p) as t:
  files={Path(m.name).name:t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
 if 'sha256.json' in files:
  manifest=json.loads(files['sha256.json'])
  bad=[n for n,h in manifest.items() if n in files and hashlib.sha256(files[n]).hexdigest()!=h]
  assert bad==item['internal_manifest_mismatches'],(p,bad)
 by_name[item['name']]=files
 print('ARCHIVE',item['name'],'known mismatches',item['internal_manifest_mismatches'])
with tempfile.TemporaryDirectory(prefix='gp-no-wall-archive-verify-') as tmp:
 for seed in (0,2,3,4,15):
  with tarfile.open(HERE/f'evidence/candidate-s{seed}.tar.xz') as t:t.extractall(Path(tmp)/str(seed),filter='data')
  folder=next((Path(tmp)/str(seed)).glob('gp-u-*-witness-*'));r=verify(folder)
  assert r['result']['status']=='achieved'
  saved=json.loads((HERE/f'evidence/candidate-s{seed}.json').read_text());assert r==saved
  print('REPLAY',seed,r['result']['seconds'],r['result']['crossings'])
 with tarfile.open(HERE/'evidence/historical-s3.tar.xz') as t:t.extractall(Path(tmp)/'historical',filter='data')
 r=verify(next((Path(tmp)/'historical').glob('gp-u-*-witness-*')),True)
 assert r['result']['reason']=='off-track' and r['result']['seconds']==28.632 and not r['turn_requests']
print('PASS archived byte integrity and five positive pose replays; known partial/refused cases remain partial/refused')
