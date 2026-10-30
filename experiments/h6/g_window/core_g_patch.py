#!/usr/bin/env python3
"""Source-pinned experimental G only, bounded to retired-group cleanup.

The baseline A remains Webots upstream exact; G only changes disabled OWNER
cleanup after cluster buffer swap. Fail closed on source changes. Each run
selects G via H6_G_CORE=1, not an instrumentation-time source rebuild.
"""
from pathlib import Path
import hashlib
import subprocess
import sys

PIN="c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
ORIGINAL="f5fc3eee26cfc2bfedd32fe31b6636e526c9ea6779930496613c6a60558e7387"
if len(sys.argv)!=2:
    raise SystemExit("usage: core_g_patch.py WEBOTS_SOURCE_ROOT")
root=Path(sys.argv[1])
if subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()!=PIN:
    raise SystemExit("REFUSED wrong Webots pin")
p=root/"src/webots/ode/WbOdeContext.cpp"
s=p.read_text()
if hashlib.sha256(s.encode()).hexdigest()!=ORIGINAL:
    raise SystemExit("REFUSED source SHA mismatch")
if s.count("#include <cassert>")!=1:
    raise SystemExit("REFUSED include insertion ambiguity")
s=s.replace("#include <cassert>","#include <cassert>\n#include <cstdlib>\n#include <cstring>\n#include <cstdio>")
needle="    if (dBodyIsEnabled(it.key()))\n      dJointGroupEmpty(it.value());"
if s.count(needle)!=2:
    raise SystemExit("REFUSED enabled-only cleanup count != 2")
for group in ("1","2"):
    marker="void WbOdeContext::emptyEnabledBodyContactJointGroups"+group+"() {"
    if s.count(marker)!=1:
        raise SystemExit("REFUSED group method missing")
    start=s.index(marker)
    anchor=s.index(needle,start)
    if s.find("}",start)<anchor:
        # first closing brace may be the iterator loop one: anchor must be before it
        raise SystemExit("REFUSED group anchor out of loop")
    replacement=(
        "    const bool h6g = std::getenv(\"H6_G_CORE\") && !std::strcmp(std::getenv(\"H6_G_CORE\"), \"1\");\n"
        "    const int h6count = static_cast<int>(dJointGroupGetCount(it.value()));\n"
        "    if (std::getenv(\"H6_G_CORE_TRACE\") && h6count > 0) {\n"
        "      std::fprintf(stderr, \"H6_CORE event=retire group="+group+" enabled=%d contacts=%d g=%d\\n\",\n"
        "                   static_cast<int>(dBodyIsEnabled(it.key())), h6count, static_cast<int>(h6g));\n"
        "      std::fflush(stderr);\n"
        "    }\n"
        "    if (dBodyIsEnabled(it.key()) || h6g)\n"
        "      dJointGroupEmpty(it.value());"
    )
    s=s[:anchor]+replacement+s[anchor+len(needle):]
if s.count("H6_CORE event=retire")!=2 or "const bool h6g" not in s:
    raise SystemExit("REFUSED instrumentation postcondition")
p.write_text(s)
print("H6_EXACT_PIN",PIN)
print("H6_EXACT_G_PATCH_SHA256",hashlib.sha256(p.read_bytes()).hexdigest())
