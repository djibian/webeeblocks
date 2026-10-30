#!/usr/bin/env python3
"""Cross-arm independent native Webots checks: old RESET parasites, wakeup identity."""
from pathlib import Path
import json,re,math,sys,hashlib
base=Path(sys.argv[1]);out={"arms":{},"contrasts":{},"errors":[]}
def need(x,msg):
 if not x:raise RuntimeError(msg)
def kv(s):return dict(re.findall(r"([a-z_]+)=([^\s]+)",s))
def line(ls,kind,tick):
 v=[kv(x) for x in ls if "event="+kind+" tick="+str(tick)+" " in x]
 need(len(v)==1,kind+str(tick));return v[0]
def velocity(d):return math.sqrt(sum(float(d["w"+z])**2 for z in ("x","y","z")))
for setting in ("canonical", "foreign-t1", "foreign-t2"):
 for path in ("global","node"):
  data={}
  for arm in ("A","R"):
   name=f"{setting}-{path}-{arm}"; p=base/"reset"/name
   try:
    n=(p/"native.log").read_text().splitlines()
    w=(p/"webots.log").read_text()
    need(int((p/"exit.txt").read_text())==0,name+" exit")
    need(len([x for x in n if "event=pre tick=" in x])==44,name+" 44 PRE")
    need(len([x for x in n if "event=post tick=" in x])==44,name+" 44 POST")
    need("H6_G_WINDOW event=plugin_cleanup ticks=44 reset_seen=1" in "\n".join(n),name+" terminal")
    need("controller=requested path="+path in w,name+" supervisor reset")
    p36,p37=line(n,"pre",36),line(n,"pre",37)
    post=line(n,"post",37 if path=="global" else 38)
    need(p37["reset"]=="1",name+" reset not observed")
    before=int(p37["contacts"])
    removed=sum(int(re.search(r'detached=(\d+)',s).group(1)) for s in w.splitlines() if "H6_STANDALONE_R detached=" in s)
    need(removed>=1 if arm=="R" else removed==0,name+" R count")
    need(before==0 if arm=="R" else before>=4,name+" stale target joints")
    v=velocity(post)
    data[arm]={"pre36":p36,"pre37":p37,"omega":v,"removed":removed}
    out["arms"][name]={"omega_rad_s":v,"removed":removed,"pre_solve_contacts":before,
      "native_sha256":hashlib.sha256((p/"native.log").read_bytes()).hexdigest()}
   except Exception as e:out["errors"].append(name+": "+str(e))
  if len(data)!=2: continue
  try:
   for key in ("x","y","z","vx","vy","vz","wx","wy","wz"):
    need(abs(float(data["A"]["pre36"][key])-float(data["R"]["pre36"][key]))<1e-8,
         setting+"/"+path+" R changed ordinary physics before RESET: "+key)
   need(data["R"]["omega"]<1e-7,setting+"/"+path+" native R did not suppress post-RESET angular speed")
   if setting=="canonical":
    need(data["A"]["omega"]>0.1,setting+"/"+path+" baseline not discriminant")
   if setting.startswith("foreign") and path=="global":
    need(data["A"]["omega"]>0.01,setting+"/"+path+" baseline not discriminant")
   out["contrasts"][setting+"/"+path]={"A_rad_s":data["A"]["omega"],
     "R_rad_s":data["R"]["omega"],"pre_RESET_physics_equal":True}
  except Exception as e:out["errors"].append(str(e))
for case in ("wake","no_disable"):
 for trial in (range(1,4) if case=="wake" else range(1,2)):
  d={}
  for arm in ("A","R"):
   name=f"{case}-{trial}-{arm}";p=base/"wake"/name
   try:
    log=(p/"webots.log").read_text().splitlines()
    plugin=(p/"plugin.log").read_text()
    ctrl=(p/"controller.jsonl").read_text()
    need(int((p/"exit.txt").read_text())==0,name+" exit")
    need(ctrl.count("H6_WAKE_CONTROLLER_DONE")==1,name+" controller complete")
    need("H6_WAKE_DONE ticks=12" in plugin,name+" plugin complete")
    def parse(tick,phase):
     v=[re.fullmatch(r"H6_WAKE_SOLVE phase=(pre|post) tick=(\d+) body=(\S+) enabled=(\d+) joints=(\d+) z=([+\-0-9.eE]+) vz=([+\-0-9.eE]+)",s) for s in log if s.startswith(f"H6_WAKE_SOLVE phase={phase} tick={tick} ")]
     need(len(v)==1 and v[0] is not None,name+" solver "+str(tick)+phase)
     m=v[0];return {"enabled":int(m[4]),"joints":int(m[5]),"z":float(m[6]),"vz":float(m[7])}
    p2=parse(2,"pre");p3=parse(3,"pre");post=parse(3,"post")
    joints2={re.search(r'joint=(\S+)',s).group(1) for s in log if s.startswith("H6_WAKE_SOLVE_JOINT phase=pre tick=2 ")}
    joints3={re.search(r'joint=(\S+)',s).group(1) for s in log if s.startswith("H6_WAKE_SOLVE_JOINT phase=pre tick=3 ")}
    if case=="wake":
     need(p2["joints"]==4 and p3["joints"]==4 and len(joints2&joints3)==4,name+" old wake contacts not conserved")
     need(p3["enabled"]==1,name+" body never woken")
    d[arm]={"p2":p2,"p3":p3,"post":post}
    out["arms"][name]={"pre_wake":p3,"post_wake":post,"kept_original_contact_joints":len(joints2&joints3)}
   except Exception as e:out["errors"].append(name+": "+str(e))
  if len(d)!=2:continue
  try:
   for stage in ("p2","p3","post"):
    for key in ("enabled","joints","z","vz"):
     a,b=d["A"][stage][key],d["R"][stage][key]
     need(abs(a-b)<1e-9,f"{case}-{trial} altered {stage}/{key}: {a} vs {b}")
   if case=="wake":
    need(abs(d["A"]["post"]["vz"]-0.248340218408736)<1e-8,
         "historical wake first solver reference changed")
   out["contrasts"][f"{case}-{trial}"]={"first_solver_delta_vz":d["A"]["post"]["vz"]-d["R"]["post"]["vz"],
      "first_solver_delta_z":d["A"]["post"]["z"]-d["R"]["post"]["z"],
      "four_original_joints_preserved":case=="wake"}
  except Exception as e:out["errors"].append(str(e))
out["scope"]="real pinned Webots R2025a, selective R only + standalone contact lifetime, wake without RESET"
out["status"]="PASS" if not out["errors"] and len(out["contrasts"])==10 else "RED"
(base/"qualification.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(json.dumps(out,indent=2,sort_keys=True))
if out["status"]!="PASS":raise SystemExit("H6_STANDALONE_REFUSED "+repr(out["errors"]))
print("H6_STANDALONE_NATIVE_PASS")
