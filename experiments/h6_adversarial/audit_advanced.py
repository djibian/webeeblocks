#!/usr/bin/env python3
"""Adversarial review of immutable exact candidate 2fa498... native Webots evidence.
No original oracle changes, no green == physical success inference.
"""
from pathlib import Path
import hashlib,json,re,sys
root=Path(sys.argv[1])
OUT=Path(sys.argv[2])
HEAD="2fa4984242230659d6d4f688480fc6f09e65fc84"
WEBOTS="c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
def fail(msg):raise RuntimeError("H6_ADVERSARIAL_REFUSED "+msg)
lines=(root/"SHA256SUMS.txt").read_text().splitlines()
seen=set()
for line in lines:
    sha,p=line.split("  ",1)
    if not p.startswith("evidence/advanced/"):fail("unknown manifest path: "+p)
    name=p.removeprefix("evidence/advanced/")
    if name in seen:fail("duplicate manifest "+name)
    seen.add(name)
    if not (root/name).is_file():fail("missing "+name)
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:fail("sha mismatch "+name)
observed={str(x.relative_to(root)) for x in root.rglob("*") if x.is_file()}
if observed!=seen|{"SHA256SUMS.txt"}:fail("unexpected/unlisted evidence")
if (root/"commit.txt").read_text().strip()!=HEAD:fail("original run head")
if (root/"observed-commit.txt").read_text().strip()!=HEAD:fail("observed head")
if (root/"observed-pin.txt").read_text().strip()!=WEBOTS:fail("Webots pin")
patch=(root/"native-rg-mt-trace.patch").read_text()
files=set(re.findall(r"^diff --git a/(\S+)",patch,re.M))
if files!={"src/webots/engine/WbSimulationCluster.cpp",
          "src/webots/nodes/WbSolid.cpp",
          "src/webots/ode/WbOdeContext.cpp",
          "src/webots/ode/WbOdeContext.hpp"}:fail("unapproved native diff")
if patch.count('const bool h6G = std::getenv("H6_NATIVE_G")')!=2:fail("not G candidate")
q=json.loads((root/"advanced_qualification.json").read_text())
if len(q["arms"])!=16 or len(q["contrasts"])!=4 or q["errors"]:fail("not full successful original")
arms={}
for t in (1,2):
  for path in ("global","node"):
    for arm in ("A","R","G","RG"):
      key=f"t{t}-{path}-{arm}"
      folder=root/key
      if int((folder/"exit_code.txt").read_text())!=0:fail("nonzero process "+key)
      stdout=(folder/"webots.log").read_text()
      native=(folder/"native.log").read_text().splitlines()
      flagged=(folder/"flags.txt").read_text()
      for expected in [f"threads={t}",f"path={path}",f"arm={arm}",
                        f"r={int('R' in arm)}",f"g={int('G' in arm)}"]:
          if expected not in flagged:fail("flags "+key+" "+expected)
      if sum("event=plugin_cleanup ticks=44 reset_seen=1" in s for s in native)!=1:fail("missing 44 native steps "+key)
      if sum("event=pre tick=" in s for s in native)!=44:fail("missing pre steps "+key)
      retire=[x for x in stdout.splitlines() if "H6_NATIVE_G event=retire " in x]
      disabled=sum("owner_enabled=0" in x for x in retire)
      real_g=sum("owner_enabled=0" in x and "g=1" in x for x in retire)
      if not retire:fail("no group retired "+key)
      if int(q["arms"][key]["R_removed"])!=(8 if "R" in arm else 0):fail("R observation "+key)
      arms[key]={"retired_groups":len(retire),"disabled_owner_events":disabled,
                 "actual_G_extra_empty_calls":real_g,
                 "omega":q["arms"][key]["omega_rad_s"]}
# Explicitly fail any global safety claim based on this green run:
for t in (1,2):
  for path in ("global","node"):
    if arms[f"t{t}-{path}-G"]["actual_G_extra_empty_calls"]!=0:
      fail("unexpected G-only activation; reconsider adversarial finding")
    if path=="node":
      if q["contrasts"][f"t{t}-{path}"]["R_physical_suppression_observed"] is not False:
        fail("node baseline newly discriminating")
      if abs(arms[f"t{t}-{path}-A"]["omega"])>1e-15:
        fail("node control became nonzero")
    else:
      if not q["contrasts"][f"t{t}-{path}"]["R_physical_suppression_observed"]:
        fail("global not discriminating")
report={"reviewed_candidate":HEAD,"webots":WEBOTS,"original_run":41089341711,
        "verified_sha256_entries":len(seen),"verified_arms":len(arms),
        "falsification_found":{
          "G_only_diff_behavior_never_exercised":True,
          "node_R_physics_contrast_false_both_thread_modes":True,
          "original_advanced_workflow_was_green":True},
        "arm_observations":arms,
        "scope_limitations":[
          "Not proof of native Webots general G regression",
          "Configured ODE thread count does not prove an actual simultaneous reset/collision race",
          "No general memory bound or physical ordinary nonregression demonstrated"
        ]}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/"review.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
print("H6_ADVERSARIAL_COVERAGE_REFUTATION_PROVEN exact_head="+HEAD)
