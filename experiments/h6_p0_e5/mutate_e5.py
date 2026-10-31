#!/usr/bin/env python3
"""Mutation-based RED controls on a *real, already qualified* E5 log.
Changes are solely in copied log text; Webots physical outcome is not synthetic.
Re-number P0 sequences when events are removed to exclude sequence-gap-only REDs.
"""
from pathlib import Path
import sys,re,hashlib
from qualify_e5 import evaluate
def need(ok,msg):
    if not ok: raise SystemExit("E5_MUTANT_REFUSED "+msg)
def delete_events(log,events):
    names=set(events)
    lines=[]
    for x in log.splitlines():
        if x.startswith("H6_P0 ") and "event="+next(iter(names)) in x:
            pass
        if x.startswith("H6_P0 ") and any("event="+n+" " in x for n in names):
            continue
        lines.append(x)
    seq=0;out=[]
    for line in lines:
        if line.startswith("H6_P0 seq="):
            seq+=1;line=re.sub(r"^H6_P0 seq=\d+",f"H6_P0 seq={seq}",line)
        out.append(line)
    return "\n".join(out)+"\n"
def change_logs(log,old,new):
    need(old in log,"mutation_anchor_"+old[:60]);return log.replace(old,new)
def run(path,case,mode,n,outdir):
    original=Path(path).read_text(errors="replace")
    evaluate(original,case,mode,n) # precondition: only real PASS logs eligible
    mutants={
      "missing_plugin_attached":delete_events(original,["E5_plugin_attached_group_before"]),
      "missing_plugin_group_empty":delete_events(original,["E5_plugin_group_empty"]),
      "missing_plugin_permanent_free":delete_events(original,["E5_plugin_permanent_destroyed"]),
      "missing_configured_workers":delete_events(original,["configured_threads"]),
      "no_internal_free":delete_events(original,["P0_internal_free"]),
      "no_unregister":delete_events(original,["P0_unregister"]),
      "no_admission":delete_events(original,["P0_admission_installed"]),
      "missing_operation":change_logs(original,"H6_E5_CONTROLLER operation_complete","H6_E5_CONTROLLER operation_missing"),
    }
    if case=="body":
        mutants.update({
            "no_body_destroy":delete_events(original,["E5_before_dBodyDestroy"]),
            "no_cross_body_scan":"\n".join(x for x in original.splitlines() if not x.startswith("H6_E5_SCAN "))+"\n",
            "no_drop":delete_events(original,["E5_drop"]),
            "no_AC_feedback":"\n".join(x for x in original.splitlines()
                                         if not x.startswith("H6_E5_AC_SOLVER "))+"\n",
        })
        if mode=="attached":
            mutants["owner_only_rule"]=change_logs(original,"H6_E5_SCAN mode=attached","H6_E5_SCAN mode=owner")
    else:
        mutants.update({
          "fake_reset_not_called":delete_events(original,["E5_reset_id_enter"]),
          "no_RESET_engine":delete_events(original,["E5_reset_engine"]),
          "no_RESET_M":delete_events(original,["P0_reset_M_acquired"]),
          "no_plugin_reset_detach":delete_events(original,["E5_reset_plugin_detached"]),
        })
    bad_plugin=re.sub(r"(H6_E5_PLUGIN_STEP case=\w+ tick=\d+ group_count=\d+ group_b0=)\S+",
                      r"\g<1>(nil)", original)
    mutants["plugin_was_never_attached"]=bad_plugin
    need(bad_plugin!=original,"plugin field mutation failed")
    if n==2:
        # Workers require distinct native task TIDs, not just a configured count.
        tasks=re.findall(r"^H6_P0 seq=\d+ step=\d+ tid=(\d+) event=worker_task_enter ",original,re.M)
        need(len(set(tasks))>=2,"no-two-real-workers-precondition")
        from_tid=tasks[-1]
        to_tid=next(x for x in tasks if x!=from_tid)
        mutants["false_second_worker"]=re.sub(
            r"(^H6_P0 seq=\d+ step=\d+ tid=)"+re.escape(from_tid)+r"( event=worker_task_)",
            lambda m:m.group(1)+to_tid+m.group(2),original,flags=re.M)
    od=Path(outdir);od.mkdir(parents=True,exist_ok=True)
    verdict=[]
    for label,mutation in mutants.items():
        require_red=False
        try:
            evaluate(mutation,case,mode,n)
        except (ValueError,IndexError,KeyError):
            require_red=True
        (od/(label+".log")).write_text(mutation)
        verdict.append((label,require_red,hashlib.sha256(mutation.encode()).hexdigest()))
        need(require_red,"MUTANT_ACCEPTED_"+label)
    (od/"mutant-verdicts.txt").write_text("\n".join("%s %s %s"%(a,"REJECTED" if b else "ACCEPTED",c)
                                                      for a,b,c in verdict)+"\n")
    print("H6_E5_ALL_MUTANTS_REJECTED",len(verdict),case,mode,n)
if __name__=="__main__":
    if len(sys.argv)!=6: raise SystemExit("usage: LOG case mode workers OUTDIR")
    run(sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4]),sys.argv[5])
