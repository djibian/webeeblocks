#!/usr/bin/env python3
"""Fail-closed source-pinned scheduler OBSERVATION oracle; NOT a P0 safety proof."""
import re
import sys
from pathlib import Path

PATTERN = re.compile(r"^H6_P0 seq=(\d+) step=(\d+) tid=(\d+) event=([a-z0-9_]+) arg=(\d+)$")
class Reject(Exception):
    pass

def require(b, why):
    if not b:
        raise Reject(why)

def read(path):
    result = []
    for line in Path(path).read_text(errors="replace").splitlines():
        m = PATTERN.match(line.strip())
        if m:
            seq, step, tid, ev, arg = m.groups()
            result.append(dict(seq=int(seq), step=int(step),
                               tid=int(tid), ev=ev, arg=int(arg)))
    require(result, "MISSING_TRACE")
    seqs = [x["seq"] for x in result]
    require(len(seqs) == len(set(seqs)), "DUPLICATE_SEQ")
    result.sort(key=lambda x:x["seq"])
    require([x["seq"] for x in result] == list(range(1, len(result)+1)),
            "MISSING_NOTIFICATION_OR_SEQ")
    return result

def validate(ev, requested):
    events = [x["ev"] for x in ev]
    for necessary in ("configured_threads","step_enter","main_b1_before",
                      "main_b2_after","solver_return","plugin_callback_enter",
                      "plugin_callback_exit","plugin_public_attempt",
                      "plugin_public_return","plugin_baseline_noop",
                      "contact_create","M_acquired","group_empty",
                      "step_cleanup_done","plugin_teardown_before",
                      "plugin_teardown_after","cluster_teardown_before",
                      "cluster_teardown_after","context_teardown",
                      "context_teardown_after","world_destroy"):
        require(necessary in events, "MISSING_"+necessary.upper())
    require(any(x["ev"]=="configured_threads" and x["arg"]==requested for x in ev),
            "THREAD_SETTING_NOT_SEEN")
    # A configured worker is not an exercised worker.
    active = set()
    worker_callbacks = set()
    m_held = set()
    first_solver_return = {}
    first_retire = {}
    callbacks = set()
    for x in ev:
        typ, tid, step = x["ev"], x["tid"], x["step"]
        if typ == "worker_task_enter":
            require(tid not in active, "NESTED_WORKER_TASK")
            active.add(tid)
        elif typ == "worker_task_exit":
            require(tid in active, "ORPHAN_WORKER_TASK_EXIT")
            active.remove(tid)
        elif typ == "plugin_callback_enter":
            require(tid not in callbacks, "NESTED_PLUGIN_CALLBACK")
            callbacks.add(tid)
            if tid in active:
                worker_callbacks.add(tid)
        elif typ == "plugin_callback_exit":
            require(tid in callbacks, "ORPHAN_PLUGIN_CALLBACK_EXIT")
            callbacks.remove(tid)
        elif typ == "M_acquired":
            require(tid not in m_held, "RECURSIVE_M")
            m_held.add(tid)
        elif typ == "M_release":
            require(tid in m_held, "UNBALANCED_M")
            m_held.remove(tid)
        elif typ == "solver_return":
            first_solver_return.setdefault(step,x["seq"])
        elif typ == "plugin_group_retire":
            first_retire.setdefault(step,x["seq"])
            require(step in first_solver_return, "RETIRE_BEFORE_SOLVER_RETURN")
        elif typ == "plugin_public_attempt":
            require(tid in callbacks, "PUBLIC_ATTEMPT_OUTSIDE_CALLBACK")
    require(not active and not callbacks and not m_held, "UNBALANCED_ACTIVITY")
    require(len(worker_callbacks) >= requested,
            "WORKER_CALLBACKS_NOT_EXERCISED:"+str(sorted(worker_callbacks)))
    require(all(first_solver_return[step] < seq for step,seq in first_retire.items()),
            "BAD_STEP_RETIRE_ORDER")
    require(events.index("plugin_teardown_before") < events.index("plugin_teardown_after") <
            events.index("cluster_teardown_before") < events.index("cluster_teardown_after") <
            events.index("context_teardown") < events.index("world_destroy") <
            events.index("context_teardown_after"),"BAD_TEARDOWN_ORDER")
    # Baseline observation ONLY: ODE's original group-owned public NO-OP.
    # Joint IDs are never dereferenced by this oracle.
    return sorted(worker_callbacks)

def e(ev, tid, step=1):
    return dict(ev=ev, tid=tid, step=step, seq=0, arg=0)

def selftest():
    # Mutants model the discriminants, NOT physical evidence.
    base = [e("configured_threads",1),e("step_enter",1),e("main_b1_before",1),
            e("worker_task_enter",2),e("plugin_callback_enter",2),
            e("plugin_public_attempt",2),e("plugin_public_return",2),
            e("plugin_baseline_noop",2),e("plugin_callback_exit",2),
            e("worker_task_exit",2),e("main_b2_after",1),
            e("M_acquired",2),e("M_release",2),e("contact_create",2),
            e("solver_return",1),e("plugin_group_retire",1),
            e("group_empty",1),e("step_cleanup_done",1),
            e("plugin_teardown_before",1),e("plugin_teardown_after",1),
            e("cluster_teardown_before",1),e("cluster_teardown_after",1),
            e("context_teardown",1),e("world_destroy",1),
            e("context_teardown_after",1)]
    for i,x in enumerate(base): x["seq"]=i+1
    base[0]["arg"]=1  # synthetic configured_threads=1, not a recorded event
    validate(base,1)
    mutants = {
      "no_callback": [x for x in base if x["ev"]!="plugin_callback_enter"],
      "no_worker": [x for x in base if x["ev"]!="worker_task_enter"],
      "no_notification": [x for x in base if x["ev"]!="plugin_public_return"],
      "recursion": base[:12] + [e("M_acquired",2)] + base[12:],
      "premature_retire": sorted(base,key=lambda x:0 if x["ev"]=="plugin_group_retire" else 1),
      "wrong_teardown": [x for x in base if x["ev"]!="world_destroy"],
    }
    for name,mutation in mutants.items():
        # reorder sequence for sorting-independent mutants
        for i,x in enumerate(mutation): x = dict(x,seq=i+1); mutation[i]=x
        try:
            validate(mutation,1)
        except Reject:
            print("ORACLE_NEGATIVE_REJECTED",name)
        else:
            raise SystemExit("ORACLE_FAILED_TO_REJECT "+name)
    try:
        validate(base,2)
    except Reject as ex:
        require("WORKER_CALLBACKS_NOT_EXERCISED" in str(ex), "BAD_2_WORKER_NEGATIVE")
        print("ORACLE_NEGATIVE_REJECTED fake_two_workers")
    else:
        raise SystemExit("ORACLE_FAILED_TO_REJECT fake_two_workers")
    print("H6_P0_OBSERVATION_SELFTEST_PASS")

if __name__ == "__main__":
    if len(sys.argv)==2 and sys.argv[1]=="--selftest":
        selftest()
    elif len(sys.argv)==3:
        try:
            observed = validate(read(sys.argv[1]),int(sys.argv[2]))
            print("H6_P0_OBSERVED_WORKER_CALLBACKS",observed)
        except Reject as exc:
            raise SystemExit("H6_P0_UNPROVEN:"+str(exc))
    else:
        raise SystemExit("usage: qualify_observation.py --selftest | TRACE EXPECTED_WORKERS")
