#!/usr/bin/env python3
"""Four native Supervisor/ODE A vs plugin-R arms, fail-closed and physical.
This is NOT core G proof: use core_qualify.py for G factor.
"""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

if len(sys.argv)!=2:
    raise SystemExit("usage: qualify_native.py EVIDENCE_ROOT")
root=Path(sys.argv[1])
result={"classification":"NATIVE_SUPERVISOR_PLUGIN_OBSERVATION_ONLY",
        "core_Webots_R_G_tested":False,"cases":{},"errors":[]}

def get(line):
    return dict(re.findall(r"([a-z_]+)=([^\s]+)",line))
def require(ok,why):
    if not ok: raise ValueError(why)
def one(rows,event,t):
    arr=[get(s) for s in rows if f"event={event} tick={t} " in s]
    require(len(arr)==1,f"missing/ambiguous {event}/{t}")
    return arr[0]
def norm(d):
    return math.sqrt(sum(float(d["w"+c])**2 for c in ("x","y","z")))

for path in ("global","node"):
    pairs={}
    for arm in ("A","R"):
        spec=f"{path}-{arm}"
        folder=root/spec
        try:
            code=int((folder/"exit_code.txt").read_text())
            raw=(folder/"native.log").read_bytes()
            ctrl=(folder/"webots.log").read_text(errors="replace")
            require(code==0 and raw.endswith(b"\n"),"nonzero exit or truncated native trace")
            rows=raw.decode().splitlines()
            require(len([x for x in rows if "event=plugin_init" in x])==1,
                    "plugin initialization missing")
            require(len([x for x in rows if "event=plugin_cleanup ticks=44 reset_seen=1" in x])==1,
                    "not all 44 native physics steps finished and cleaned")
            require(f"controller=requested path={path}" in ctrl and
                    f"controller=about_to_reset path={path}" in ctrl,
                    "Supervisor real API request not authenticated")
            prior=one(rows,"pre",36); first=one(rows,"pre",37); nextp=one(rows,"pre",38)
            post=one(rows,"post",37 if path=="global" else 38)
            require(int(prior["contacts"])>0 and prior["reset"]=="0", "no prior real collision")
            require(first["reset"]=="1" and int(first["contacts"])==4 and float(first["z"])>0.7,
                    "no four prior contacts at reset")
            require(int(first["enabled"])==(1 if path=="global" else 0),"bad enabled transition")
            require(int(nextp["enabled"])==1,"reactivation absent")
            require(all(abs(float(first[k]))<1e-9 for k in ("vx","vy","vz","wx","wy","wz")),
                    "pre-intervention velocities not reset")
            detaches=len([x for x in rows if "event=r_detach tick=37" in x])
            require(detaches==(4 if arm=="R" else 0), "R detachment mismatch")
            v=norm(post)
            require(v>0.1 if arm=="A" else v<1e-8, "physical contrast falsified")
            pairs[arm]=(first,v)
            result["cases"][spec]={
                "process_exit":code,"pre_reset_contacts":int(first["contacts"]),
                "enabled_at_reset":int(first["enabled"]),
                "contact_count_after_reenable":int(nextp["contacts"]),
                "omega_rad_s":v,"detach_count":detaches,
                "native_log_sha256":hashlib.sha256(raw).hexdigest()}
        except (ValueError,KeyError,OSError) as exc:
            result["errors"].append(spec+": "+str(exc))
    if len(pairs)==2:
        for key in ("enabled","contacts","x","y","z","vx","vy","vz","wx","wy","wz"):
            try:
                require(abs(float(pairs["A"][0][key])-float(pairs["R"][0][key]))<1e-8,
                        path+": pre-intervention A/R "+key+" differs")
            except (ValueError,KeyError) as exc:
                result["errors"].append(str(exc))
(root/"native_verdict.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
if result["errors"]:
    raise SystemExit("REFUSED incomplete real native A/R evidence")
