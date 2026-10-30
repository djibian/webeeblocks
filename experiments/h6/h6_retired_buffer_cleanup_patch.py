#!/usr/bin/env python3
"""Fail-closed patch: clean retired contact buffers in the H6-instrumented Webots source."""
from pathlib import Path
import hashlib
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: h6_retired_patch_preflight.py WEBOTS_SOURCE_ROOT")
root = Path(sys.argv[1])
p = root / 'src/webots/ode/WbOdeContext.cpp'
s = p.read_text()
if s.count('static dBodyID h6ArmedBody = nullptr;') != 1:
    raise SystemExit('H6 REFUSED native instrumentation absent')
needle = '    if (dBodyIsEnabled(it.key()))\n      dJointGroupEmpty(it.value());'
if s.count(needle) != 2:
    raise SystemExit(f'H6 REFUSED cleanup shape count={s.count(needle)} != 2')
# Mode F = qualified R, plus cleaning the retired buffer of disabled owners
# ONLY after armed RESET; baseline A/P/B unchanged. Production proposal differs.
replacement = '    if (dBodyIsEnabled(it.key()) || (h6ArmedBody && h6Mode() && !std::strcmp(h6Mode(), "F")))\n      dJointGroupEmpty(it.value());'
s2 = s.replace(needle, replacement)
if s2.count(replacement) != 2 or s2.count(needle):
    raise SystemExit('H6 REFUSED replacement count invalid')
p.write_text(s2)
print('H6 RETIRED CLEANUP', hashlib.sha256(p.read_bytes()).hexdigest())
