#!/usr/bin/env python3
"""Fail-closed causal Webots R2025a wakeup qualification; independent from legacy H6 oracles."""
import json, pathlib, re, sys, math, hashlib
p=pathlib.Path(sys.argv[1]); e=p/"wake"; report={"scope":"pinned Webots R2025a, single thread, no RESET, real contacts, one binary A/G",
"cases":{}, "errors":[],"claim":"only first solver after forced wake; no universal safety inference"}
def die(msg): report["errors"].append(msg)
def lines(path): return path.read_text(errors="replace").splitlines()
def getdata(case,trial,arm):
 d=e/f"{case}-{trial}-{arm}"; raw=lines(d/"webots.log"); pl=lines(d/"plugin.log"); ctrl=lines(d/"controller.jsonl")
 assert "H6_WAKE_CONTROLLER_DONE" in ctrl
 rows=[json.loads(s) for s in ctrl if s.startswith("{")]
 assert len(rows)==12 and [r["frame"] for r in rows]==list(range(12))
 assert len([s for s in pl if s.startswith("H6_WAKE_DONE ")])==1
 sol={}
 for s in raw:
  if not s.startswith("H6_WAKE_SOLVE phase="): continue
  m=re.fullmatch(r"H6_WAKE_SOLVE phase=(pre|post) tick=(\d+) body=(\S+) enabled=(\d+) joints=(\d+) z=([+\-0-9.eE]+) vz=([+\-0-9.eE]+)",s)
  assert m,s
  sol[(int(m[2]),m[1])]={"body":m[3],"enabled":int(m[4]),"joints":int(m[5]),"z":float(m[6]),"vz":float(m[7])}
 sj={}
 for s in raw:
  if not s.startswith("H6_WAKE_SOLVE_JOINT "): continue
  m=re.fullmatch(r"H6_WAKE_SOLVE_JOINT phase=(pre|post) tick=(\d+) joint=(\S+) type=(\d+) b0=(\S+) b1=(\S+)",s)
  assert m,s
  sj.setdefault((int(m[2]),m[1]),[]).append({"ptr":m[3],"type":int(m[4]),"b0":m[5],"b1":m[6]})
 effects=[]
 for s in raw:
  if not s.startswith("H6_G_EFFECT "): continue
  m=re.fullmatch(r"H6_G_EFFECT retired=1 owner_disabled=1 before=(\d+) after=(\d+) arm=(A|G)",s)
  assert m,s
  effects.append((int(m[1]),int(m[2]),m[3]))
 retired=[]
 for s in raw:
  if not s.startswith("H6_WAKE_RETIRE_JOINT "): continue
  m=re.fullmatch(r"H6_WAKE_RETIRE_JOINT owner=(\S+) group=(\S+) joint=(\S+) b0=(\S+) b1=(\S+) enabled=(\d+)",s)
  assert m,s
  retired.append({"owner":m[1],"group":m[2],"ptr":m[3],"b0":m[4],"b1":m[5],"enabled":int(m[6])})
 actions=[s for s in pl if s.startswith("H6_WAKE_ACTION ")]
 assert len(sol)==24, (case,trial,arm,len(sol))
 assert all(math.isfinite(x["z"]) and math.isfinite(x["vz"]) for x in sol.values())
 return {"solver":sol,"joint":sj,"effects":effects,"retired":retired,"actions":actions,
         "controller":rows,"log_sha256":hashlib.sha256((d/"webots.log").read_bytes()).hexdigest()}
for case, trials in [("wake",3),("no_disable",1),("no_initial",1),("no_wake",1)]:
 for trial in range(1,trials+1):
  name=f"{case}-{trial}"
  try:
   a=getdata(case,trial,"A"); g=getdata(case,trial,"G")
   for key in a["solver"]:
    x,y=a["solver"][key],g["solver"][key]
    assert x["enabled"]==y["enabled"],(name,key,"activation mismatch")
   s2a=a["solver"][(2,"pre")];s2g=g["solver"][(2,"pre")]
   s3a=a["solver"][(3,"pre")];s3g=g["solver"][(3,"pre")]
   p3a=a["solver"][(3,"post")];p3g=g["solver"][(3,"post")]
   assert abs(s3a["z"]-s3g["z"])<1e-12 and abs(s3a["vz"]-s3g["vz"])<1e-12,(name,"unmatched pre-solver wake state")
   assert [i for i in a["actions"] if "op=disable" in i]==([] if case=="no_disable" else ["H6_WAKE_ACTION tick=2 op=disable"])
   assert [i for i in g["actions"] if "op=enable" in i]==([] if case in ("no_disable","no_wake") else ["H6_WAKE_ACTION tick=3 op=enable"])
   assert (s2a["joints"]>0)==(case!="no_initial"),(name,"initial real contact oracle",s2a)
   assert s2a["joints"]==s2g["joints"]
   extraA=sum(x-y for x,y,mode in a["effects"] if mode=="A")
   extraG=sum(x-y for x,y,mode in g["effects"] if mode=="G")
   assert extraA==0
   if case in ("wake","no_wake"):
    assert extraG>0 and any(x["enabled"]==0 and x["ptr"] for x in g["retired"]),(name,"G never destroyed qualifying J")
    ids={x["ptr"] for x in a["joint"].get((2,"pre"),[])}
    removed={x["ptr"] for x in a["retired"]}
    reused={x["ptr"] for x in a["joint"].get((3,"pre"),[])}
    assert ids&removed&reused,(name,"no evidenced same J retained for wake")
    assert s3a["joints"]>0 and s3g["joints"]==0,(name,"joint persistence wrong")
   else:
    assert extraG==0,(name,"negative control unexpectedly exercised G",extraG)
   dz=p3a["z"]-p3g["z"];dv=p3a["vz"]-p3g["vz"]
   item={"A_pre_wake":s3a,"G_pre_wake":s3g,"A_after_solver_before_new_collisions":p3a,
         "G_after_solver_before_new_collisions":p3g,"delta_post_solver_z_m":dz,
         "delta_post_solver_vz_m_s":dv,"G_contacts_destroyed":extraG,
         "A_retired_joint_ids":sorted({x["ptr"] for x in a["retired"]}),
         "A_pre_wake_joint_ids":sorted({x["ptr"] for x in a["joint"].get((3,"pre"),[])}),
         "G_pre_wake_joint_ids":sorted({x["ptr"] for x in g["joint"].get((3,"pre"),[])}),
         "log_sha256":{"A":a["log_sha256"],"G":g["log_sha256"]}}
   report["cases"][name]=item
   if case=="wake":
    if abs(dz)<1e-8 and abs(dv)<1e-8: die(name+": G removed old joint but no mechanical divergence on first solver")
   elif abs(dz)>1e-8 or abs(dv)>1e-8:
    die(name+": unexpected physical divergence in negative control")
  except (AssertionError,KeyError,ValueError,IndexError,FileNotFoundError) as ex:
   die(name+": "+str(ex))
report["verdict"]="PROVEN_NATIVE_WAKEUP_REGRESSION" if not report["errors"] else "UNPROVEN_OR_REFUTATION_REQUIRES_AUDIT"
(e/"qualification.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print(json.dumps(report,indent=2,sort_keys=True))
if report["errors"]: raise SystemExit("H6_WAKE_REFUSED: "+repr(report["errors"]))
