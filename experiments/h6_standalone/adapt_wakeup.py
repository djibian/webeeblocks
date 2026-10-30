#!/usr/bin/env python3
"""Reuses the EXACT PR #756 wakeup world+plugin, with no G mutation.

Input setup_wakeup.py is read-only extracted at pinned PR756 SHA. Its solver
read-only observation is retained; the now-disproven unconditional-G post-swap
modification is removed (it is not part of the standalone candidate).
"""
from pathlib import Path
import hashlib,sys
if len(sys.argv)!=4:
 raise SystemExit("usage: adapt_wakeup.py PR756_SETUP LOCAL_WEBOTS OUTPUT_PROJECT")
reference,webots,out=map(Path,sys.argv[1:])
source=reference.read_text()
a="ctx=root/\"src/webots/ode/WbOdeContext.cpp\""
b="world=r'''#VRML_SIM R2025a utf8"
if source.count(a)!=1 or source.count(b)!=1:
 raise SystemExit("REFUSED wakeup fixture source changed")
start=source.index(a);end=source.index(b,start)
sanitized=source[:start]+source[end:]
check=source[start:end]
if "H6_WAKE_RETIRE_JOINT" not in check or "dJointGroupEmpty(it.value())" not in check:
 raise SystemExit("REFUSED not the pinned G-only injection block")
# First part must remain solver wrapper that calls dWorldStep exactly and returns it.
if "const int result=dWorldStep(world,dt)" not in sanitized:
 raise SystemExit("REFUSED noncanonical solver")
wrapper=out.parent/"wakeup_setup_no_g.py"
wrapper.write_text(sanitized)
print("H6_WAKEDATA_ORIGINAL",hashlib.sha256(reference.read_bytes()).hexdigest())
print("H6_WAKEDATA_ADAPTED",hashlib.sha256(wrapper.read_bytes()).hexdigest())
import subprocess
subprocess.run([sys.executable,str(wrapper),str(webots),str(out)],check=True)
