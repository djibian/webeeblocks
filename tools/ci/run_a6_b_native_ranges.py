#!/usr/bin/env python3
"""A6-B six-world genuine R2025a ray probe. NO motors, pupils, or GO."""
import argparse,hashlib,json,math,os,re,signal,subprocess,time
import run_classroom_count_h_rear_range as original
ROOT=original.ROOT
OUT=ROOT/"ci-artifacts/a6-b-native-range"
FAMILY={"matched":"matched-tail","sampling":"sampling-holdout"}
TOKEN="A6_B_NATIVE_RANGE_PASS"
# Exact private scene positions, separately checked by C against native Boxes.
EXPECTED_X={"matched":{1:(.36,),2:(-.85,.36),3:(-.85,-.31,.36)},
            "sampling":{1:(.48,),2:(-.80,.48),3:(-.80,-.16,.48)}}
FIXED_X=(-.85,-.31,0.,.85,1.48)
ROW=re.compile(r"A6_B_NATIVE_RAY family=(\d) n=(\d) slot=(\d+) kind=(\d) "
               r"gate=(\d+) offset=(-?\d) x=(-?[0-9.]+) up=([0-9.]+) "
               r"front=([0-9.]+) contact=(\d+)")
def compose(family,n):
 if family not in FAMILY or type(n) is not int or n not in (1,2,3):
  raise ValueError("invalid native B fixture")
 old=(ROOT/f"worlds/scenes/count-h-{n}-v1.wbo").read_text().rstrip()+"\n"
 new=(ROOT/f"tools/ci/fixtures/a6-b/count-h-{n}-{FAMILY[family]}-private.wbo").read_text().rstrip()+"\n"
 source=original.compose(n)
 if not source.endswith(old):raise ValueError("old native scene not exact suffix")
 source=source[:-len(old)]+new
 old_ctrl='controller "progression_count_h_range_probe"'
 if source.count(old_ctrl)!=1 or source.count("DEF WEBEEBLOCKS_COUNT_")!=1:
  raise ValueError("ambiguous controller/physical scene")
 return source.replace(old_ctrl,'controller "progression_count_h_b_probe"')+"# A6_B_NATIVE_CI_ONLY\n"
def validate(text,family,n):
 count=3*n+5;fid=0 if family=="matched" else 1
 result=re.search(r"A6_B_NATIVE_RANGE_PASS family=(\d) n=(\d) samples=(\d+) "
                  r"physical_h=true motor=false pupil=false",text)
 rows=list(ROW.finditer(text))
 if (text.count(TOKEN)!=1 or "A6_B_NATIVE_FATAL" in text or not result or
     tuple(map(int,result.groups()))!=(fid,n,count) or len(rows)!=count):
  raise AssertionError("physical native evidence not complete")
 data=[]
 for slot,row in enumerate(rows):
  i=list(map(int,row.group(1,2,3,4,5,6)))
  x,u,f,contact=map(float,row.group(7,8,9,10))
  if i[:3]!=[fid,n,slot] or contact!=0 or not all(
      math.isfinite(v) for v in (x,u,f)) or not 0<=u<=2.001 or not 0<=f<=2.001:
   raise AssertionError("native ray identity/range/contact invalid")
  if slot<3*n:
   if i[3:]!=[1,slot//3,slot%3-1] or (slot%3==1 and u>.55):
    raise AssertionError("physical H center/ray unavailable")
   if slot%3!=1 and u<1.50:
    raise AssertionError("off-center H falsely detected in native ray")
   expected_x=EXPECTED_X[family][n][slot//3]+.04*(slot%3-1)
  else:
   if i[3:]!=[0,n+slot-3*n,-1]:
    raise AssertionError("wrong physical checkpoint")
   expected_x=FIXED_X[slot-3*n]
  # The clearance at +/-40mm around a 70mm BAR is only 5mm.
  # A 35mm position error would invalidate the aliasing experiment.
  tolerance=.003 if slot<3*n else .035
  if abs(x-expected_x)>tolerance:
   raise AssertionError("native ray sampled at wrong physical x coordinate")
  data.append({"x":x,"up_m":u,"front_m":f})
 return {"family":family,"count":n,"real_webots":True,"motor":False,
         "pupil":False,"samples":data}
def run(family,n):
 world_data=compose(family,n)
 out=OUT/f"{family}-n{n}";out.mkdir(parents=True,exist_ok=True)
 w=ROOT/f"worlds/ci_classroom_a6_b_{family}_{n}.wbt"
 project=ROOT/f"worlds/.ci_classroom_a6_b_{family}_{n}.wbproj"
 logfile=out/"webots.log"
 if w.exists() or project.exists():raise FileExistsError("refusing world overwrite")
 proc=None
 try:
  w.write_text(world_data);project.write_text(original.PROJECT_TEXT)
  env=dict(os.environ);env["LIBGL_ALWAYS_SOFTWARE"]="true"
  env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
  with logfile.open("w") as output:
   proc=subprocess.Popen(["timeout","-k","5s","95s","xvfb-run","-a",
     "webots","--stdout","--stderr","--batch","--mode=fast",str(w)],
     cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
   until=time.monotonic()+85
   while time.monotonic()<until:
    output.flush();raw=logfile.read_text(errors="replace")
    if TOKEN in raw or "A6_B_NATIVE_FATAL" in raw or proc.poll() is not None:break
    time.sleep(.25)
 finally:
  if proc is not None and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=8)
   except subprocess.TimeoutExpired:
    os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=8)
  if w.exists():
   if w.read_text()!=world_data:raise ValueError("world mutated; refuse cleanup")
   w.unlink()
  if project.exists():
   if project.read_text()!=original.PROJECT_TEXT:raise ValueError("project mutated")
   project.unlink()
 info=validate(logfile.read_text(errors="replace"),family,n)
 info["sha256"]=hashlib.sha256(world_data.encode()).hexdigest()
 (out/"summary.json").write_text(json.dumps(info,indent=2)+"\n")
 print(f"A6_B_NATIVE_RAYS_PROVEN family={family} count={n} "
       f"samples={len(info['samples'])} motor=false",flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--family",required=True,choices=tuple(FAMILY))
 p.add_argument("--count",required=True,type=int,choices=(1,2,3))
 a=p.parse_args();run(a.family,a.count)
