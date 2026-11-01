#!/usr/bin/env python3
"""Paired original/P0 native RESET and plugin-lifetime oracle (NO synthetic PASS).

The individual original E5 oracle is first applied without modifications.
Address values are compared ONLY within one simultaneous live generation.
Never query a freed dJointID or infer an incarnation from a reused address.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"h6_p0_e5"))
from qualify_e5 import evaluate, parse, require

NIL={"(nil)", "0x0"}
def events_named(events, name):
    return [e for e in events if e["ev"] == name]
def exactly(events, name, count=1):
    found=events_named(events,name)
    require(len(found)==count,"BC_EVENT_COUNT_%s_expected_%d_observed_%d"%(name,count,len(found)))
    return found
def index(events, name):
    return exactly(events,name)[0]["seq"]

def check_arm(root, mode, workers):
    dir=root/(("p0" if mode=="attached" else "baseline")+"-reset-workers"+str(workers))
    require(dir.is_dir(),"MISSING_ARM_"+str(dir))
    require((dir/"exit.txt").read_text().strip()=="0",
            "NATIVE_NONZERO_"+str(dir))
    require((dir/"qualification-exit.txt").read_text().strip()=="0",
            "PRIMARY_ORACLE_RED_"+str(dir))
    log=(dir/"webots.log").read_text(errors="replace")
    evaluate(log,"reset",mode,workers)
    ev,scans,feedback,steps=parse(log)
    require("operation_begin case=reset" in log and
            "target_loadState_requested" in log,"NO_REAL_SUPERVISOR_LOADSTATE_"+mode)
    require(len(steps)>2,"NO_STEPS_OF_PLUGIN_LIFETIME")
    require(all(case=="reset" and count==1 for case,tick,count,b0,b1,motor in steps),
            "GROUP_COUNT_CHANGED_BEFORE_OWNER_CLEANUP")
    # group/AMotor remain alive in the plugin through RESET; the group
    # contact itself loses body attachment. The standalone contact is NEVER
    # dereferenced in any witness after its native destruction.
    attached=[(tick,b0,motor) for _,tick,_,b0,_,motor in steps if b0 not in NIL]
    detached=[(tick,b0,motor) for _,tick,_,b0,_,motor in steps if b0 in NIL]
    require(attached and detached and max(x[0] for x in attached)<min(x[0] for x in detached),
            "NO_REAL_ATTACHED_THEN_DETACHED_GROUP")
    initial_motor=attached[0][2]
    require(initial_motor not in NIL and all(motor==initial_motor for _,_,motor in attached+detached),
            "PLUGIN_PERMANENT_JOINT_NOT_ATTACHED_ACROSS_RESET")
    initial_group=attached[0][1]
    require(initial_group not in NIL and all(b0==initial_group for _,b0,_ in attached),
            "UNEXPECTED_GROUP_BODY_REPLACEMENT")
    require(exactly(ev,"E5_plugin_attached_group_before")[0]["arg"] !=
            exactly(ev,"E5_plugin_attached_standalone_before")[0]["arg"],
            "SAME_SIMULTANEOUS_JOINT_GROUP_AND_STANDALONE")
    group=exactly(ev,"E5_plugin_attached_group_before")[0]["arg"]
    standalone=exactly(ev,"E5_plugin_attached_standalone_before")[0]["arg"]
    motor=exactly(ev,"E5_plugin_permanent_before")[0]["arg"]
    require(len({group,standalone,motor})==3,"PLUGIN_JOINTS_NOT_DISTINCT_WHILE_ALIVE")
    ge=index(ev,"E5_plugin_group_empty")
    me=index(ev,"E5_plugin_permanent_destroyed")
    require(ge<me and index(ev,"E5_plugin_standalone_reset_no_use")<me,
            "PLUGIN_CLEANUP_SEMANTICS_WRONG")
    require(not events_named(ev,"E5_plugin_standalone_owner_free"),
            "PLUGIN_REDESTROYED_STANDALONE_ON_CLEANUP")
    require(len({e["tid"] for e in ev if e["ev"]=="worker_task_enter"})>=workers,
            "NOT_REAL_%d_WORKERS"%workers)
    if mode=="attached":
        entry=index(ev,"E5_reset_id_enter")
        exit_=index(ev,"E5_reset_id_exit")
        lock=index(ev,"P0_reset_M_acquired")
        unlock=index(ev,"P0_reset_M_released")
        require(entry<lock<unlock<exit_,"P0_RESET_ID_MUTEX_TIMELINE")
        engine=events_named(ev,"E5_reset_engine")
        require(engine,"NO_LIVE_ENGINE_CONTACT_AT_RESET")
        require(len({e["arg"] for e in engine})==len(engine),
                "DUPLICATE_ENGINE_RESET_ATTEMPT_IN_SAME_PHASE")
        for e in engine:
            j=e["arg"];t=e["seq"]
            unreg=[x for x in events_named(ev,"P0_unregister") if x["arg"]==j and t<x["seq"]<unlock]
            free=[x for x in events_named(ev,"P0_internal_free") if x["arg"]==j and t<x["seq"]<unlock]
            require(len(unreg)==1 and len(free)==1 and
                    lock<t<unreg[0]["seq"]<free[0]["seq"]<unlock,
                    "ENGINE_NOT_EXACTLY_ONCE_UNREGISTER_INTERNAL_FREE_WITH_M")
        stage=events_named(ev,"E5_reset_plugin_native_destroy")
        require(len(stage)==2 and {x["arg"] for x in stage}=={group,standalone},
                "STAGED_PLUGIN_SET_NOT_EXACTLY_GROUP_PLUS_STANDALONE")
        allowed=events_named(ev,"P0_public_allowed")
        require(all(sum(x["arg"]==joint and x["seq"]>unlock for x in allowed)==1
                    for joint in (group,standalone)),
                "PLUGIN_RESET_PUBLIC_DESTROY_GATE_NOT_EXACTLY_ONCE_AFTER_UNLOCK")
        require(all(unlock<x["seq"]<exit_ for x in stage),
                "PLUGIN_DESTROY_STAGED_INSIDE_NONRECURSIVE_M")
        require(not any(x["arg"] in (group,standalone) for x in
                        events_named(ev,"P0_internal_free")),
                "PLUGIN_FREED_THROUGH_ENGINE_ROUTE")
        require(not any(x["arg"] in (group,standalone) for x in
                        events_named(ev,"P0_public_denied")),
                "PLUGIN_FALSIFIED_AS_ENGINE")
        require(exactly(ev,"P0_registries_empty")[0]["seq"] <
                exactly(ev,"world_destroy")[0]["seq"],
                "TEARDOWN_ORDER_WRONG")
    else:
        entry=index(ev,"BC_original_reset_enter")
        exit_=index(ev,"BC_original_reset_exit")
        require(entry<exit_,"BASELINE_RESET_ORIGINAL_NOT_EXECUTED")
        public=events_named(ev,"public_destroy_enter")
        require(sum(x["arg"]==group and entry<x["seq"]<exit_ for x in public)==1,
                "ORIGINAL_GROUP_CONTACT_NOT_ROUTED_EXACTLY_ONCE")
        require(sum(x["arg"]==standalone and entry<x["seq"]<exit_ for x in public)==1,
                "ORIGINAL_STANDALONE_CONTACT_NOT_ROUTED_EXACTLY_ONCE")
        require(not events_named(ev,"P0_internal_free"),
                "BASELINE_NOT_ORIGINAL_ENGINE_OWNERSHIP")
    return {"mode":mode,"workers":workers,"reset_enter_seq":entry,
            "initial_group_body_attached":True,
            "post_reset_group_detached_motor_still_attached":True,
            "native_worker_tids":len({e["tid"] for e in ev if e["ev"]=="worker_task_enter"}),
            "engine_reset_contacts":len(events_named(ev,"E5_reset_engine")),
            "original_observer_only":mode=="baseline"}

def main():
    if len(sys.argv)!=2: raise ValueError("usage: qualify_reset_plugin.py EVIDENCE_ROOT")
    root=Path(sys.argv[1])
    for expected in ("experiment-head.txt","observed-head.txt","observed-pin.txt",
                     "binary-sha256.txt","baseline/bin-sha256.txt",
                     "standalone-p0-only.patch","baseline/observer-only.patch"):
        require((root/expected).is_file(),"MISSING_PROVENANCE_"+expected)
    require((root/"experiment-head.txt").read_text().strip()==
            (root/"observed-head.txt").read_text().strip(),"HEAD_CHANGED_WITHIN_RUN")
    require((root/"observed-pin.txt").read_text().strip()==
            "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b","WEBOTS_PIN_CHANGED")
    for n in (1,2):
        a=check_arm(root,"attached",n)
        b=check_arm(root,"baseline",n)
        print("E5_BC_NATIVE_PAIRED_PASS",a,b,flush=True)
    print("E5_B_RESET=BOUNDED_PASS E5_C_PLUGIN=BOUNDED_PASS "
          "PHI_PRIVATE_THREADS=UNPROVEN ABI=UNQUALIFIED",flush=True)

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("E5_BC_RED_OR_UNPROVEN",str(e),file=sys.stderr)
        raise SystemExit(42)
