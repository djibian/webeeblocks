#!/usr/bin/env python3
"""Strict evidence audit. A/R are plugin-level, NOT G or core Webots R/G factorial."""
import hashlib
import json
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: qualify_native.py EVIDENCE_ROOT")
root = Path(sys.argv[1])
result = {"classification": "NATIVE_SUPERVISOR_PLUGIN_OBSERVATION_ONLY",
          "core_Webots_R_G_tested": False, "cases": {}, "errors": []}
for path in ("global", "node"):
    for arm in ("A", "R"):
        spec = path + "-" + arm
        loc = root / spec
        try:
            code = int((loc / "exit_code.txt").read_text().strip())
            raw = (loc / "native.log").read_text()
            ctrl = (loc / "webots.log").read_text()
            rows = [line for line in raw.splitlines() if line.startswith("H6_G_WINDOW ")]
            pre = [x for x in rows if "event=pre " in x]
            bound = [x for x in rows if "event=reset_boundary " in x]
            must = [x for x in rows if "event=plugin_init " in x]
            if code != 0 or len(must) != 1 or len(bound) != 1 or len(pre) < 40:
                raise ValueError(f"incomplete native evidence exit={code} init={len(must)} bound={len(bound)} pre={len(pre)}")
            if f"controller=complete path={path}" not in ctrl:
                raise ValueError("Supervisor controller completion missing")
            if "event=plugin_cleanup " not in raw:
                raise ValueError("native plugin cleanup missing")
            previous = [x for x in pre if "reset=0 " in x and
                        int(re.search(r"contacts=(\d+)", x).group(1)) > 0]
            if not previous:
                raise ValueError("no real contact observed before reset")
            bc = int(re.search(r"active_attached=(\d+)", bound[0]).group(1))
            interventions = len([x for x in rows if "event=r_detach " in x])
            if arm == "A" and interventions:
                raise ValueError("baseline was not observational")
            if arm == "R" and bc and not interventions:
                raise ValueError("plugin R required but did not act")
            result["cases"][spec] = {
                "exit": code, "steps_pre": len(pre), "contacts_before_reset": len(previous),
                "contacts_attached_at_reset_boundary": bc, "plugin_r_detach": interventions,
                "log_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            }
        except (ValueError, OSError, AttributeError) as e:
            result["errors"].append(f"{spec}: {e}")
(root / "native_verdict.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
if result["errors"]:
    raise SystemExit("REFUSED: missing native proof (not proof of G sufficiency or R necessity)")
