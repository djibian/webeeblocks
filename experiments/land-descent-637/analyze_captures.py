"""Read-only verification and summary of the recovered #637 captures.
Run with the directory containing captures as argument. No native process runs.
"""
import hashlib,json,math,re,sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
summary=[]
for p in sorted(root.iterdir()):
 if not p.is_dir() or not p.name.startswith(('full-','historical-','hold-','native-independent-','regression-')):continue
 manifest=next((p/name for name in ('manifest.json','sha256.json') if (p/name).exists()),None)
 integrity='no completed manifest'
 if manifest:
  expected=json.loads(manifest.read_text())
  for name,digest in expected.items():
   member=p/name
   assert member.is_file() and hashlib.sha256(member.read_bytes()).hexdigest()==digest,(p.name,name)
  integrity={'verified_members':len(expected)}
 item={'capture':p.name,'integrity':integrity}
 log=p/'controller.log'
 if log.exists():
  text=log.read_text();rows=[]
  for line in text.splitlines():
   if line.startswith(('LAND_OBS ','LAND_REGRESSION_OBS ')):
    d=dict(re.findall(r'(\w+)=([^ ]+)',line));d['t']=float(d['t']);d['stage']=int(d['stage']);rows.append(d)
  requests=[float(re.search(r't=([0-9.]+)',l).group(1)) for l in text.splitlines() if ('EXPERIMENT_REQUEST' in l or 'REGRESSION_REQUEST' in l) and l.endswith(' LAND')]
  if rows and requests:
   start=min(rows,key=lambda r:abs(r['t']-requests[0]));post=[r for r in rows if r['t']>=requests[0]]
   def pos(r):return [float(v) for v in r.get('pos',r.get('position','')).split(',')]
   def pitch(r):return float(r['pitch']) if 'pitch' in r else float(r['rpy'].split(',')[1])
   first=next((r for r in post if int(r['contacts'])>0),None)
   item.update(land_request_s=requests[0],landing_anchor_m=pos(start),final_position_m=pos(rows[-1]),
    final_xy_displacement_m=math.dist(pos(start)[:2],pos(rows[-1])[:2]),
    maximum_abs_pitch_during_and_after_land_rad=max(abs(pitch(r)) for r in post),
    first_observed_contact=first,
    terminal_marker=next((l for l in reversed(text.splitlines()) if 'REGRESSION_END' in l or 'EXPERIMENT_END' in l),None))
 summary.append(item)
print(json.dumps({'scope':'recovered raw capture integrity and independent recalculated summaries; not canonical mission acceptance','captures':summary},indent=2,allow_nan=False))
