#!/usr/bin/env python3
"""Strict *additional* native H6 factorial oracle. NEVER replaces historical P4.
The 00 no-repair F arm is an expected physical negative control; historical P4
expects F to be repaired and MUST NOT be relabelled as passing on that arm.
"""
from pathlib import Path
import json, math, re, sys, hashlib

def check(cond, msg):
    if not cond:
        raise AssertionError("H6_RG_FACTORIAL_REFUSED " + msg)

def events(path):
    b = path.read_bytes()
    check(b and b.endswith(b"\n"), str(path)+" truncated native log")
    records = []
    pids = set()
    timestamp = -1
    for no, ln in enumerate(b.decode("utf-8").splitlines(), 1):
        check(ln.startswith("H6 event="), f"{path}:{no} non-native event")
        m = re.search(r" h6_pid=([0-9]+) h6_ns=([0-9]+)$", ln)
        check(m is not None, f"{path}:{no} missing native provenance")
        pids.add(m.group(1))
        t = int(m.group(2))
        check(t >= timestamp, f"{path}:{no} time out of order")
        timestamp = t
        row = dict(re.findall(r"(?<!\\S)([A-Za-z_0-9]+)=([^ ]+)", ln))
        row["_line"] = no
        records.append(row)
    check(len(pids) == 1, str(path)+" mixed native process IDs")
    return records

def only(e, name, **match):
    found = [r for r in e if r.get("event") == name and
             all(r.get(k) == v for k, v in match.items())]
    check(len(found) == 1, f"expected single {name} {match}, got {len(found)}")
    return found[0]

def omega(e):
    r = only(e, "body", step="2", phase="after_integrate_and_collide_before_cleanup")
    w = [float(v) for v in r["omega"].split(",")]
    check(len(w) == 3 and all(math.isfinite(v) for v in w), "invalid omega")
    return math.sqrt(sum(v*v for v in w)), r

def arm(root, name):
    p = root/name
    check((p/"F/native.log").is_file(), name+" F missing native logs")
    f = events(p/"F/native.log")
    others = {a:events(p/a/"native.log") for a in ("A","P","B")}
    af = only(f,"armed",mode="F")
    bd = only(f,"intervention_boundary",mode="F")
    check(af.get("contacts") == "2" and bd.get("before") == "2",
          name+" old contacts not armed")
    check(af["_line"] < bd["_line"], name+" inverted experiment")
    w, after = omega(f)
    wa,_ = omega(others["A"]); wp,_ = omega(others["P"]); wb,_ = omega(others["B"])
    check(wa > 0.25 and abs(wa-wp) <= 1e-12 and wb <= 1e-9,
          name+" control physics changed")
    for a,e in others.items():
        check(only(e,"armed",mode=a).get("contacts") == "2",
              name+" control "+a+" not armed")
        check(not any(x["event"]=="webots_reset_cleanup" for x in e),
              name+" leaked R into control "+a)
    sol = [x for x in f if x.get("event")=="solver_member" and x.get("id") in ("3","4")]
    cleanup = [x for x in f if x.get("event")=="cleanup" and x.get("enabled")=="0"
               and x.get("count")=="2" and af["_line"]<x["_line"]<bd["_line"]]
    revents = [x for x in f if x.get("event")=="webots_reset_cleanup"]
    cfg = {"A00":(0,0),"G01":(0,1),"R10":(1,0),"RG11":(1,1)}[name]
    r_on,g_on = cfg
    if g_on:
        check(len(cleanup)==1, name+" G did not actually clear disabled group")
        check(bd.get("currently")=="0", name+" G not effective before R")
    else:
        check(len(cleanup)==0 and bd.get("currently")=="2",
              name+" G accidentally active")
    if r_on:
        check(len(revents)==1 and revents[0]["_line"]>bd["_line"],
              name+" R missing or out of order")
        expected_removed = 0 if g_on else 2
        check(revents[0].get("removed")==str(expected_removed),
              name+" R joint count not "+str(expected_removed))
    else:
        check(len(revents)==0, name+" R active with flag off")
    if not r_on and not g_on:
        check(abs(w-wa)<=1e-12 and len(sol)>=2 and after.get("nold_current")=="2",
              "A00 negative control failed")
    else:
        check(w<=1e-9 and len(sol)==0 and after.get("nold_current")=="0",
              name+" residual physical old contacts")
    # Ensure F actually ended normally, even if the historical postprocessing
    # rejects its changed semantics. A failed underlying native process is never valid.
    rc_file=p/"F/process_exit_code.txt"
    check(rc_file.is_file() and rc_file.read_text().strip()=="0",
          name+" native Webots did not exit normally")
    ctrl = p/"F/controller.jsonl"
    check(ctrl.is_file() and ctrl.read_text().splitlines()[-1] ==
          "H6_CONTROLLER end_of_one_shot_experiment",name+" supervisor incomplete")
    return {
        "R":r_on,"G":g_on,"armed_old_contacts":int(af["contacts"]),
        "at_reset_before_intervention":int(bd["before"]),
        "at_R_boundary":int(bd["currently"]),
        "G_retired_cleanup_events":len(cleanup),
        "R_detached_contacts":int(revents[0]["removed"]) if revents else 0,
        "old_solver_records":len(sol),
        "old_after_next_step":int(after["nold_current"]),
        "omega_rad_s":w,"baseline_A_omega_rad_s":wa,
        "historical_runner_exit":(p.parent.parent/"logs"/(name+"-run.exit")).read_text().strip()
            if (p.parent.parent/"logs"/(name+"-run.exit")).exists() else "NOT_RECORDED",
        "F_native_log_sha256":hashlib.sha256((p/"F/native.log").read_bytes()).hexdigest(),
    }

def main(root):
    names=("A00","G01","R10","RG11")
    result={name:arm(root,name) for name in names}
    a=result["A00"]["omega_rad_s"]
    check(all(abs(result[n]["baseline_A_omega_rad_s"]-a)<=1e-12 for n in names),
          "baseline drift across processes")
    check(result["G01"]["R_detached_contacts"]==0 and
          result["RG11"]["R_detached_contacts"]==0,
          "R falsely credited for G effect")
    out={
      "scope":"H6 SYNTHETIC only; single-thread pinned Webots R2025a",
      "factorial":result,
      "mechanism":"G before R in retired-buffer scenario; R independently effective",
      "oracle":"H6_RG_FACTORIAL_PASS",
      "general_G_nonregression":"UNPROVEN",
      "joint_lifetime_in_full_Webots":"UNPROVEN",
      "ordinary_no_RESET_physics":"UNPROVEN",
      "cross_body_current_buffer":"UNPROVEN",
      "multi_thread":"UNPROVEN",
      "P5_historical_RESET_TIMEOUT":"UNPROVEN",
      "production":"NO_GO"
    }
    (root/"factorial_verdict.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out,indent=2,sort_keys=True))
    print("H6_RG_FACTORIAL_PASS")

if __name__=="__main__":
    check(len(sys.argv)==2,"usage: h6_rg_factorial_oracle.py ROOT")
    main(Path(sys.argv[1]))
