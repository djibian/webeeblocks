#!/usr/bin/env python3
"""Adversarial Webots foreign-owner contact and 1-vs-2 thread post-RESET audit."""
from pathlib import Path
import json,math,re,sys
root=Path(sys.argv[1])
def need(c,m):
 if not c: raise RuntimeError("H6_ADVANCED_REFUSED "+m)
def fields(s):return dict(re.findall(r"([a-z_]+)=([^\s]+)",s))
def first(lines,kind,tick):
 f=[fields(s) for s in lines if f"event={kind} tick={tick} " in s]
 need(len(f)==1,f"{kind} tick {tick} not unique")
 return f[0]
def norm(s):return math.sqrt(sum(float(s["w"+v])**2 for v in "xyz"))
out={"scope":"real Webots R2025a foreign-owner dynamic contacts and configured ODE threads","arms":{},"contrasts":{},"errors":[]}
vals={}
for threads in (1,2):
 for path in ("global","node"):
  for arm in ("A","R","G","RG"):
   spec=f"t{threads}-{path}-{arm}";f=root/spec
   try:
    log=(f/"webots.log").read_text()
    trace=(f/"native.log").read_text().splitlines()
    need(int((f/"exit_code.txt").read_text())==0,spec+" process")
    need("controller=requested path="+path in log,spec+" Supervisor command")
    need(sum("event=plugin_cleanup ticks=44 reset_seen=1" in s for s in trace)==1,spec+" terminal")
    need(len([s for s in trace if "event=pre tick=" in s])==44,spec+" pre steps")
    need(len([s for s in trace if "event=post tick=" in s])==44,spec+" post steps")
    configs=[int(re.search(r'configured=(-?\d+)',s).group(1)) for s in log.splitlines() if "H6_NATIVE_THREAD_COUNT configured=" in s]
    need(len(configs)==1 and configs[0]==threads,spec+" unverified thread count "+str(configs))
    pre36=first(trace,"pre",36)
    pre37=first(trace,"pre",37)
    post=first(trace,"post",37 if path=="global" else 38)
    prior=[fields(s) for s in trace if "event=pre " in s and int(fields(s)["tick"])<=36]
    foreign_peak=max(int(z["foreign"]) for z in prior)
    # The requested foreign owner is different from this target body,
    # because native plugin observes contact-body index zero.
    need(foreign_peak>=1,spec+" no real foreign-first dynamic contact")
    removals=[int(re.search(r'removed=(\d+)',s).group(1)) for s in log.splitlines() if "H6_NATIVE_R event=detach" in s]
    removed=sum(removals)
    if "R" in arm:need(removed>=1,spec+" R never detached foreign-owned contact")
    else:need(removed==0,spec+" unexpected R")
    need(pre37["reset"]=="1" and float(pre37["z"])>.7,spec+" no real RESET")
    if "R" in arm:need(int(pre37["contacts"])==0,spec+" stale attached after native R")
    vals[spec]={"omega":norm(post),"pre36":pre36,"pre37":pre37,"removed":removed,"foreign_peak":foreign_peak}
    out["arms"][spec]={"omega_rad_s":norm(post),"R_removed":removed,"foreign_contact_peak":foreign_peak,
      "thread_count_observed":configs[0],"pre37_old_contacts":int(pre37["contacts"]),
      "complete_native_steps":44}
   except Exception as e:out["errors"].append(spec+": "+str(e))
for t in (1,2):
 for path in ("global","node"):
  keys=[f"t{t}-{path}-{a}" for a in ("A","R","G","RG")]
  if any(k not in vals for k in keys):continue
  a,r,g,rg=[vals[k] for k in keys]
  omega={label:vals[f"t{t}-{path}-{label}"]["omega"] for label in ("A","R","G","RG")}
  dist=lambda x,y:math.sqrt(sum((float(x.get(v,0))-float(y.get(v,0)))**2 for v in ("x","y","z","vx","vy","vz","wx","wy","wz")))
  # Contrast before any RESET, so G-before-RESET deviations cannot be hidden.
  before_g=dist(a["pre36"],g["pre36"])
  before_r=dist(a["pre36"],r["pre36"])
  need(before_r<1e-8,f"t{t}-{path}: R changed pre-RESET physics")
  out["contrasts"][f"t{t}-{path}"]={"omega_rad_s":omega,
    "G_no_RESET_pre36_state_difference":before_g,
    "R_no_RESET_pre36_state_difference":before_r,
    "R_physical_suppression_observed":omega["A"]>1e-5 and omega["R"]<1e-7 and omega["RG"]<1e-7}
out["limits"]="No long-running Webots arena-memory or genuine simultaneous RESET callback races established."
(root/"advanced_qualification.json").write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
print(json.dumps(out,sort_keys=True,indent=2))
need(not out["errors"]," ; ".join(out["errors"]))
need(len(out["contrasts"])==4,"missing 1/2-thread global/node contrasts")
print("H6_ADVANCED_NATIVE_OBSERVATION_PASS")
