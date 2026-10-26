"""Verify retained bytes, exact ordinary AST and independent pose replay.

Replay does not recreate contact-point observations; those remain native
supervisor evidence. No simulation or world mutation is performed here.
"""
import argparse,csv,dataclasses,hashlib,json,math,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.grand_prix.layout_u import generate,world_text,RADIUS
from tools.grand_prix.oracle_u import Attempt,local,point_segment_gap,swept_gap

def verify(folder,historical=False):
 p=Path(folder);manifest=json.loads((p/'sha256.json').read_text())
 for name,expected in manifest.items():
  assert hashlib.sha256((p/name).read_bytes()).hexdigest()==expected,(p,name)
 raw=json.loads((p/'layout.json').read_text());layout=generate(raw['seed'],raw['side'])
 assert json.loads(json.dumps(dataclasses.asdict(layout)))==raw
 assert layout.width==.60 and RADIUS==.09 and not layout.walls
 world=world_text(layout,controller='<extern>',window='<none>',evaluator=True)
 world=world.replace('controller "grand_prix_u_evaluator"','controller "<extern>"').replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/','webots://')
 assert (p/'world.wbt').read_text()==world
 result=json.loads((p/'native-result-1.json').read_text());diag=json.loads((p/'native-diagnostic-1.json').read_text())
 events=[json.loads(s) for s in (p/'events.jsonl').read_text().splitlines()]
 programs=[e['detail'] for e in events if e['event']=='program'];assert len(programs)==1
 module='./tools/grand_prix/witness_workspace_u' if historical else './experiments/grand-prix-no-wall/workspace'
 expected=json.loads(subprocess.check_output(['node','-e',f'console.log(JSON.stringify(require("{module}").build().ast))'],cwd=ROOT,text=True))
 assert programs[0]==expected,'ordinary preflighted Blockly AST mismatch'
 digest=hashlib.sha256(json.dumps(expected,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if not historical: assert digest=='b27f65fa1961de2a7b162b11feffcd6c1452769056f10d03e4770c5f32dd5d19'
 errors=[e for e in events if e['event'] in ('error','transport-error','wall-timeout')]
 if result['status']=='achieved':assert not errors
 text=(p/'webots.log').read_text()+(p/'flight.log').read_text()+(p/'evaluator.log').read_text()
 bad=[s for s in text.splitlines() if s.startswith('ERROR:') and not (s.startswith('ERROR: Cannot listen to the local server (server name = ') and 'QLocalServer::listen: Unknown error 1' in s)]
 assert not bad,bad
 a=Attempt(layout,1,diag['origin_z']);a.start(1,diag['start_ms']/1000)
 minimum_boundary=math.inf;minimum_collider=math.inf;crossings=[];samples=0;first=None;last=None
 with (p/'native_trace.csv').open() as f:
  for r in csv.DictReader(f):
   t=float(r['time']);ms=round(t*1000)
   if int(r['attempt'])!=1 or ms<diag['start_ms']:continue
   pose=tuple(float(r[k]) for k in ('x','y','z'));velocity=tuple(float(r[k]) for k in ('vx','vy','vz'))
   assert all(math.isfinite(x) for x in (*pose,*velocity))
   prev=a.previous;old=a.cursor
   replay=a.sample(t,pose,velocity,completed=diag['completion_ms'] is not None and ms>=diag['completion_ms'])
   samples+=1;first=first or t;last=t
   for c,d in zip(layout.polygon,layout.polygon[1:]+layout.polygon[:1]):
    minimum_boundary=min(minimum_boundary,point_segment_gap(prev,c,d),point_segment_gap(pose,c,d),point_segment_gap(c,prev,pose),point_segment_gap(d,prev,pose))
   for b in layout.boxes:minimum_collider=min(minimum_collider,swept_gap(prev,pose,b))
   if a.cursor>old:
    g=layout.gates[old];progress,lateral=local(g,pose)
    crossings.append(dict(time=t,side=g.side,progress=progress,lateral=lateral,z=pose[2]))
   if replay is not None:break
 assert a.result is not None and dataclasses.asdict(a.result)==result,(a.result,result)
 turns=[e['detail'] for e in events if e['event']=='request' and ' TURN ' in e['detail']]
 if result['status']=='achieved':assert len(turns)==2 and len(crossings)==len(layout.gates)
 return dict(folder=p.name,result=result,ast_sha256=digest,pose_replay_without_contacts=True,
  manifest_files=len(manifest),samples_until_result=samples,turn_requests=turns,crossing_clear_events=crossings,
  swept_boundary_margin_m=minimum_boundary-RADIUS,swept_collider_margin_m=minimum_collider-RADIUS,
  final_position=diag['position'],target=diag['landing_target'],time_margin_s=210-result['seconds'],errors=errors)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--historical',action='store_true');args=p.parse_args()
 print(json.dumps(verify(args.folder,args.historical),indent=2,allow_nan=False))
