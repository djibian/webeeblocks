#!/usr/bin/env python3
"""Posthoc audit of an IMMUTABLE RED run: physics data, not rerunning/relabeling CI.

Consumes eight native Webots processes from 41086041857, evidence SHA pinned.
The original run is RED owing to lossy stdout-only Supervisor terminal marker.
Requires stronger independent terminal evidence: exit=0, 44/44 pre+post ODE
step observations and the plugin's own cleanup/termination marker.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import sys

root=Path(sys.argv[1])
PIN="c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
HEAD="22490571f6df9e5258000f5d8e6ddb191a738ba3"
def check(v,msg):
    if not v: raise AssertionError("H6_NATIVE_POSTHOC_REFUSED "+msg)
def kv(s): return dict(re.findall(r"([a-z_]+)=([^\s]+)",s))
def omega(s):
    d=kv(s)
    return math.sqrt(sum(float(d["w"+axis])**2 for axis in ("x","y","z")))
def exactly(lines,token,tick):
    found=[x for x in lines if token+" tick="+str(tick)+" " in x]
    check(len(found)==1,token+" "+str(tick)+" multiplicity="+str(len(found)))
    return found[0]

original=(root/"SHA256SUMS.txt").read_text().splitlines()
seen=set()
for line in original:
    sha,rel=line.split("  ",1)
    check(rel.startswith("evidence/native/"),"bad manifest path")
    path=rel.removeprefix("evidence/native/")
    check(path not in seen,"duplicate manifest")
    seen.add(path)
    check(hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,path+" altered")
actual={str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
check(actual==seen|{"SHA256SUMS.txt"},"missing/unlisted files")
check((root/"experiment-head.txt").read_text().strip()==HEAD,"experiment SHA")
check((root/"actual-head.txt").read_text().strip()==HEAD,"actual SHA")
check((root/"actual-webots-pin.txt").read_text().strip()==PIN,"native source pin")
patch=(root/"native-rg.patch").read_text()
changed=set(re.findall(r"^diff --git a/(\S+) b/",patch,re.M))
check(changed=={
 "src/webots/ode/WbOdeContext.cpp",
 "src/webots/ode/WbOdeContext.hpp",
 "src/webots/nodes/WbSolid.cpp",
 "src/webots/engine/WbSimulationCluster.cpp"}, "source patch scope")
check("detachResetBodyContacts" in patch and "dJointGroupEmpty" in patch,"not R+G")
plugin=Path("experiments/h6/g_window/plugins/physics/h6_g_window/h6_g_window.c").read_text()
check("dJointAttach(" not in plugin and "dJointDestroy(" not in plugin,"plugin mutated ODE")
summary={"archive_origin_run":41086041857,"original_run_status":"RED (stdout terminal marker missing)",
         "head":HEAD,"webots":PIN,"hashed_files_verified":len(seen),
         "terminal_oracle":"8x exit=0 AND 44 complete pre/post native physics frames AND plugin_cleanup",
         "arms":{},"contrasts":{},"findings":[]}
raw={}
for path in ("global","node"):
    for arm in ("A","R","G","RG"):
        name=path+"-"+arm
        folder=root/name
        trace=(folder/"native.log").read_text().splitlines()
        webots=(folder/"webots.log").read_text().splitlines()
        check(int((folder/"exit_code.txt").read_text())==0,name+" nonzero exit")
        flag=(folder/"flags.txt").read_text()
        check(f"g={int('G' in arm)} r={int('R' in arm)} path={path}" in flag,name+" flags")
        check(sum("event=plugin_init " in z for z in trace)==1,name+" plugin init")
        check(sum("event=plugin_cleanup ticks=44 reset_seen=1" in z for z in trace)==1,
              name+" incomplete plugin")
        pres=[z for z in trace if "event=pre tick=" in z]
        posts=[z for z in trace if "event=post tick=" in z]
        check(len(pres)==44 and len(posts)==44,name+" incomplete 44 steps")
        check([int(kv(z)["tick"]) for z in pres]==list(range(1,45)),name+" pre order")
        check([int(kv(z)["tick"]) for z in posts]==list(range(1,45)),name+" post order")
        check(any("controller=about_to_reset path="+path in z for z in webots),name+" no Supervisor preflight")
        check(any("controller=requested path="+path in z for z in webots),name+" no Supervisor reset")
        p36=kv(exactly(trace,"event=pre",36))
        p37=kv(exactly(trace,"event=pre",37))
        p38=kv(exactly(trace,"event=pre",38))
        check(int(p36["contacts"])>=1,name+" no old physical contacts")
        check(p37["reset"]=="1" and float(p37["z"])>.7,name+" moved/reset body not observed")
        for z in ("vx","vy","vz","wx","wy","wz"):
            check(abs(float(p37[z]))<1e-9,name+" nonzero RESET velocity "+z)
        check(int(p37["enabled"]) == (1 if path=="global" else 0),name+" wrong Supervisor path")
        check(p38["enabled"]=="1",name+" target did not wake")
        cleanup=[kv(z) for z in webots if "H6_NATIVE_G event=retire " in z]
        check(len(cleanup)>=1 and all(int(z["count"])>0 for z in cleanup),name+" no old group")
        check(all(int(z["g"])==int("G" in arm) for z in cleanup),name+" G flag mismatch")
        rtrace=[kv(z) for z in webots if "H6_NATIVE_R event=detach " in z]
        removed=sum(int(z["removed"]) for z in rtrace)
        check(removed==(4 if "R" in arm else 0),name+" R detach count "+str(removed))
        check(int(p37["contacts"])==(0 if "R" in arm else 4),name+" wrong pre-solver contacts")
        check(len([z for z in trace if "event=reset_boundary tick=37 " in z])==1,name+" RESET boundary")
        testpost=37 if path=="global" else 38
        post=exactly(trace,"event=post",testpost)
        velocity=omega(post)
        raw[name]=dict(p37=p37,omega=velocity)
        summary["arms"][name]={"omega_rad_s":velocity,
          "contacts_at_first_post_reset_pre_solver":int(p37["contacts"]),
          "R_removed":removed,"retired_group_events":len(cleanup),
          "disabled_owner_retired_group_events":sum(x["owner_enabled"]=="0" for x in cleanup),
          "terminates_normally":True}

for path in ("global","node"):
    refer=raw[path+"-A"]["p37"]
    for arm in ("R","G","RG"):
        cur=raw[path+"-"+arm]["p37"]
        for k in ("x","y","z","vx","vy","vz","wx","wy","wz"):
            check(abs(float(refer[k])-float(cur[k]))<1e-8,
                  path+"-"+arm+" different pre-RESET state: "+k)
    omegas={arm:raw[path+"-"+arm]["omega"] for arm in ("A","R","G","RG")}
    check(omegas["A"]>0.1,path+" no parasite in baseline")
    check(omegas["R"]<1e-9 and omegas["RG"]<1e-9,path+" native R ineffective")
    if path=="global":
        check(abs(omegas["A"]-omegas["G"])<1e-9,"G-only global falsely fixes")
    else:
        check(omegas["G"]<1e-9,"G-only node not fixed")
    summary["contrasts"][path]={"omega_rad_s":omegas,
          "pre_reset_state_equal":True,
          "native_R_suppresses":True,
          "G_only_suppresses":omegas["G"]<1e-9}
summary["findings"]=[
"Native source integrated R works in real Webots on two Supervisor paths; G alone fails global",
"R is attachment-selective: four old contacts removed before solve in R and RG",
"Global disabled-owner retired-group lifetime still unqualified beyond 44 steps",
"Foreign group-owner contact, articulation, mixed groups, Webots multithreading and long-run memory not yet qualified",
"Original execution 41086041857 remains RED; this only requalifies original immutable artifact"]
(root/"posthoc_native_rg_qualification.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print(json.dumps(summary,indent=2,sort_keys=True))
print("H6_NATIVE_RG_POSTHOC_PASS")
