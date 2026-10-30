#!/usr/bin/env python3
"""H6-only independent switches R/G; mutate generated patcher, not upstream Webots.
Run after h6_attachment_cleanup_patch.py and BEFORE patch_webots_h6.py.
Fail closed on unexpected source shape. No production changes or oracle changes.
"""
from pathlib import Path
import hashlib
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: h6_rg_factorial_patch.py EXTRACTED_PAYLOAD")
p = Path(sys.argv[1]) / "source/patch_webots_h6.py"
raw = p.read_bytes()
s = raw.decode("utf-8")

# R only at the already existing F/reset boundary, conditional on its own flag.
r_old = '!std::strcmp(std::getenv("WEBEE_H6_MODE"), "F"))'
r_new = ('!std::strcmp(std::getenv("WEBEE_H6_MODE"), "F") && '
         'std::getenv("WEBEE_H6_R") && '
         '!std::strcmp(std::getenv("WEBEE_H6_R"), "1"))')
if s.count(r_old) != 1:
    raise SystemExit(f"H6 RG REFUSED R guard count {s.count(r_old)}")
s = s.replace(r_old, r_new, 1)

# G in BOTH retired buffers. Keep its existing H6 arm and F boundaries:
# this experiment does NOT qualify general-purpose G in ordinary Webots.
g_old = 'h6ArmedBody && h6Mode() && !std::strcmp(h6Mode(), "F")'
g_new = (g_old + ' && std::getenv("WEBEE_H6_G") && '
         '!std::strcmp(std::getenv("WEBEE_H6_G"), "1")')
if s.count(g_old) != 2:
    raise SystemExit(f"H6 RG REFUSED G guard count {s.count(g_old)}")
s = s.replace(g_old, g_new)
if s.count(g_new) != 2 or s.count(r_new) != 1:
    raise SystemExit("H6 RG REFUSED independent guard postcondition")
if "dJointAttach(joint, 0, 0);" not in s:
    raise SystemExit("H6 RG REFUSED attachment-selective R is missing")
compile(s, str(p), "exec")
p.write_text(s)
print("H6 RG independent factors:", "R guard=1", "G guards=2",
      "generator_sha256="+hashlib.sha256(p.read_bytes()).hexdigest())
