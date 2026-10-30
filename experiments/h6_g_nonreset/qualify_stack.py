#!/usr/bin/env python3
"""Native non-RESET G retirement: real two-dynamic-body stack on static floor.

No confidence inflation: G must actually remove contacts A preserves, and
ordinary collision/sleep and trajectory must be observed for all six arms.
"""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: qualify_stack.py EVIDENCE_DIRECTORY")
root=Path(sys.argv[1])
logs=root/"logs"
out={"scope":"Webots R2025a pinned; gravity, two dynamic Box solids stacked on static floor, 1-thread, no RESET",
     "experiment_commit":(root/"experiment_commit.txt").read_text().strip(),
     "runs":{},"errors":[],
     "inference":"G physical safety is conditional and NOT universally established"}

def require(p, msg):
    if not p:
        raise ValueError(msg)

def rowdata(arm,trial):
    spec=f"stack-A{arm}-trial{trial}"
    raw=(logs/f"stack-webots-A{arm}-trial{trial}.log").read_text(errors="replace")
    trace=(logs/f"stack-trace-A{arm}-trial{trial}.jsonl").read_bytes()
    require(trace.endswith(b"\n"),spec+": incomplete record")
    lines=trace.decode().splitlines()
    rows=[json.loads(line[len("H6_G_STEP "):]) for line in lines if line.startswith("H6_G_STEP {")]
    require(len(rows)==140 and [r["frame"] for r in rows]==list(range(140)),spec+": wrong 140-frame proof")
    require([r["arm"] for r in rows]==[str(arm)]*140,spec+": wrong arm")
    require(lines.count(f"H6_G_NONRESET_DONE arm={arm}")==1,spec+": completion absent")
    require(not any("H6_G_FATAL" in line or "Traceback (most recent call last)" in line for line in raw.splitlines()),
            spec+": native fatal")
    events=[]
    for line in raw.splitlines():
        if "H6_G_EFFECT retired=1 owner_disabled=1" not in line:
            continue
        match=re.fullmatch(r"H6_G_EFFECT retired=1 owner_disabled=1 before=(\d+) after=(\d+) arm=(A|G)",line)
        require(match is not None, spec+": malformed G native effect record")
        before,after,mode=int(match[1]),int(match[2]),match[3]
        require(before>0 and mode==("A" if arm==0 else "G"),spec+": invalid G arm")
        require(after==(before if arm==0 else 0),spec+": G not behaving as claimed")
        events.append((before,after))
    old=[line for line in raw.splitlines() if "H6_G_CONTACT owner_disabled=1" in line]
    active=sum(int(re.search(r"active_other_contacts=(\d+)",l).group(1))>0 for l in old)
    return rows,{"retired_disabled_owner_groups":len(events),
        "contacts_retained_A_or_cleaned_G":sum(x[0] for x in events),
        "net_contacts_removed":sum(x[0]-x[1] for x in events),
        "active_other_contact_events":active,
        "raw_log_sha256":hashlib.sha256(raw.encode()).hexdigest(),
        "trace_sha256":hashlib.sha256(trace).hexdigest()}

for trial in (1,2,3):
    pair={}
    for arm in (0,1):
        try:
            pair[arm],d=rowdata(arm,trial)
            out["runs"][f"trial{trial}-A{arm}"]=d
        except (ValueError,KeyError,AttributeError,FileNotFoundError,IndexError) as e:
            out["errors"].append(f"trial{trial}-A{arm}: {e}")
    if len(pair)!=2:
        continue
    dr=[];dv=[]
    for x,y in zip(pair[0],pair[1]):
        try:
            require(x["frame"]==y["frame"] and x["time"]==y["time"],"A/G clock difference")
            dr.append(math.sqrt(sum((x[k][i]-y[k][i])**2 for k in ("a_position","b_position") for i in range(3))))
            dv.append(math.sqrt(sum((x[k][i]-y[k][i])**2 for k in ("a_velocity","b_velocity") for i in range(6))))
        except (ValueError,KeyError,IndexError) as e:
            out["errors"].append(f"trial{trial}: {e}")
            break
    if dr and dv:
        out["runs"][f"trial{trial}-contrast"]={
            "max_position_difference_m":max(dr),
            "max_six_dof_velocity_difference":max(dv),
            "first_position_difference_frame":next((i for i,x in enumerate(dr) if x>1e-10),None)}
a=sum(out["runs"].get(f"trial{t}-A0",{}).get("contacts_retained_A_or_cleaned_G",0) for t in (1,2,3))
g=sum(out["runs"].get(f"trial{t}-A1",{}).get("net_contacts_removed",0) for t in (1,2,3))
active=sum(out["runs"].get(f"trial{t}-A1",{}).get("active_other_contact_events",0) for t in (1,2,3))
out.update(A_retained_contact_count=a,G_destroyed_contact_count=g,active_other_contact_events=active)
if a==0 or g==0:
    out["verdict"]="UNPROVEN_NO_G_INTERVENTION"
    out["errors"].append("No naturally retired disabled-owner contact group was altered by G")
elif len(out["errors"])==0:
    out["verdict"]="G_EXERCISED_SCOPE_BOUNDED_PHYSICAL_CONTRAST"
(root/"stack_qualification.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(json.dumps(out,indent=2,sort_keys=True))
if out["errors"]:
    raise SystemExit("REFUSED incomplete or non-discriminant native G stack campaign")
