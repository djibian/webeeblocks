#!/usr/bin/env python3
"""Requalify already executed real native Webots D3 evidence; NO native rebuild.

The original oracle selected the *first* reset, on hinge child. Select the
target body by native first-solver identity and require same-body registry
removal and reset(id). All physical postconditions remain mandatory.
"""
from pathlib import Path
import json,re,sys
root=Path(sys.argv[1])
def qualify(log,exitcode):
    assert exitcode==0,("NATIVE_PROCESS_FAILURE",exitcode)
    for token in ("H6_D3_TRUE_CONTROLLER_BEGIN","H6_D3_TRUE_BEFORE_SAVE",
                  "H6_D3_TRUE_REQUEST_LOAD","H6_D3_ACTUAL_RESET_ID_BEGIN",
                  "H6_D3_ACTUAL_RESET_ID_END","H6_D3_FIRST_SOLVER_BEFORE",
                  "H6_D3_FIRST_SOLVER_AFTER","H6_D3_FIRST_SOLVER_RETIRED",
                  "H6_D3_FINAL_CONTEXT_END count1=0 count2=0"):
        assert token in log,("MISSING_PROOF",token)
    first=re.search(r"H6_D3_FIRST_SOLVER_BEFORE body=(\S+) contacts=(\d+) permanent=(\d+)",log)
    after=re.search(r"H6_D3_FIRST_SOLVER_AFTER body=(\S+) contacts=(\d+) permanent=(\d+)",log)
    assert first and after,"NO_NATIVE_FIRST_SOLVER"
    body=first.group(1)
    assert body==after.group(1),("MISMATCHED_SOLVER_BODY",first.groups(),after.groups())
    checks=re.findall(r"H6_D3_REGISTRY_CHECK body=(\S+) before1=(\d+) before2=(\d+) after1=(\d+) after2=(\d+) beforeAttached=(\d+) ownedRemoved=(\d+) remainingContacts=(\d+)",log)
    matches=[tuple(map(int,c[1:])) for c in checks if c[0]==body and int(c[6])>=4]
    assert matches,("NO_TARGET_REGISTRY_DELETION",body,checks)
    selected=matches[-1]
    b1,b2,a1,a2,attached,removed,remaining=selected
    assert b1+b2>=4 and a1==0 and a2==0 and attached>=5 and removed>=4 and remaining==0,("BAD_TARGET_REGISTRY",selected)
    begins=re.findall(r"H6_D3_ACTUAL_RESET_ID_BEGIN solid=(\S+) body=(\S+) contacts=(\d+)",log)
    ends=re.findall(r"H6_D3_ACTUAL_RESET_ID_END solid=(\S+) body=(\S+) contacts=(\d+)",log)
    assert any(c[1]==body and int(c[2])>=5 for c in begins),("TARGET_RESET_NOT_CALLED",begins)
    assert any(c[1]==body and int(c[2])>=1 for c in ends),("TARGET_RESET_NOT_FINISHED",ends)
    destroyed=re.findall(r"H6_D3_RESET_JOINT joint=(\S+) owned=(\d+) in1=(\d+) in2=(\d+)",log)
    assert len(destroyed)>=4 and len({x[0] for x in destroyed})==len(destroyed),("DUPLICATE_RESET_POINTER_FREE",destroyed)
    assert all(x[1]=="1" and int(x[2])+int(x[3])==1 for x in destroyed),("NONOWNED_CONTACT_DESTRUCTION",destroyed)
    assert int(first.group(2))==0 and int(first.group(3))>=1,("OLD_JOINT_AT_FIRST_SOLVER",first.groups())
    assert int(after.group(3))>=1 and int(after.group(2))>=1,("NO_PHYSICAL_SOLVER_RESULT",after.groups())
    start=log.index("H6_D3_ACTUAL_RESET_ID_END")
    i=log.index("H6_D3_FIRST_SOLVER_BEFORE")
    j=log.index("H6_D3_FIRST_SOLVER_AFTER")
    k=log.index("H6_D3_FIRST_SOLVER_RETIRED")
    teardown=log.index("H6_D3_FINAL_CONTEXT_END")
    assert start<i<j<k<teardown,("WRONG_EVENT_ORDER",start,i,j,k,teardown)
    assert "H6_D3_RETIRE buffer=" in log[j:teardown],"MISSING_RETIRE_AFTER_SOLVER"
    return {"body":body,"registries_before":[b1,b2],"registries_after":[a1,a2],
            "removed_owned":removed,"attached_pre_reset":attached,"remaining_contacts":remaining,
            "first_solver_before":{"contacts":int(first.group(2)),"permanent":int(first.group(3))},
            "first_solver_after":{"contacts":int(after.group(2)),"permanent":int(after.group(3))},
            "child_resets_seen":sum(c[1]!=body for c in begins),
            "controller_complete_observed":"H6_D3_TRUE_CONTROLLER_COMPLETE" in log}
results={}
for arm in ("0","1"):
    p=root/("arm-"+arm)
    s=(p/"webots.log").read_text(errors="replace")
    code=int((p/"exit.txt").read_text())
    results[arm]=qualify(s,code)
    for corrupt in (s.replace("H6_D3_FIRST_SOLVER_AFTER","X"),
                    s.replace("H6_D3_REGISTRY_CHECK body="+results[arm]["body"],
                              "H6_D3_REGISTRY_CHECK body=X"),
                    s.replace("H6_D3_FIRST_SOLVER_RETIRED","X")):
        try:qualify(corrupt,code)
        except AssertionError:pass
        else:raise AssertionError("NEGATIVE_ORACLE_FAILED_TO_REJECT")
report={"status":"PASS","native_run_id":41196404220,"native_artifact_id":13041450574,
        "native_candidate":"8d8d644b2bc6d5821572d87d474e59f533ec3260",
        "scope":"actual native reset(id), target registry cleanup, next real solver, surviving hinge",
        "results":results}
out=Path(sys.argv[2]);out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("H6_D3_REPLAY_AUTHENTICATED_NATIVE_POSTLOAD_PASS",json.dumps(results,sort_keys=True))
