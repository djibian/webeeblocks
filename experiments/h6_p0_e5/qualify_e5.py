#!/usr/bin/env python3
"""Strict E5 native-trace oracle. Synthetic mutants are NEVER native evidence.
Usage: qualify_e5.py WEBOTS_LOG {body|reset} {owner|attached|baseline} {1|2}
Exit 0 only for explicitly discriminating measured cases.
"""
import re, sys
from pathlib import Path
from collections import defaultdict
P=re.compile(r"^H6_P0 seq=(\d+) step=(\d+) tid=(\d+) event=([A-Za-z0-9_]+) arg=(\d+)$")
S=re.compile(r"^H6_E5_SCAN mode=(\w+) joint=(0x[0-9a-fA-F]+) owner=(0x[0-9a-fA-F]+) victim=(0x[0-9a-fA-F]+) v0=(0x[0-9a-fA-F]+|\(nil\)) v1=(0x[0-9a-fA-F]+|\(nil\)) owner_enabled=(\d+) drop=(\d+)$")
F=re.compile(r"^H6_E5_AC_SOLVER case=(\w+) tick=(\d+) forceL1=([\d.eE+-]+)$")
PL=re.compile(r"^H6_E5_PLUGIN_STEP case=(\w+) tick=(\d+) group_count=(\d+) group_b0=(\S+) group_b1=(\S+) motor_b0=(\S+)$")
def require(cond,msg):
    if not cond: raise ValueError("E5_UNPROVEN_OR_REFUTED: "+msg)
def parse(text):
    events=[]; scans=[]; feedback=[]; plugin=[]
    for no,line in enumerate(text.splitlines(),1):
        if line.startswith("H6_P0"):
            m=P.fullmatch(line.strip());require(m is not None,"MALFORMED_P0:%d"%no)
            seq,step,tid,ev,arg=m.groups()
            events.append(dict(seq=int(seq),step=int(step),tid=int(tid),ev=ev,arg=int(arg)))
        if line.startswith("H6_E5_SCAN"):
            m=S.fullmatch(line.strip());require(m is not None,"MALFORMED_SCAN:%d"%no)
            mode,j,owner,b,v0,v1,en,drop=m.groups()
            value=lambda v: 0 if v=="(nil)" else int(v,16)
            scans.append(dict(mode=mode,j=int(j,16),owner=int(owner,16),
                              b=int(b,16),v0=value(v0),v1=value(v1),
                              enabled=int(en),drop=int(drop)))
        if line.startswith("H6_E5_AC_SOLVER"):
            m=F.fullmatch(line.strip());require(m is not None,"MALFORMED_FEEDBACK:%d"%no)
            a,t,f=m.groups();feedback.append((a,int(t),float(f)))
        if line.startswith("H6_E5_PLUGIN_STEP"):
            m=PL.fullmatch(line.strip());require(m is not None,"MALFORMED_PLUGIN:%d"%no)
            a,t,n,b0,b1,p=m.groups();plugin.append((a,int(t),int(n),b0,b1,p))
    events.sort(key=lambda e:e["seq"])
    require(events,"NO_NATIVE_P0_TRACE")
    require([e["seq"] for e in events]==list(range(1,len(events)+1)),"MISSING_OR_DUPLICATE_SEQ")
    return events,scans,feedback,plugin

def evaluate(log,case,mode,workers):
    ev,scans,feedback,plugin=parse(log)
    if mode=="baseline":
        # Original Webots contact ownership, with the #777 READ-ONLY trace
        # observer. No P0 events, E5 patch, or transfer of engine semantics.
        require(case in ("body","reset"),"INVALID_BASELINE_CASE")
        require("operation_begin case="+case in log,"BASELINE_OPERATION_NOT_REQUESTED")
        require(workers==1 or workers==2,"INVALID_BASELINE_WORKERS")
        require(any(e["ev"]=="configured_threads" and e["arg"]==workers
                    for e in ev),"BASELINE_WORKERS_NOT_CONFIGURED")
        require("E5_plugin_group_empty" in {e["ev"] for e in ev} and
                "E5_plugin_permanent_destroyed" in {e["ev"] for e in ev},
                "BASELINE_PLUGIN_CLEANUP_MISSING")
        standalone=[e["arg"] for e in ev if e["ev"]=="E5_plugin_attached_standalone_before"]
        require(len(standalone)==1,"BASELINE_ATTACHED_PLUGIN_STANDALONE_MISSING")
        if case=="reset":
            require(any(e["ev"]=="public_destroy_enter" and
                        e["arg"]==standalone[0] for e in ev),
                    "BASELINE_ORIGINAL_RESET_DID_NOT_DESTROY_STANDALONE")
            require(any(e["ev"]=="E5_plugin_standalone_reset_no_use" for e in ev),
                    "BASELINE_PLUGIN_DANGLING_HANDLE_NOT_QUARANTINED")
        else:
            require(any(e["ev"]=="E5_plugin_standalone_owner_free" for e in ev),
                    "BASELINE_BODY_PLUGIN_STANDALONE_OWNER_CLEANUP_MISSING")
        require(any(a==case and n==1 and b0 not in ("(nil)","0x0") and
                    p not in ("(nil)","0x0") for a,t,n,b0,b1,p in plugin),
                "BASELINE_PLUGIN_ATTACHMENT_NOT_EXERCISED")
        require(any(a==case and n==1 and b0 in ("(nil)","0x0") and
                    p not in ("(nil)","0x0") for a,t,n,b0,b1,p in plugin),
                "BASELINE_PLUGIN_DETACH_OR_PERMANENT_REGRESSION")
        return {"case":case,"mode":"baseline","workers":workers,
                "events":len(ev),"plugin_steps":len(plugin),
                "scope":"ATTACHED_PLUGIN_SEMANTICS_ONLY"}
    names=[e["ev"] for e in ev]
    def select(name): return [e for e in ev if e["ev"]==name]
    require(workers in (1,2),"INVALID_WORKERS")
    require(any(x["arg"]==workers for x in select("configured_threads")),"NOT_CONFIGURED_WORKERS")
    require("operation_begin case="+case in log,
            "CONTROLLER_OPERATION_NOT_REQUESTED")
    require("P0_admission_installed" in names and "P0_admission_removed" in names,
            "P0_ADMISSION_LIFECYCLE_MISSING")
    require("P0_registries_empty" in names and "world_destroy" in names,
            "TEARDOWN_MISSING")
    require(select("P0_registries_empty")[0]["seq"] <
            select("world_destroy")[-1]["seq"],"REGISTRY_NOT_CLOSED_BEFORE_WORLD_DESTROY")
    require(all(x["ev"]!="P0_public_denied" or x["arg"] not in
                {v["arg"] for v in select("P0_internal_free")} for x in []),
            "INTERNAL_ROUTE_CHECK") # event timeline below is discriminating
    active=set(); held=set(); live=set(); retired=set()
    engine_frees=0; recursive=0
    begins={"M_acquired","P0_M_acquired","P0_body_M_acquired",
            "P0_reset_M_acquired","P0_retire_M_acquired",
            "P0_cluster_dtor_M_acquired","P0_teardown_M_acquired"}
    ends={"M_released","P0_M_released","P0_body_M_released",
          "P0_reset_M_released","P0_retire_M_released",
          "P0_cluster_dtor_M_released","P0_teardown_M_released"}
    for x in ev:
        n,tid,j=x["ev"],x["tid"],x["arg"]
        if n=="worker_task_enter":
            require(tid not in active,"DUPLICATE_WORKER");active.add(tid)
        elif n=="worker_task_exit":
            require(tid in active,"WORKER_EXIT_WITHOUT_ENTER");active.remove(tid)
        elif n in begins:
            if tid in held:recursive+=1
            held.add(tid)
        elif n in ends:
            require(tid in held,"M_UNLOCK_WITHOUT_LOCK");held.remove(tid)
        elif n=="P0_register":
            require(j not in live,"DUPLICATE_LIVE_ID");live.add(j)
        elif n=="P0_unregister":
            require(j in live,"INVALID_UNREGISTER");live.remove(j);retired.add(j)
        elif n=="P0_internal_free":
            require(j in retired and j not in live,"INTERNAL_FREE_BEFORE_UNREGISTER")
            require(tid in held,"INTERNAL_FREE_WITHOUT_M")
            require(not active,"INTERNAL_FREE_DURING_WORKER")
            retired.remove(j);engine_frees+=1
    require(not active and not held and not live and not retired,"UNCLOSED_WORKERS_M_OR_REGISTRY")
    require(recursive==0,"RECURSIVE_NONRECURSIVE_M")
    worker_tids={e["tid"] for e in select("worker_task_enter")}
    require(len(worker_tids)>=workers,"FALSE_SECOND_WORKER")
    require(engine_frees>0,"NO_ENGINE_FREE")
    require(select("E5_plugin_attached_group_before") and
            select("E5_plugin_permanent_before") and
            len(select("E5_plugin_attached_standalone_before"))==1,
            "PLUGIN_ATTACHED_WITNESS_MISSING")
    require(select("E5_plugin_group_empty") and
            select("E5_plugin_permanent_destroyed"),"PLUGIN_GROUP_OR_PERMANENT_CLEANUP_MISSING")
    require(any(a==case and n==1 and b0 not in ("(nil)","0x0") and
                p not in ("(nil)","0x0") for a,t,n,b0,b1,p in plugin),
            "PLUGIN_NOT_PHYSICALLY_ATTACHED")
    require(any(a==case and n==1 and b0 in ("(nil)","0x0") and
                p not in ("(nil)","0x0") for a,t,n,b0,b1,p in plugin),
            "PLUGIN_CONTACT_NOT_DETACHED_OR_PERMANENT_LOST")
    if case=="body":
        require("foreign_remove_requested" in log,"NO_REAL_FOREIGN_REMOVE")
        require(select("E5_before_dBodyDestroy") and select("E5_after_dBodyDestroy"),
                "NO_REAL_WBSOLIDMERGER_DTOR")
        require(scans,"NO_REGISTERED_CONTACT_SCAN")
        initial = next((x for x in plugin if x[0]=="body" and x[1]<=36 and
                        x[3] not in ("(nil)","0x0") and x[5] not in ("(nil)","0x0")),None)
        require(initial is not None,"NO_INITIAL_ATTACHED_PLUGIN_REFERENCE")
        victim=int(initial[3],16)  # FOREIGN body alive before delete
        owner_a=int(initial[5],16) # TARGET body, evidenced by plugin permanent AMotor
        require(any(x["arg"]==victim for x in select("E5_before_dBodyDestroy")),
                "FOREIGN_VICTIM_NEVER_REALLY_DESTROYED")
        cross=[s for s in scans if s["owner"]==owner_a and s["b"]==victim and
               (s["v0"]==victim or s["v1"]==victim)]
        require(cross,"NO_DISCRIMINATING_OWNER_A_FOREIGN_B_ATTACHMENT")
        require(all(s["mode"]==mode for s in scans),"MIXED_DROP_MODES")
        if mode=="owner":
            require(any(s["drop"]==0 for s in cross),"NEGATIVE_OWNER_ARM_NOT_REFUTED")
            require(any(s["j"]==e["arg"] for s in cross for e in select("E5_keep")),
                    "OWNER_RETAIN_EVENT_MISSING")
            bound=min(e["seq"] for e in select("E5_before_dBodyDestroy")
                      if e["arg"]==victim)
            enter=max(e["seq"] for e in select("E5_body_destructor_enter")
                      if e["arg"]==victim and e["seq"]<bound)
            require(all(not any(e["arg"]==s["j"] and enter<e["seq"]<bound
                                for e in select("P0_unregister")) for s in cross),
                    "OWNER_NEGATIVE_ARM_NOT_ACTUALLY_RETAINED")
        else:
            require(mode=="attached","INVALID_BODY_MODE")
            require(all(s["drop"]==1 for s in cross),"ATTACHED_CROSS_BODY_NOT_DROPPED")
            drops={e["arg"]:e["seq"] for e in select("E5_drop")}
            unreg={e["arg"]:e["seq"] for e in select("P0_unregister")}
            frees={e["arg"]:e["seq"] for e in select("P0_internal_free")}
            bound=min(e["seq"] for e in select("E5_before_dBodyDestroy")
                      if e["arg"]==victim)
            enter=max(e["seq"] for e in select("E5_body_destructor_enter")
                      if e["arg"]==victim and e["seq"]<bound)
            require(all(s["j"] in drops and enter<drops[s["j"]]
                        < unreg.get(s["j"],0)<frees.get(s["j"],0)<bound for s in cross),
                    "DROPPED_CONTACT_NOT_UNREGISTERED_AND_FREED_BEFORE_BODY_DESTROY")
            # A-C feedback is evidence of an actual solver contribution, not registry count.
            require(select("E5_AC_excited"),"FIRST_POST_DELETE_SOLVER_NOT_EXCITED")
            require(any(a==case and t==4 and f>0 for a,t,f in feedback),
                    "NO_FIRST_POST_DELETE_AC_PHYSICAL_FEEDBACK")
            require(len([e for e in select("solver_return") if e["seq"]>bound])>=10,
                    "POST_BODY_DESTRUCTION_NOT_TEN_REAL_SOLVER_STEPS")
    else:
        require(case=="reset" and mode=="attached","UNSUPPORTED_RESET_MODE")
        require("target_loadState_requested" in log and select("E5_reset_id_enter")
                and select("E5_reset_id_exit"),"NODE_LOADSTATE_DID_NOT_REACH_RESET_ID")
        require(select("E5_reset_engine"),"NO_LIVE_ENGINE_CONTACT_AT_RESET")
        engine={e["arg"] for e in select("E5_reset_engine")}
        require(engine.issubset({e["arg"] for e in select("P0_unregister")}) and
                engine.issubset({e["arg"] for e in select("P0_internal_free")}),
                "RESET_ENGINE_NOT_FREED_INTERNALLY")
        require(select("E5_reset_plugin_detached"),"ATTACHED_PLUGIN_CONTACT_NOT_ROUTED")
        require(select("P0_reset_M_acquired") and select("P0_reset_M_released"),
                "RESET_M_NOT_EXERCISED")
        group=select("E5_plugin_attached_group_before")[0]["arg"]
        standalone=select("E5_plugin_attached_standalone_before")[0]["arg"]
        staged={e["arg"] for e in select("E5_reset_plugin_native_destroy")}
        allowed={e["arg"] for e in select("P0_public_allowed")}
        class_plugin={e["arg"] for e in select("P0_class_plugin")}
        require(group in staged and standalone in staged,
                "RESET_PLUGIN_GROUP_AND_STANDALONE_NOT_NATIVE_DESTROYED")
        require({group,standalone}.issubset(allowed & class_plugin),
                "PLUGIN_MISCLASSIFIED_ENGINE_OR_PUBLIC_GATE_BLOCKED")
        releases=[e["seq"] for e in select("P0_reset_M_released")]
        require(all(any(u<e["seq"] for u in releases)
                    for e in select("E5_reset_plugin_native_destroy")),
                "PUBLIC_PLUGIN_GATE_CALLED_WHILE_NONRECURSIVE_M_HELD")
        require(select("E5_plugin_standalone_reset_no_use") and
                not select("E5_plugin_standalone_owner_free"),
                "RESET_PLUGIN_STANDALONE_USED_AFTER_ENGINE_FREE")
    return {"case":case,"mode":mode,"workers":workers,"events":len(ev),
            "scans":len(scans),"engine_frees":engine_frees,
            "attached_plugin_steps":len(plugin),
            "ac_feedback":len(feedback)}
if __name__=="__main__":
    try:
        if len(sys.argv)!=5: raise ValueError("usage: LOG case mode workers")
        path,case,mode,workers=sys.argv[1:]
        print("H6_E5_NATIVE_QUALIFICATION",evaluate(Path(path).read_text(errors="replace"),
                                                    case,mode,int(workers)))
    except Exception as error:
        print("H6_E5_RED",str(error),file=sys.stderr)
        raise SystemExit(42)
