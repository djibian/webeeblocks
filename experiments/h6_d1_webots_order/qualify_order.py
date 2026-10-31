#!/usr/bin/env python3
"""Strict native D1 owner=A-asleep precondition and first-solver qualification.
All negative mutations apply only to copied log STRINGS, not physical runs.
"""
from pathlib import Path
import re,json,sys
root=Path(sys.argv[1])
def classify(log,rc,forced):
  assert rc==0,("NATIVE_FAILURE",rc)
  required=("H6_D1_CONTROLLER_READY","H6_D1_CONTROLLER_REMOVE_B",
    "H6_D1_PLUGIN_INIT","H6_D1_REAL_BODY_DESTROY_START",
    "H6_D1_REAL_BODY_DESTROY_BEFORE_ODE","H6_D1_REAL_BODY_DESTROY_AFTER_ODE",
    "H6_D3_FINAL_CONTEXT_END count1=0 count2=0")
  for token in required:assert token in log,("SCENARIO_NOT_EXERCISED",token)
  ids=re.search(r"H6_D1_PLUGIN_INIT a=(\S+) b=(\S+) c=(\S+)",log)
  assert ids, "MISSING_BODY_IDS"
  a,b,c=ids.groups()
  assert len({a,b,c})==3 and all(x not in ("(nil)","0x0") for x in (a,b,c)), "NON_DISTINCT_BODIES"
  create=re.findall(r"H6_D1_CREATE t=(\S+) o1=(\S+) o2=(\S+) b1=(\S+) b2=(\S+) owner=(\S+) joint=(\S+) buffer=(\d+)",log)
  assert create,"NO_NORMAL_WEBOTS_CONTACT_CREATION"
  ab=[x for x in create if x[3]==a and x[4]==b and x[5]==a]
  assert ab,("NO_O1_A_CONTACT_OWNER_A_AB",len(create))
  scans=re.findall(r"H6_D1_FOREIGN_SCAN victim=(\S+) joint=(\S+) owner=(\S+) ownerEnabled=(\d+) b0=(\S+) b1=(\S+) destroy=(\d+)",log)
  fromb=[x for x in scans if x[0]==b]
  foreign=[x for x in fromb if x[2]==a and x[3]=="0" and b in (x[4],x[5]) and x[6]=="1"]
  assert foreign,("NO_OWNER_A_ASLEEP_D1",fromb)
  created={x[6] for x in ab}
  assert all(x[1] in created for x in foreign), ("NOT_SAME_CREATED_AB_JOINT",foreign)
  assert len(set(x[1] for x in foreign))==len(foreign), "DUPLICATE_AB_SCAN"
  ac=[x for x in fromb if a in (x[4],x[5]) and c in (x[4],x[5]) and x[6]=="0"]
  assert ac,("NO_LIVE_AC_AT_B_REMOVAL",fromb)
  begin=log.index("H6_D1_REAL_BODY_DESTROY_START body="+b)
  before=log.index("H6_D1_REAL_BODY_DESTROY_BEFORE_ODE body="+b)
  after=log.index("H6_D1_REAL_BODY_DESTROY_AFTER_ODE",before)
  assert begin<before<after,"WRONG_NATIVE_DESTRUCTION_SEQUENCE"
  assert all(begin<log.index("H6_D1_FOREIGN_SCAN victim="+b+" joint="+x[1],begin)<before for x in foreign), "LATE_JOINT_REAP"
  assert re.search(r"H6_D1_REAL_BODY_DESTROY_BEFORE_ODE body="+re.escape(b)+r" joints=0",log[begin:after]),"BODY_STILL_ATTACHED_BEFORE_ODE"
  post=re.search(r"H6_D1_REGISTRY_AFTER victim="+re.escape(b)+r" count1=(\d+) count2=(\d+)",log[begin:before])
  assert post and int(post.group(1))+int(post.group(2))>=len(ac),"REGISTRY_DROPPED_AC"
  assert all(x[1] not in [s[1] for s in ac] for x in foreign),"AB_AC_OVERLAP"
  if forced:
    forced_dis=re.findall(r"H6_D1_FIXTURE_DISABLE victim=(\S+) other=(\S+) before=(\d+) after=(\d+) joint=(\S+)",log[begin:before])
    assert any(x[0]==b and x[1]==a and x[3]=="0" for x in forced_dis),"FORCED_SLEEP_NOT_EXERCISED"
  pre=re.search(r"H6_D1_FIRST_SOLVER_BEFORE tick=4 enabled_before=(\d+) ac=(\d+) forcedWake=(\d+)",log[after:])
  aft=re.search(r"H6_D1_FIRST_SOLVER_AFTER tick=4 ac=(\d+) forcedWake=(\d+) forceL1=([\d.eE+-]+) enabled=(\d+)",log[after:])
  assert pre and aft, "NO_FIRST_POST_REMOVE_SOLVER_OBSERVATION"
  assert pre.group(1)=="0" and int(pre.group(2))>=1 and pre.group(3)=="1","NO_A_C_AT_A_WAKE"
  assert int(aft.group(1))==int(pre.group(2)) and aft.group(2)=="1","SOLVER_FEEDBACK_MISSING"
  f=float(aft.group(3))
  assert f>1e-12,("NO_PHYSICAL_AC_CONTRIBUTION",f)
  return {"ids":{"A":a,"B":b,"C":c},"normalABOwnedA":len(ab),
    "foreignABReaped":len(foreign),"ACPreserved":len(ac),
    "registryAfter":tuple(map(int,post.groups())),
    "firstSolverAC":int(pre.group(2)),"firstSolverForceL1":f}
result={}
for arm in ("control","forced"):
  p=root/arm
  log=(p/"webots.log").read_text(errors="replace")
  rc=int((p/"exit.txt").read_text())
  try:
    result[arm]={"status":"PASS",**classify(log,rc,arm=="forced")}
  except AssertionError as e:
    result[arm]={"status":"UNPROVEN","reason":str(e)[:1200],"exit":rc}
    if arm=="forced":
      (root/"qualification.json").write_text(json.dumps({"status":"UNPROVEN","result":result},indent=2)+"\n")
      raise
log=(root/"forced"/"webots.log").read_text(errors="replace")
mutations={
 "bad_owner":re.sub(r"(H6_D1_FOREIGN_SCAN victim=\S+ joint=\S+ owner=)\S+( ownerEnabled=0)",r"\g<1>(nil)\2",log),
 "enabled_owner":log.replace(" ownerEnabled=0"," ownerEnabled=1"),
 "absent_AC":re.sub(r"^.*H6_D1_FOREIGN_SCAN .*?(?=^|$)",lambda m:"" if "destroy=0" in m.group(0) else m.group(0),log,flags=re.M),
 "no_creation":log.replace("H6_D1_CREATE","NOT_CREATED"),
 "no_B_destroy":log.replace("H6_D1_REAL_BODY_DESTROY_AFTER_ODE","MISSING_AFTER_ODE"),
 "wrong_registry":log.replace("H6_D1_REGISTRY_AFTER","UNVERIFIED_REGISTRY"),
 "no_solver":log.replace("H6_D1_FIRST_SOLVER_AFTER","MISSING_FIRST_SOLVER"),
 "no_force":re.sub(r"(forceL1=)[\d.eE+-]+",r"\g<1>0",log)
}
for name,damage in mutations.items():
  try:classify(damage,0,True)
  except AssertionError:pass
  else:raise AssertionError(("NEGATIVE_MUTATION_NOT_REJECTED",name))
report={"status":"PASS","candidate":"8d8d644b2bc6d5821572d87d474e59f533ec3260",
        "nativeArms":result,"negativeMutations":list(mutations)}
(root/"qualification.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("H6_D1_FOREIGN_ASLEEP_CLOSED",json.dumps(report,sort_keys=True))
