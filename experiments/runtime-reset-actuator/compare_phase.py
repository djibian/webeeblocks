import json,math,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/runtime-reset-phase'))
from analyze import fields,summarize
p=Path(sys.argv[1]); log=(p/'webots.log').read_text(); summary=summarize(log)
native={round(r['time'],9):r for r in map(json.loads,(p/'native-reset-state.jsonl').read_text().splitlines()[1:])}
records={};origins={}
for line in log.splitlines():
 if ' RESET_PHASE_BEGIN ' in line:
  r=fields(line);origins[int(r['id'])]=r
 if ' RESET_PHASE_SAMPLE ' in line:
  r=fields(line);records.setdefault(int(r['id']),[]).append(r)
out={'scope':'aligned observations after +64 ms; no universal cause or health verdict','resets':[]}
for r in summary['resets']:
 identity=r['id'];origin=origins[identity];a={'id':identity,'receipt_time':r['begin_time'],'elapsed':r['last_sample_elapsed'],'terminal':r['terminal'],'compared':0,'runtime_false_native_true':[],'runtime_true_native_false':[],'max_position_error':0.,'max_velocity_error':0.,'max_gyro_error':0.}
 for row in records[identity]:
  if row['elapsed']<.064-1e-8:continue
  n=native.get(round(row['time'],9))
  if n is None:raise ValueError('missing native time '+str(row['time']))
  m=n['orientation'];v=n['velocity'];rpy=[math.atan2(m[7],m[8]),math.atan2(-m[6],math.hypot(m[7],m[8])),math.atan2(m[3],m[0])]
  bg=[sum(m[k*3+i]*v[3+k] for k in range(3)) for i in range(3)]
  pose=all(abs(x-y)<tol for x,y,tol in zip(n['position'],origin['origin'],(.03,.03,.05))) and all(abs(x-y)<math.pi/90 for x,y in zip(rpy[:2],origin['origin_rpy'][:2])) and abs(math.remainder(rpy[2]-origin['origin_rpy'][2],2*math.pi))<math.pi/90
  motion=math.hypot(*v[:2])<.12 and abs(v[2])<.15 and abs(bg[2])<.10
  runtime=bool(row['pose_ready'] and row['motion_ready']);physical=pose and motion
  if not runtime and physical:a['runtime_false_native_true'].append(row['elapsed'])
  if runtime and not physical:a['runtime_true_native_false'].append(row['elapsed'])
  a['max_position_error']=max(a['max_position_error'],max(abs(x-y) for x,y in zip(row['position'],n['position'])))
  a['max_velocity_error']=max(a['max_velocity_error'],max(abs(x-y) for x,y in zip(row['velocity'],v[:3])))
  a['max_gyro_error']=max(a['max_gyro_error'],max(abs(x-y) for x,y in zip(row['gyro'],bg)))
  a['compared']+=1
 out['resets'].append(a)
print(json.dumps(out,indent=2))
