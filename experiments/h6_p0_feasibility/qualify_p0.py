#!/usr/bin/env python3
"""H6 P0 native audit; strict fail-closed trace, no stale-pointer dereferences.
Synthetic mutants are diagnostic controls, NOT physical evidence.
"""
from collections import defaultdict
from pathlib import Path
import re
import sys

PATTERN = re.compile(r"^H6_P0 seq=(\d+) step=(\d+) tid=(\d+) event=([A-Za-z0-9_]+) arg=(\d+)$")

class Reject(Exception): pass

def need(ok, why):
    if not ok: raise Reject(why)

def parse(lines):
    events=[]
    for line_num,line in enumerate(lines,1):
        if "H6_P0" not in line: continue
        m=PATTERN.fullmatch(line.strip())
        need(m is not None, "MALFORMED_TRACE_LINE:%d"%line_num)
        seq,step,tid,ev,arg=m.groups()
        events.append(dict(seq=int(seq),step=int(step),tid=int(tid),ev=ev,arg=int(arg)))
    need(events,"NO_TRACE")
    events.sort(key=lambda x:x["seq"])
    need([x["seq"] for x in events]==list(range(1,len(events)+1)),
         "SEQUENCE_MISSING_DUPLICATE_OR_ZERO")
    return events

def check(events, expected_workers):
    need(expected_workers in (1,2),"BAD_WORKER_ARGUMENT")
    names=[e["ev"] for e in events]
    mandatory=(
        "configured_threads","step_enter","contact_create","P0_admission_installed",
        "P0_register","P0_public_enter","P0_public_denied","P0_class_engine",
        "P0_M_acquired","P0_M_released","plugin_callback_enter",
        "plugin_public_attempt","plugin_public_return","plugin_p0_live",
        "plugin_callback_exit","worker_task_enter","worker_task_exit",
        "main_b2_after","solver_return","P0_unregister","P0_internal_free",
        "plugin_standalone_before","plugin_standalone_destroyed",
        "plugin_group_before","plugin_group_noop","plugin_group_empty",
        "P0_registries_empty","P0_admission_removed","context_teardown",
        "world_destroy","context_teardown_after",
    )
    for event in mandatory: need(event in names,"MISSING_"+event)
    need(any(e["ev"]=="configured_threads" and e["arg"]==expected_workers
             for e in events),"WRONG_THREAD_CONFIGURATION")
    active=set(); callbacks=set(); worker_callbacks=set()
    m_held=set(); pub={}; attempted={}; denied=set()
    live={}; pending_free={}; recycled=0
    observed_creates=defaultdict(list); solver_return={}
    plugin_controls=defaultdict(list); engine_attempts=0; completed=0
    contention=0; internal=0; retire_steps=0; first_destroy={}
    teardown_seen=False
    for e in events:
        ev,tid,j,step,seq=e["ev"],e["tid"],e["arg"],e["step"],e["seq"]
        if ev=="contact_create":
            observed_creates[j].append(seq)
        elif ev=="P0_register":
            need(j not in live and j not in pending_free,"DUPLICATE_LIVE_INCARCATION")
            need(observed_creates[j] and observed_creates[j][-1]<seq,
                 "NO_REAL_CONTACT_CREATION_BEFORE_REGISTER")
            live[j]={"reg":seq, "create":observed_creates[j][-1]}
        elif ev=="P0_unregister":
            need(j in live,"UNREGISTER_NOT_LIVE")
            need(j not in pending_free,"ALREADY_DESTROYING")
            need(step==0 or (step in solver_return and solver_return[step]<seq)
                 or ("context_teardown" in names[:events.index(e)]),
                 "RETIRE_BEFORE_SOLVER_RETURN")
            pending_free[j]=dict(live.pop(j),unreg=seq,tid=tid)
            retire_steps+=1
        elif ev=="P0_internal_free":
            need(j in pending_free,"FREE_BEFORE_UNREGISTER_OR_DOUBLE_FREE")
            need(pending_free[j]["tid"]==tid and pending_free[j]["unreg"]<seq,
                 "INTERNAL_FREE_NOT_ATOMIC_WITH_RETIRE")
            need(tid in m_held,"INTERNAL_FREE_OUTSIDE_M")
            pending_free.pop(j); internal+=1; first_destroy[j]=seq
        elif ev in ("M_acquired","P0_M_acquired","P0_teardown_M_acquired","P0_retire_M_acquired","P0_cluster_dtor_M_acquired","P0_body_M_acquired","P0_reset_M_acquired"):
            need(tid not in m_held,"RECURSIVE_M")
            m_held.add(tid)
        elif ev in ("M_released","P0_M_released","P0_teardown_M_released","P0_retire_M_released","P0_cluster_dtor_M_released","P0_body_M_released","P0_reset_M_released"):
            need(tid in m_held,"RELEASE_WITHOUT_M")
            m_held.remove(tid)
        elif ev=="P0_M_contended":
            contention+=1
        elif ev=="P0_class_engine":
            need(tid in m_held and j in live,"CLASSIFIED_ENGINE_NOT_LIVE_OR_NO_M")
        elif ev=="P0_class_plugin":
            need(tid in m_held and j not in live,
                 "FALSE_CLASS_PLUGIN_OR_WITHOUT_M")
        elif ev=="worker_task_enter":
            need(tid not in active,"DOUBLE_WORKER_ENTER")
            active.add(tid)
        elif ev=="worker_task_exit":
            need(tid in active,"WORKER_EXIT_WITHOUT_ENTER")
            active.remove(tid)
        elif ev=="plugin_callback_enter":
            need(tid in active and tid not in callbacks,
                 "PLUGIN_CALLBACK_NOT_ON_REAL_WORKER")
            callbacks.add(tid);worker_callbacks.add(tid)
        elif ev=="plugin_callback_exit":
            need(tid in callbacks,"CALLBACK_EXIT_WITHOUT_ENTER")
            callbacks.remove(tid)
        elif ev=="plugin_public_attempt":
            need(tid in callbacks and j in live,"PUBLIC_ATTEMPT_NOT_LIVE_WORKER")
            need(tid not in attempted,"OVERLAPPING_PLUGIN_ATTEMPT")
            attempted[tid]=j
            engine_attempts+=1
        elif ev=="P0_public_enter":
            need(tid not in pub,"REENTRANT_PUBLIC_DESTROY")
            pub[tid]={"joint":j, "enter":seq,"class":None}
        elif ev in ("P0_public_allowed","P0_public_denied"):
            need(tid in pub and pub[tid]["joint"]==j,"DECISION_MISSING_ADMISSION")
            if ev=="P0_public_denied":
                need(j in live,"P0_DENIED_NON_ENGINE_JOINT")
                denied.add((tid,j,seq))
            else:
                need(j not in live,"P0_ALLOWED_LIVE_ENGINE_JOINT")
            pub.pop(tid)
        elif ev=="plugin_public_return":
            need(tid in attempted and attempted[tid]==j,
                 "WORKER_RETURN_WITHOUT_ATTEMPT")
            need(any(t==tid and a==j and s<seq for t,a,s in denied),
                 "ENGINE_PUBLIC_DELETE_NOT_DENIED")
        elif ev=="plugin_p0_live":
            need(tid in attempted and attempted[tid]==j and j in live,
                 "PUBLIC_P0_FAILED_OR_STALE")
            need(any(t==tid and a==j and s<seq for t,a,s in denied),
                 "P0_NOOP_NOT_OBSERVED")
            attempted.pop(tid)
            completed+=1
        elif ev=="solver_return":
            solver_return[step]=seq
        elif ev.startswith("plugin_standalone_") or ev.startswith("plugin_group_"):
            plugin_controls[ev].append((j,seq))
        elif ev=="P0_registries_empty":
            need(not live and not pending_free,"TEARDOWN_STALE_ENGINE_REGISTRY")
            teardown_seen=True
        elif ev=="P0_admission_removed":
            need(teardown_seen and not live and not pending_free,
                 "ADMISSION_REMOVED_TOO_EARLY")
    need(not active and not callbacks and not m_held and not pub and not attempted,
         "UNBALANCED_ACTIVE_OR_MUTEX")
    need(not live and not pending_free,"LIVE_OR_DESTROYING_LEAK")
    need(len(worker_callbacks)>=expected_workers,"REAL_WORKER_CALLBACKS_NOT_EXERCISED")
    need(completed>=expected_workers and engine_attempts>=expected_workers,
         "NOT_ALL_WORKERS_ATTEMPTED_LIVE_ENGINE_P0")
    need(internal>0 and retire_steps>0,"NO_OWNED_INTERNAL_FREE")
    before=plugin_controls["plugin_standalone_before"]
    after=plugin_controls["plugin_standalone_destroyed"]
    group=plugin_controls["plugin_group_before"]
    noop=plugin_controls["plugin_group_noop"]
    empty=plugin_controls["plugin_group_empty"]
    need(before and after and before[0][0]==after[0][0] and before[0][1]<after[0][1],
         "PLUGIN_STANDALONE_NOT_DESTROYED")
    need(group and noop and empty and group[0][0]==noop[0][0]==empty[0][0]
         and group[0][1]<noop[0][1]<empty[0][1],
         "PLUGIN_GROUP_SEMANTICS_CHANGED")
    need(names.index("context_teardown")<names.index("P0_registries_empty")<
         names.index("P0_admission_removed")<names.index("world_destroy")<
         names.index("context_teardown_after"),"INVALID_TEARDOWN")
    need(any(e["ev"]=="P0_class_plugin" and e["arg"]==before[0][0]
             for e in events),"PLUGIN_STANDALONE_FALSE_BLOCK")
    need(any(e["ev"]=="P0_class_plugin" and e["arg"]==group[0][0]
             for e in events),"PLUGIN_GROUP_FALSE_BLOCK")
    # Φ is only bounded here: Webots' step() return; foreign plugin workers excluded.
    return dict(real_worker_tids=sorted(worker_callbacks),engine_public_attempts=engine_attempts,
                no_op_live=completed,internal_frees=internal,retirements=retire_steps,
                M_contention_events=contention,source="NATIVE_ONLY_WHEN_READ_FROM_RUN_LOG")

def selftest():
    def ev(name, tid=10, ptr=0, step=1):
        return dict(ev=name,tid=tid,arg=ptr,step=step,seq=0)
    # A synthetic causal skeleton: never claimed to be a Webots execution.
    base=[
        ev("P0_admission_installed"),ev("configured_threads",ptr=1),
        ev("P0_M_acquired"),ev("P0_class_plugin",ptr=51),ev("P0_M_released"),
        ev("plugin_standalone_before",ptr=51),ev("P0_public_enter",ptr=51),
        ev("P0_public_allowed",ptr=51),ev("plugin_standalone_destroyed",ptr=51),
        ev("P0_M_acquired"),ev("P0_class_plugin",ptr=52),ev("P0_M_released"),
        ev("plugin_group_before",ptr=52),ev("P0_public_enter",ptr=52),
        ev("P0_public_allowed",ptr=52),ev("plugin_group_noop",ptr=52),
        ev("plugin_group_empty",ptr=52),
        ev("step_enter"),ev("contact_create",ptr=71),ev("M_acquired"),
        ev("P0_register",ptr=71),ev("M_released"),ev("worker_task_enter",tid=20),
        ev("plugin_callback_enter",tid=20),ev("plugin_public_attempt",tid=20,ptr=71),
        ev("P0_public_enter",tid=20,ptr=71),ev("P0_M_acquired",tid=20,ptr=71),
        ev("P0_class_engine",tid=20,ptr=71),ev("P0_M_released",tid=20,ptr=71),
        ev("P0_public_denied",tid=20,ptr=71),ev("plugin_public_return",tid=20,ptr=71),
        ev("plugin_p0_live",tid=20,ptr=71),ev("plugin_callback_exit",tid=20),
        ev("worker_task_exit",tid=20),ev("main_b2_after"),ev("solver_return"),
        ev("M_acquired"),ev("P0_unregister",ptr=71),ev("P0_internal_free",ptr=71),
        ev("M_released"),ev("context_teardown"),ev("P0_teardown_M_acquired"),
        ev("P0_registries_empty"),ev("P0_teardown_M_released"),
        ev("P0_admission_removed"),ev("world_destroy"),ev("context_teardown_after")]
    def renum(items): return [dict(x,seq=i+1) for i,x in enumerate(items)]
    check(renum(base),1)
    mutants={
        "missing_engine_attempt":[x for x in base if x["ev"]!="plugin_public_attempt"],
        "fake_two_workers":base,
        "false_engine_allow":[dict(x,ev="P0_public_allowed") if x["ev"]=="P0_public_denied" else x for x in base],
        "missing_internal_free":[x for x in base if x["ev"]!="P0_internal_free"],
        "missing_unregister":[x for x in base if x["ev"]!="P0_unregister"],
        "no_plugin_group_noop":[x for x in base if x["ev"]!="plugin_group_noop"],
        "no_teardown":[x for x in base if x["ev"]!="P0_registries_empty"],
        "no_real_callback":[x for x in base if x["ev"]!="worker_task_enter"],
        "no_registration":[x for x in base if x["ev"]!="P0_register"],
        "destruction_before_unregister":base[:37]+[ev("P0_internal_free",ptr=71)]+base[37:],
        "recursive_M":base[:28]+[ev("P0_M_acquired",tid=20,ptr=71)]+base[28:],
    }
    for name,items in mutants.items():
        try:
            check(renum(items),2 if name=="fake_two_workers" else 1)
        except Reject as exc:
            print("NEGATIVE_REJECTED",name,str(exc))
        else: raise SystemExit("ORACLE_ACCEPTED_MUTANT:"+name)
    for name,lines in {
        "malformed":["H6_P0 seq=no step=1 tid=1 event=P0_register arg=71"],
        "gap":["H6_P0 seq=1 step=1 tid=1 event=x arg=0",
               "H6_P0 seq=3 step=1 tid=1 event=y arg=0"]
    }.items():
        try:parse(lines)
        except Reject:print("NEGATIVE_REJECTED",name)
        else:raise SystemExit("ORACLE_ACCEPTED_MUTANT:"+name)
    print("H6_P0_ORACLE_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["--selftest"]:selftest()
    elif len(sys.argv)==3:
        try: print("H6_P0_QUALIFICATION",check(parse(Path(sys.argv[1]).read_text(errors="replace").splitlines()),int(sys.argv[2])))
        except Reject as exc: raise SystemExit("H6_P0_UNPROVEN:"+str(exc))
    else: raise SystemExit("usage: qualify_p0.py --selftest | WEBOTS_LOG WORKERS")
