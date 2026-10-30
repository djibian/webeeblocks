#!/usr/bin/env python3
"""Falsifiable eight-arm native A/G/R/RG qualification, exact-pinned Webots source.
G is native retired-buffer cleanup; R is equivalent selective attached contact
detach at pre-solver physics plugin boundary; this is NOT production qualification.
"""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: core_qualify.py CORE_EVIDENCE_ROOT")
root = Path(sys.argv[1])
out = {"scope": "ONE_SYNTHETIC_WORLD_TWO_REAL_SUPERVISOR_PATHS_ONE_THREAD",
       "g": "native Webots source modification retired disabled owner cleanup",
       "r": "ODE-contact attachment-selective plugin intervention before solver",
       "source_pin_required": "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b",
       "arms": {}, "contrasts": {}, "errors": [],
       "R_necessary_in_Webots": "UNPROVEN",
       "G_alone_physically_sufficient": "UNPROVEN"}

def require(test, reason):
    if not test:
        raise ValueError(reason)

def parse_values(line):
    return dict(re.findall(r"([a-z_]+)=([^\s]+)", line))

def norm(v):
    return math.sqrt(sum(x*x for x in v))

def vec(d):
    return [float(d["w"+x]) for x in ("x","y","z")]

def read(path, arm):
    spec = path+"-"+arm
    folder = root / spec
    require((folder/"flags.txt").is_file(), spec+": missing flags")
    flags=(folder/"flags.txt").read_text()
    expect_g=arm in ("G","RG")
    expect_r=arm in ("R","RG")
    require(f"g={int(expect_g)} r={int(expect_r)} path={path} " in flags, spec+": wrong arm flags")
    code=int((folder/"exit_code.txt").read_text().strip())
    require(code==0, spec+": native nonzero process exit "+str(code))
    raw=(folder/"native.log").read_bytes()
    require(raw.endswith(b"\n"), spec+": truncated native log")
    lines=raw.decode("utf-8").splitlines()
    require(len([s for s in lines if "event=plugin_init" in s]) == 1, spec+": not exactly one plugin init")
    require(len([s for s in lines if "event=plugin_cleanup ticks=44 reset_seen=1" in s])==1,
            spec+": incomplete 44 native steps")
    ctrl=(folder/"webots.log").read_text(errors="replace")
    require(f"controller=about_to_reset path={path} " in ctrl and
            f"controller=requested path={path}" in ctrl, spec+": no real Supervisor request")
    require("H6_CORE event=retire" in ctrl, spec+": missing native source G cleanup trace")
    core_events=[parse_values(s) for s in ctrl.splitlines() if "H6_CORE event=retire" in s]
    require(all(e["g"]==str(int(expect_g)) for e in core_events), spec+": source G switch mismatch")
    require(any(int(e["contacts"])>0 for e in core_events), spec+": no native retired contacts")
    def one(kind,tick):
        found=[parse_values(s) for s in lines if f"event={kind} tick={tick} " in s]
        require(len(found)==1, spec+f": {kind}/{tick} not unique: "+str(len(found)))
        return found[0]
    p36,p37,p38=one("pre",36),one("pre",37),one("pre",38)
    post37,post38=one("post",37),one("post",38)
    boundary=[parse_values(s) for s in lines if "event=reset_boundary" in s]
    require(len(boundary)==1 and boundary[0]["tick"]=="37", spec+": noncanonical reset boundary")
    require(int(p36["contacts"])>=1 and p36["reset"]=="0", spec+": no real prior collision")
    require(p37["reset"]=="1" and
            float(p37["z"]) > 0.7 and
            p37["contacts"]=="4" and
            boundary[0]["active_attached"]=="4", spec+": no four real old joints")
    require(all(abs(float(p37[k]))<1e-9 for k in ("vx","vy","vz","wx","wy","wz")),
            spec+": pre-solve reset velocity not zero")
    require(int(p37["enabled"])==(1 if path=="global" else 0),
            spec+": Supervisor path disabled/enable invariant violated")
    require(p38["enabled"]=="1",spec+": reactivation failed")
    detached=[parse_values(s) for s in lines if "event=r_detach " in s]
    require(len(detached)==(4 if expect_r else 0), spec+": incorrect R intervention count")
    if expect_r:
        require(all(d["tick"]=="37" for d in detached),spec+": R did not act pre-solver at reset")
        require(int(p38["contacts"])==0,spec+": R left old contacts attached")
    elif path=="node":
        # G may clear previous-frame disabled owner at t37 retirement:
        # its effect is the actual object of experiment, not assumed.
        require(int(p38["contacts"]) in (0,4),spec+": unexpected partial old contact count")
    return {"pre36":p36,"pre37":p37,"pre38":p38,"post37":post37,"post38":post38,
            "omega_after_global_or_reenabled":norm(vec(post37 if path=="global" else post38)),
            "contact_count_after_reenable":int(p38["contacts"]),
            "retire_events":len(core_events),
            "retire_disabled_events":len([e for e in core_events if e["enabled"]=="0"]),
            "detached":len(detached),"native_sha256":hashlib.sha256(raw).hexdigest(),
            "webots_log_sha256":hashlib.sha256(ctrl.encode()).hexdigest()}

for path in ("global","node"):
    cases={}
    for arm in ("A","G","R","RG"):
        try:
            entry=read(path,arm)
            cases[arm]=entry
            out["arms"][path+"-"+arm] = {k:v for k,v in entry.items()
                                        if k not in ("pre36","pre37","pre38","post37","post38")}
        except (ValueError,KeyError,TypeError,OSError) as e:
            out["errors"].append(path+"-"+arm+": "+str(e))
    if len(cases)!=4:
        continue
    try:
        ref=cases["A"]["pre37"]
        keys=("enabled","joints","contacts","x","y","z","vx","vy","vz","wx","wy","wz")
        for arm in ("G","R","RG"):
            for key in keys:
                x,y=float(ref[key]),float(cases[arm]["pre37"][key])
                require(abs(x-y)<1e-8,path+" pre-intervention mismatch "+arm+":"+key)
        omega={arm:cases[arm]["omega_after_global_or_reenabled"] for arm in cases}
        require(omega["A"]>0.1,path+": A did not produce physical parasite")
        require(omega["R"]<1e-8 and omega["RG"]<1e-8,path+": R did not suppress parasite")
        match=abs(omega["A"]-omega["G"])<=1e-8
        out["contrasts"][path]={
            "omega_rad_s":omega, "G_matches_A":match,
            "G_reproduces_parasite":omega["G"]>0.1,
            "R_suppresses":omega["R"]<1e-8 and omega["RG"]<1e-8,
            "pre_intervention_state_equal":True,
            "G_cleanup_actually_invoked":True}
    except ValueError as e:
        out["errors"].append(path+": "+str(e))
if not out["errors"] and len(out["contrasts"])==2:
    # Counterexample in real Webots global reset suffices to refute universal G.
    if any(v["G_reproduces_parasite"] for v in out["contrasts"].values()):
        out["G_alone_physically_sufficient"]="REFUTED_FOR_TESTED_REAL_WEBOTS_PATH"
        out["R_necessary_in_Webots"]="PROVEN_FOR_ATTACHMENT_CLEARING_ON_TESTED_PATH"
    else:
        out["G_alone_physically_sufficient"]="UNPROVEN_NO_COUNTEREXAMPLE_THIS_WORLD"
        out["R_necessary_in_Webots"]="UNPROVEN"
outpath=root/"factorial_verdict.json"
outpath.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(json.dumps(out,indent=2,sort_keys=True))
if out["errors"]:
    raise SystemExit("H6 CORE REFUSED incomplete/falsified 8-arm evidence")
