"""Paired fixed-force intervention from a near-contact s3 pose.
Requires numpy/scipy solely to reconstruct axis-angle/angular velocity from CSV.
The missing original angular velocity is an explicitly approximate derivative.
No PID, actual actuator telemetry, browser or mission PASS is claimed here.
"""
import argparse,csv,hashlib,json,os,shutil,socket,subprocess,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
HERE=Path(__file__).resolve().parent

def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--home',type=Path,required=True);ap.add_argument('--xvfb',required=True);ap.add_argument('--trace',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 assert (a.home/'resources/version.txt').read_text().strip()=='R2025a'
 a.out.mkdir(parents=True,exist_ok=False)
 raw=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(a.trace.open())]
 rows={round(r['time']*1000):r for r in raw};r=rows[174800];prev=rows[174792]
 matrix=lambda r:np.array([r['r'+str(i)] for i in range(9)]).reshape(3,3)
 R=matrix(r);axis=Rotation.from_matrix(R).as_rotvec();angle=float(np.linalg.norm(axis));aa=list(axis/angle)+[angle]
 omega=Rotation.from_matrix(R@matrix(prev).T).as_rotvec()/.008
 p={'source_trace_sha256':digest(a.trace),'source_time':r['time'],
    'position':[r[k] for k in ('x','y','z')],'axis_angle':aa,
    'velocity_6d':[r[k] for k in ('vx','vy','vz')]+list(omega),
    'angular_velocity_scope':'backward 8 ms orientation derivative, not original telemetry',
    'mass':.05,'cylinder_height':.03,'cylinder_radius':.05,'body_force_N':[0,0,.05*9.81],
    'control_scope':'fixed hover force, zero applied torque, no PID; cut after first native contact',
    'cases':['powered','cut0','cut8','cut16','cut24','no-floor']}
 (a.out/'protocol.json').write_text(json.dumps(p,indent=2)+'\n');shutil.copyfile(HERE/'probe.py',a.out/'probe.py');shutil.copyfile(Path(__file__),a.out/'run.py')
 env={k:v for k,v in os.environ.items() if not k.lower().endswith('_proxy')};env.update(WEBOTS_HOME=str(a.home.resolve()),LIBGL_ALWAYS_SOFTWARE='true',LP_NUM_THREADS='1',USER='root',WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
 env['LD_LIBRARY_PATH']=str(a.home/'lib/webots')+':'+str(a.home/'lib/controller')+':'+env.get('LD_LIBRARY_PATH','')
 xp=port();env['DISPLAY']='127.0.0.1:'+str(xp-6000)
 with (a.out/'xvfb.log').open('w') as xlog:
  xvfb=subprocess.Popen([a.xvfb,':'+str(xp-6000),'-ac','-nolisten','unix','-nolisten','local','-listen','tcp','-screen','0','1280x1024x24'],env=env,stdout=xlog,stderr=subprocess.STDOUT)
  try:
   until=time.monotonic()+10
   while True:
    try:
     with socket.create_connection(('127.0.0.1',xp),timeout=.1):break
    except OSError:
     if time.monotonic()>until:raise RuntimeError('Xvfb readiness absent')
     time.sleep(.1)
   for case in p['cases']:
    out=a.out/case;out.mkdir();wp=port()
    xyz=' '.join(map(str,p['position']));rot=' '.join(map(str,p['axis_angle']))
    floor='' if case=='no-floor' else 'Solid { boundingObject Plane { size 20 20 } }'
    (out/'world.wbt').write_text('#VRML_SIM R2025a utf8\nWorldInfo { basicTimeStep 8 randomSeed 1 optimalThreadCount 1 }\nViewpoint { position 0 -2 1 }\n'+floor+'\nRobot { name "body" supervisor TRUE controller "<extern>" window "<none>" translation '+xyz+' rotation '+rot+' boundingObject Cylinder { height .03 radius .05 } physics Physics { density -1 mass .05 } }\n')
    with (out/'webots.log').open('w') as log:
     proc=subprocess.Popen([str(a.home/'webots'),'--batch','--minimize','--no-rendering','--mode=fast','--stdout','--stderr','--port='+str(wp),str((out/'world.wbt').resolve())],env=env,stdout=log,stderr=subprocess.STDOUT)
     try:
      until=time.monotonic()+30
      while 'Waiting for local or remote connection' not in (out/'webots.log').read_text():
       if proc.poll() is not None or time.monotonic()>until:raise RuntimeError('native readiness absent: '+str(out))
       time.sleep(.1)
      with (out/'controller.log').open('w') as clog:
       subprocess.run([str(a.home/'webots-controller'),'--protocol=tcp','--ip-address=127.0.0.1','--port='+str(wp),'--robot-name=body',str((a.out/'probe.py').resolve()),str((a.out/'protocol.json').resolve()),case,str(out.resolve())],env=env,stdout=clog,stderr=subprocess.STDOUT,check=True,timeout=45)
      assert proc.wait(timeout=10)==0
     finally:
      if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
    assert 'REDUCED_CONTACT_END ' in (out/'controller.log').read_text()
  finally:xvfb.terminate();xvfb.wait(timeout=10)
 (a.out/'sha256.json').write_text(json.dumps({str(f.relative_to(a.out)):digest(f) for f in sorted(a.out.rglob('*')) if f.is_file() and f.name!='sha256.json'},indent=2)+'\n')
 print('COMPLETE reduced contact interventions; not mission qualification')
if __name__=='__main__':main()
