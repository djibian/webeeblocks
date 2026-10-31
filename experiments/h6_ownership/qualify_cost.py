#!/usr/bin/env python3
"""Fail-closed bounded comparison of exact source-pinned native ODE benchmark.

The empirical comparisons do NOT imply global MT/ABI, Webots-QHash or plugin
ownership guarantees; this summarizes observed standalone processes only.
"""
import json,statistics,sys
from pathlib import Path
if len(sys.argv)!=3:
    raise SystemExit("usage: qualify_cost.py RAW_JSONL REPORT_JSON")
raw=Path(sys.argv[1]); report=Path(sys.argv[2])
lines=[json.loads(x) for x in raw.read_text().splitlines() if x.strip()]
modes=("shared","individual","notify","singleton")
sizes=(1,8,64,256)
trials=7
errors=[]
for m in modes:
    for n in sizes:
        samples=[x for x in lines if x["mode"]==m and x["n"]==n]
        if len(samples)!=trials:
            errors.append(f"nonmatching sample count {m} {n}: {len(samples)}")
for x in lines:
    m=x["mode"];n=x["n"];invalid=x["invalid"]
    expectedAlive=n if m=="shared" else n-invalid
    if x["alive_after_selective"]!=expectedAlive:
        errors.append(f"bad selective result {m} {n} {x['repeat']}")
    if m=="notify" and (x["hook_pre"]!=n+invalid or
                        x["hook_post"]!=n+invalid or
                        x["hook_registered"]!=n+invalid):
        # First wave: n total; invalid subset then retire other subset = n.
        # Second wave: n again; total 2n notifications.
        errors.append(f"unmatched callback counts {n} {x['repeat']}")
    if x["after_empty"]["alive"]!=0 or x["after_reuse"]["alive"]!=0:
        errors.append(f"nonempty final cleanup {m} {n} {x['repeat']}")
    if x["peak"]["alive"]!=n or x["after_refill"]["alive"]!=n:
        errors.append(f"missing newly created contacts {m} {n} {x['repeat']}")
    for k in ("create_us","step_us","selective_us","wake_us","retire_us","reuse_us","teardown_us"):
        if not 0 <= x[k] < 30_000_000:
            errors.append(f"bad timing {m} {n} {x['repeat']} {k}")
    for phase in ("before","peak","after_selective","after_empty","after_refill","after_reuse","after_destroy"):
        for name in ("active","reserved","rss"):
            if x[phase][name]<0:errors.append(f"bad measure {m} {n} {phase}")
# Baseline shared group has physically retained ALL n after dJointDestroy,
# whereas the other modes must have released their selectively invalid n/2.
def med(xs):return statistics.median(xs)
def mad(xs):return statistics.median(abs(x-med(xs)) for x in xs)
metrics=("create_us","step_us","selective_us","wake_us","retire_us","reuse_us","teardown_us")
summary={}
for m in modes:
    summary[m]={}
    for n in sorted({x["n"] for x in lines if x["mode"]==m}):
        xs=[x for x in lines if x["mode"]==m and x["n"]==n]
        q={}
        q["repeats"]=len(xs)
        for k in metrics:
            v=[x[k] for x in xs]
            q[k]={"median_us":med(v),"mad_us":mad(v),"min_us":min(v),"max_us":max(v)}
        for phase in ("peak","after_selective","after_empty","after_refill","after_reuse","after_destroy"):
            for k in ("active","reserved","rss"):
                v=[x[phase][k]-x["before"][k] for x in xs]
                q[f"{phase}_{k}_delta_bytes"]={"median":med(v),"min":min(v),"max":max(v)}
        q["selective_possible"]=m!="shared"
        summary[m][str(n)]=q
# Benchmark may reject with errors, but never suppress data or claim success.
document={"pin":"c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b",
 "scope":"native pinned bundled ODE; 1+1 fixed contact body world; no full Webots or Qt QHash; single-thread subprocess samples",
 "n_processes":len(lines),
 "mode_list":list(modes),
 "sizes":list(sizes),
 "trials_per_mode_size":trials,
 "includes_optional_1024":[x["n"] for x in lines if x["n"]==1024].__len__(),
 "errors":errors,"verdict":"PASS" if not errors else "FAIL",
 "summary":summary}
report.write_text(json.dumps(document,indent=2,sort_keys=True)+"\n")
print(f"H6_BENCH_QUALIFICATION {document['verdict']} samples={len(lines)} errors={len(errors)}")
for m in modes:
    if "256" not in summary[m]:continue
    t=summary[m]["256"]
    print(f"H6_BENCH_256 {m} create_med_us={t['create_us']['median_us']:.3f} "
          f"step_med_us={t['step_us']['median_us']:.3f} "
          f"peak_active_delta={t['peak_active_delta_bytes']['median']} "
          f"peak_reserved_delta={t['peak_reserved_delta_bytes']['median']} "
          f"peak_rss_delta={t['peak_rss_delta_bytes']['median']} "
          f"after_empty_active_delta={t['after_empty_active_delta_bytes']['median']}")
if errors:raise SystemExit("H6_BENCH_QUALIFICATION_REJECT")
