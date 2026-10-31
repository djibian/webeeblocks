#!/usr/bin/env python3
"""Test-only native H6 registry-key trace, no freed joint dereference.

Exactly applies PR766 Webots patch, then logs pointer/owner equality before
its existing delete path. Never interprets a freed ODE pointer's contents.
"""
import hashlib, subprocess, sys
from pathlib import Path
if len(sys.argv)!=2:raise SystemExit("usage: instrument_registry.py WEBOTS_ROOT")
root=Path(sys.argv[1])
subprocess.run([sys.executable,str(Path(__file__).parents[1]/"h6_standalone/patch_corrected.py"),str(root)],check=True)
ctx=root/"src/webots/ode/WbOdeContext.cpp"
s=ctx.read_text()
anchor='''    while (it.hasNext()) {
      it.next();
      dJointID joint = it.key();
      // A sleeping owner may hold an A-B contact while B is being destroyed.'''
if s.count(anchor)!=1:raise SystemExit("REFUSED: exact D1 destructor scanner not found")
replacement='''    while (it.hasNext()) {
      it.next();
      dJointID joint = it.key();
      // Observation only. The *value* is a raw stale-safe key, never dereferenced.
      std::fprintf(stderr,
        "H6_C_REGISTRY_SCAN joint=%p owner=%p victim=%p owner_is_victim=%d\\\\n",
        (void *)joint, (void *)it.value(), (void *)b, int(it.value() == b));
      std::fflush(stderr);
      // A sleeping owner may hold an A-B contact while B is being destroyed.'''
s=s.replace(anchor,replacement)
needle='''        it.remove();  // unregister before freeing: no stale pointer after free
        dJointDestroy(joint);'''
if s.count(needle)!=1:raise SystemExit("REFUSED: exact D1 free not found")
s=s.replace(needle,'''        std::fprintf(stderr, "H6_C_REGISTRY_FREE joint=%p owner=%p victim=%p\\\\n",
          (void *)joint, (void *)it.value(), (void *)b);
        std::fflush(stderr);
        it.remove();  // unchanged original registry cleanup before ODE release
        dJointDestroy(joint);''')
# Introspection of the patch must prove only logging additions.
ctx.write_text(s)
print("H6_C_REGISTRY_TRACE_INSTALLED",hashlib.sha256(ctx.read_bytes()).hexdigest())
