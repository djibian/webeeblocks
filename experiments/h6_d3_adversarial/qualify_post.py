#!/usr/bin/env python3
"""Fail-closed D3 oracle: native first solver, not lifecycle of the controller that called loadState."""
import json,re,sys
from pathlib import Path
root=Path(sys.argv[1])
def qualify(log,exitcode):
    assert exitcode==0,("NATIVE_PROCESS_FAILURE",exitcode)
    for token in ("H6_D3_TRUE_CONTROLLER_BEGIN","H6_D3_TRUE_BEFORE_SAVE",
                  "H6_D3_TRUE_REQUEST_LOAD","H6_D3_ACTUAL_RESET_ID_BEGIN",
                  "H6_D3_ACTUAL_RESET_ID_END","H6_D3_FIRST_SOLVER_BEFORE",
                  "H6_D3_FIRST_SOLVER_AFTER","H6_D3_FIRST_SOLVER_RETIRED",
                  "H6_D3_FINAL_CONTEXT_END count1=0 count2=0"):
        assert token in log,("MISSING_PROOF",token)
    match=re.search(r"H6_D3_REGISTRY_CHECK body=(\\S+) before1=(\\d+) before2=(\\d+) after1=(\\d+) after2=(\\d+) beforeAttached=(\\d+) ownedRemoved=(\\d+) remainingContacts=(\\d+)",log)
    assert match, "NO_REGISTRY_CHECK"
    body,b1,b2,a1,a2,attached,removed,remaining=match.groups()
    n=list(map(int,(b1,b2,a1,a2,attached,removed,remaining)))
    assert n[0]+n[1]>=4 and n[2]==0 and n[3]==0 and n[5]>=4 and n[6]==0,("BAD_REGISTER_OR_RESET",n)
    destroyed=re.findall(r"H6_D3_RESET_JOINT joint=(\\S+) owned=(\\d+) in1=(\\d+) in2=(\\d+)",log)
    assert len(destroyed)>=4 and len(set(x[0] for x in destroyed))==len(destroyed),("DUPLICATE_RESET_DESTRUCTION",destroyed)
    assert all(int(x[1])==1 and int(x[2])+int(x[3])==1 for x in destroyed),("NONOWNED_CONTACT_DESTRUCTION",destroyed)
    first=re.search(r"H6_D3_FIRST_SOLVER_BEFORE body=(\\S+) contacts=(\\d+) permanent=(\\d+)",log)
    after=re.search(r"H6_D3_FIRST_SOLVER_AFTER body=(\\S+) contacts=(\\d+) permanent=(\\d+)",log)
    assert first and after,"NO_NATIVE_FIRST_SOLVER"
    assert body==first.group(1)==after.group(1),("WRONG_BODY_SOLVER",body,first.group(1),after.group(1))
    assert int(first.group(2))==0,("STALE_CONTACT_AT_NEXT_SOLVER",first.groups())
    assert int(first.group(3))>=1 and int(after.group(3))>=1,("PERMANENT_JOINT_NOT_PRESERVED",first.groups(),after.groups())
    start=log.index("H6_D3_ACTUAL_RESET_ID_END")
    before=log.index("H6_D3_FIRST_SOLVER_BEFORE")
    end=log.index("H6_D3_FIRST_SOLVER_AFTER")
    retired=log.index("H6_D3_FIRST_SOLVER_RETIRED")
    teardown=log.index("H6_D3_FINAL_CONTEXT_END")
    assert start<before<end<retired<teardown,("ORDER_ERROR",start,before,end,retired,teardown)
    assert "H6_D3_RETIRE buffer=" in log[end:teardown], "NO_RETIRE_AFTER_SOLVER"
    return {"body":body,"registry_before":[n[0],n[1]],"registry_after":[n[2],n[3]],
            "owned_removed":n[5],"old_contacts_after_reset":n[6],
            "first_solver_before":{"contacts":int(first.group(2)),"permanent":int(first.group(3))},
            "first_solver_after":{"contacts":int(after.group(2)),"permanent":int(after.group(3))},
            "controller_complete_observed":"H6_D3_TRUE_CONTROLLER_COMPLETE" in log}
results={}
for arm in ("0","1"):
    p=root/("arm-"+arm)
    log=(p/"webots.log").read_text(errors="replace")
    rc=int((p/"exit.txt").read_text())
    results[arm]=qualify(log,rc)
    # Negative mutation: removing a physical postcondition MUST fail the strict oracle.
    for damaged in (log.replace("H6_D3_FIRST_SOLVER_AFTER","X",1),
                    log.replace("H6_D3_FIRST_SOLVER_RETIRED","X",1)):
        try: qualify(damaged,rc)
        except AssertionError: pass
        else: raise AssertionError("NEGATIVE_ORACLE_NOT_DISCRIMINANT")
report={"status":"PASS","source_candidate":"8d8d644b2bc6d5821572d87d474e59f533ec3260",
        "scope":"actual reset(id), registry removal, native first solver and persistent hinge",
        "results":results}
(root/"qualification-postload.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("H6_D3_INDEPENDENT_NATIVE_POST_LOAD_PASS",json.dumps(results,sort_keys=True))
