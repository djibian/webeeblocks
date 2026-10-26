"""Verify original s3 evidence and reconstruct its airborne lateral force.
Usage: analyze.py ORIGINAL.zip REDUCED_CAPTURE_DIRECTORY
The vertical velocity determines thrust; X/Y are independent predictions.
This is a force balance, not measured rotor telemetry or PID identification.
"""
import csv,hashlib,io,json,math,sys,zipfile
from pathlib import Path
archive,capture=Path(sys.argv[1]),Path(sys.argv[2])
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(archive.read_bytes())=='445bd574d1ee8412d8d681e49b35ce60dda3e8302f8d9384befaa3e6f7abaf9a'
z=zipfile.ZipFile(archive);assert z.testzip() is None
members=0
for name in z.namelist():
 if name.endswith('/sha256.json'):
  base=name.rsplit('/',1)[0]+'/'
  for member,digest in json.loads(z.read(name)).items():
   assert sha(z.read(base+member))==digest;members+=1
name=next(n for n in z.namelist() if 's3-witness' in n and n.endswith('/native_trace.csv'))
rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(io.StringIO(z.read(name).decode()))]
layout=json.loads(z.read(name.rsplit('/',1)[0]+'/layout.json'))
boxes=layout['walls']+layout['gate_boxes']
free=[]
for a,b in zip(rows,rows[1:]):
 if not 174.88-1e-8<=a['time']<175.28:continue
 # World-Z half extent of the unchanged oriented cylinder.
 gap=a['z']-.015*a['r8']-.05*math.hypot(a['r2'],a['r5'])
 # The body fits inside a radius-.0523 sphere. Show every box is disjoint.
 box_distance=min(math.sqrt(sum(max(abs(a[axis]-box[axis])-box['s'+axis]/2,0)**2 for axis in 'xyz')) for box in boxes)
 assert gap>0 and box_distance>math.hypot(.05,.015)
 dt=b['time']-a['time'];thrust=.05*((b['vz']-a['vz'])/dt+9.81)/a['r8']
 residual=[(b['v'+axis]-a['v'+axis])/dt-thrust/.05*a['r'+str(i)] for axis,i in [('x',2),('y',5)]]
 free.append({'time':a['time'],'plane_gap_m':gap,'box_distance_m':box_distance,'thrust_N':thrust,
              'predicted_ay':thrust/.05*a['r5'],'residual_xy_m_s2':residual})
assert len(free)==50
for member,digest in json.loads((capture/'sha256.json').read_text()).items():assert sha((capture/member).read_bytes())==digest
protocol=json.loads((capture/'protocol.json').read_text());assert protocol['source_trace_sha256']==sha(z.read(name))
reduced={};powered=json.loads((capture/'powered/observations.json').read_text())
for case in protocol['cases']:
 r=json.loads((capture/case/'observations.json').read_text());cut=next((a['time'] for a in r if a['cut']),None)
 if cut is not None:
  # Same complete physical prefix, including contact detection, up to actuation.
  for a,b in zip(powered,r):
   if a['time']>cut:break
   assert {k:v for k,v in a.items() if k!='cut'}=={k:v for k,v in b.items() if k!='cut'}
 reduced[case]={'cut_s':cut,'final_position_m':r[-1]['position'],
  'displacement_xy_m':math.dist(r[0]['position'][:2],r[-1]['position'][:2]),
  'max_vxy_m_s':max(math.hypot(*a['velocity'][:2]) for a in r)}
print(json.dumps({'original_zip_sha256':sha(archive.read_bytes()),'crc_members':len(z.namelist()),
 'verified_manifest_entries':members,'trace_sha256':sha(z.read(name)),
 'free_flight':{'samples':len(free),'start':free[0]['time'],'end':free[-1]['time']+.008,
  'min_plane_gap_m':min(a['plane_gap_m'] for a in free),
  'min_box_distance_m':min(a['box_distance_m'] for a in free),
  'thrust_range_N':[min(a['thrust_N'] for a in free),max(a['thrust_N'] for a in free)],
  'max_abs_xy_prediction_residual_m_s2':max(abs(v) for a in free for v in a['residual_xy_m_s2']),
  'max_ay_m_s2':max(a['predicted_ay'] for a in free)},
 'reduced_native_intervention':reduced,
 'limits':['force balance is not measured motor telemetry',
 'reduced probe uses a backward finite-difference angular velocity and constant hover force, not exact archived PID/actuator state',
 'reduced probe is not a full mission, browser, canonical CI, RESET or real-flight proof']},indent=2,allow_nan=False))
