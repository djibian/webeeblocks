#!/usr/bin/env python3
"""Fail-closed D1 real Webots owner=A-disabled foreign removal oracle."""
from pathlib import Path
import json,re,sys
root=Path(sys.argv[1])
def classify(log,code,require_foreign):
    assert code==0,("NATIVE_PROCESS_FAILURE",code)
    for token in ("H6_D1_CONTROLLER_READY","H6_D1_CONTROLLER_REMOVE_B",
                  "H6_D1_PLUGIN_INIT","H6_D1_REAL_BODY_DESTROY_START",
                  "H6_D1_REAL_BODY_DESTROY_BEFORE_ODE",
                  "H6_D1_REAL_BODY_DESTROY_AFTER_ODE",
                  "H6_D3_FINAL_CONTEXT_END count1=0 count2=0"):
        assert token in log,("SCENARIO_NOT_EXECUTED",token)
    hit=re.search(r"H6_D1_PLUGIN_INIT a=(\S+) b=(\S+) c=(\S+)",log)
    assert hit,"MISSING_BODY_PROVENANCE"
    a,b,c=hit.groups()
    assert len({a,b,c})==3 and all(x not in ("0x0","(nil)") for x in (a,b,c))
    sleep=re.findall(r"H6_D1_PLUGIN_SLEEP tick=(\d+) a=(\S+) enabled=(\d+) ab=(\d+) ac=(\d+) total=(\d+)",log)
    assert any(x[1]==a and x[2]=="0" and int(x[3])>=1 and int(x[4])>=1 for x in sleep),("NO_SIMULTANEOUS_AB_AC",sleep)
    scans=re.findall(r"H6_D1_FOREIGN_SCAN victim=(\S+) joint=(\S+) owner=(\S+) ownerEnabled=(\d+) b0=(\S+) b1=(\S+) destroy=(\d+)",log)
    foreign=[s for s in scans if s[0]==b and s[2]==a and s[3]=="0" and b in (s[4],s[5]) and s[6]=="1"]
    ac=[s for s in scans if s[0]==b and a in (s[4],s[5]) and c in (s[4],s[5]) and s[6]=="0"]
    witness=re.search(r"H6_D1_FIXTURE_DISABLE victim=(\S+) other=(\S+) before=(\d+) after=(\d+) joint=(\S+)",log)
    if require_foreign:
        assert witness and witness.group(1)==b and witness.group(2)==a and witness.group(4)=="0",("ASLEEP_INTERVENTION_ABSENT",witness.groups() if witness else None)
        assert foreign,("MISSING_OWNER_A_DISABLED_AB",scans)
        assert ac,("MISSING_INDEPENDENT_AC_AT_DELETION",scans)
        assert len({s[1] for s in foreign})==len(foreign),("DUPLICATE_AB_DESTRUCTION",foreign)
        bstep=[x for x in sleep if int(x[0])>=4 and int(x[4])>=1]
        assert bstep,("AC_NOT_PRESERVED_AFTER_B_DELETION",sleep)
        i=log.index("H6_D1_REAL_BODY_DESTROY_START body="+b)
        j=log.index("H6_D1_REAL_BODY_DESTROY_BEFORE_ODE body="+b)
        assert i<j and all(log.find("H6_D1_FOREIGN_SCAN victim="+b+" joint="+s[1],i,j)!=-1 for s in foreign),("WRONG_CLEANUP_ORDER",foreign)
        assert re.search(r"H6_D1_REAL_BODY_DESTROY_BEFORE_ODE body="+re.escape(b)+r" joints=0",log),"ATTACHED_B_CONTACTS_BEFORE_ODE"
    return {"A":a,"B":b,"C":c,"foreign_owner_A_disabled_destroyed":len(foreign),
            "independent_AC_preserved_at_deletion":len(ac),
            "post_remove_AC_steps":[int(x[0]) for x in sleep if int(x[0])>=4 and int(x[4])>=1],
            "fixture_intervention":witness.groups() if witness else None}
# All candidate scene arrangements are declared before running; no passing
# geometry is silently selected and all failed/negative paths remain in artifact.
scenes=("left_pair","mirrored","vertical")
result={}
passing=[]
for scene in scenes:
    result[scene]={}
    for arm in ("control","forced"):
        p=root/scene/arm
        log=(p/"webots.log").read_text(errors="replace")
        rc=int((p/"exit.txt").read_text())
        assert rc==0,("NATIVE_PROCESS_CRASH",scene,arm,rc)
        try:
            result[scene][arm]={"status":"PASS",**classify(log,rc,arm=="forced")}
            if arm=="forced": passing.append(scene)
        except AssertionError as error:
            result[scene][arm]={"status":"UNPROVEN","reason":str(error)[:1200],
                                "exit":rc}
assert passing,("NO_DISCRIMINATING_NATIVE_OWNER_A_SCENE",result)
for scene in passing:
    log=(root/scene/"forced"/"webots.log").read_text(errors="replace")
    for damaged in (log.replace("H6_D1_FIXTURE_DISABLE","X"),
                    log.replace("H6_D1_FOREIGN_SCAN","X")):
        try: classify(damaged,0,True)
        except AssertionError: pass
        else: raise AssertionError("NON_DISCRIMINATING_NEGATIVE_ORACLE")
report={"status":"PASS","candidate":"8d8d644b2bc6d5821572d87d474e59f533ec3260",
  "scope":"real Webots dBodyDestroy(B), registered AB owned by disabled A, AC retained",
  "intervention":"dBodyDisable on attached foreign body at B destructor entry (test only)",
  "predeclared_scenes":scenes,"discriminating_scenes":passing,"results":result}
(root/"qualification-asleep.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("H6_D1_NATIVE_FOREIGN_ASLEEP_OWNER_PASS",json.dumps({"passing":passing,"results":result},sort_keys=True))
