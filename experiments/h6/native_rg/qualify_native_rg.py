#!/usr/bin/env python3
"""Exact native 8-arm factorial: Webots core R/G, read-only plugin, no oracle weakening."""
import json, math, pathlib, re, sys
root=pathlib.Path(sys.argv[1])
def need(ok,why):
    if not ok: raise RuntimeError("NATIVE_RG_REFUSED "+why)
def fields(line): return dict(re.findall(r"([a-z_]+)=([^\s]+)",line))
def value(d): return math.sqrt(sum(float(d["w"+axis])**2 for axis in "xyz"))
out={"scope":"Webots R2025a pinned, real Supervisor global/node, native R/G core, one thread",
     "source_pin":"c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b","arms":{},"contrasts":{},"errors":[]}
data={}
for path in ("global","node"):
    for arm in ("A","R","G","RG"):
        spec=path+"-"+arm;folder=root/spec
        try:
            native=(folder/"native.log").read_text()
            webots=(folder/"webots.log").read_text()
            flags=(folder/"flags.txt").read_text()
            need(int((folder/"exit_code.txt").read_text())==0,spec+" process exit")
            need("H6_G_WINDOW event=plugin_cleanup ticks=44 reset_seen=1" in native,spec+" incomplete native steps")
            need("controller=requested path="+path in webots,spec+" missing real Supervisor reset")
            need("controller=complete path="+path in webots,spec+" incomplete Supervisor")
            need(f"g={int('G' in arm)} r={int('R' in arm)} path={path}" in flags,spec+" wrong arm")
            traces=[fields(s) for s in native.splitlines() if "event=pre " in s]
            posts=[fields(s) for s in native.splitlines() if "event=post " in s]
            need(len(traces)==44 and len(posts)==44,spec+" count")
            need(all(int(x["tick"])==i+1 for i,x in enumerate(traces)),spec+" steps nonmonotone")
            near=next(x for x in traces if x["tick"]=="37")
            after=next(x for x in posts if x["tick"]==("37" if path=="global" else "38"))
            need(near["reset"]=="1" and float(near["z"])>0.7,spec+" wrong RESET")
            retire=[fields(s) for s in webots.splitlines() if "H6_NATIVE_G event=retire " in s]
            rr=[fields(s) for s in webots.splitlines() if "H6_NATIVE_R event=detach " in s]
            # At least one group must contain a native contact on real collision.
            need(any(int(x["count"])>0 for x in retire),spec+" no contact group")
            need(all(int(x["g"])==int("G" in arm) for x in retire),spec+" wrong G")
            if "R" in arm:
                need(any(int(x["removed"])>0 for x in rr),spec+" R never invalidated a live contact")
            else:
                need(not rr,spec+" R executed in control")
            data[spec]={"omega":value(after),"p37":near,"retire":len(retire),
                         "disabled_retire":sum(x["owner_enabled"]=="0" for x in retire),
                         "reset_R_removed":sum(int(x["removed"]) for x in rr),
                         "pre_reset_contacts":int(near["contacts"]),
                         "native_input_step_count":len(traces)}
            out["arms"][spec]={k:v for k,v in data[spec].items() if k!="p37"}
        except Exception as exc:out["errors"].append(spec+": "+str(exc))
for path in ("global","node"):
    if any(path+"-"+arm not in data for arm in ("A","R","G","RG")): continue
    omega={arm:data[path+"-"+arm]["omega"] for arm in ("A","R","G","RG")}
    ref=data[path+"-A"]["p37"]
    for arm in ("R","G","RG"):
        cmp=data[path+"-"+arm]["p37"]
        for k in ("x","y","z","vx","vy","vz","wx","wy","wz"):
            if abs(float(ref[k])-float(cmp[k]))>1e-8:out["errors"].append(path+" "+arm+" pre-37 mismatch "+k)
    if omega["A"]<0.1:out["errors"].append(path+": no actual baseline physics parasite")
    if omega["R"]>1e-7 or omega["RG"]>1e-7:out["errors"].append(path+": core R failed to remove parasite")
    if path=="global" and omega["G"]<0.1:out["errors"].append("global G-only unexpectedly fixed; check original control")
    out["contrasts"][path]={"omega_rad_s":omega, "R_suppresses":omega["R"]<1e-7 and omega["RG"]<1e-7,
                            "G_alone_sufficient":omega["G"]<1e-7}
outpath=root/"native_rg_qualification.json"
outpath.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(json.dumps(out,indent=2,sort_keys=True))
need(not out["errors"]," ; ".join(out["errors"]))
need(len(out["contrasts"])==2,"missing both native RESET paths")
print("H6_NATIVE_RG_FACT_PASS")
