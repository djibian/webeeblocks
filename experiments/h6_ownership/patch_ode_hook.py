#!/usr/bin/env python3
"""Research-only tiny pre/post destroy interception in pinned bundled ODE.

DO NOT DEPLOY: callback registration is serial-test-only. This prototype proves
synchronous pre-free removal, including in the recursive-lock same-thread case.
Worker synchronization, ABI/versioning and contract remain UNPROVEN.
"""
import subprocess,sys,hashlib
from pathlib import Path
PIN="c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
if len(sys.argv)!=2:raise SystemExit("usage: patch_ode_hook.py WEBOTS_CHECKOUT")
root=Path(sys.argv[1])
if subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()!=PIN:
    raise SystemExit("H6_HOOK_REFUSED unexpected Webots source revision")
if subprocess.check_output(["git","-C",str(root),"status","--porcelain"],text=True).strip():
    raise SystemExit("H6_HOOK_REFUSED dirty source")
p=root/"src/ode/ode/src/ode.cpp"
s=p.read_text()
old="""void dJointDestroy (dxJoint *j)
{
    dAASSERT (j);
    if (!(j->flags & dJOINT_INGROUP)) {
        FinalizeAndDestroyJointInstance(j, true);
    }
}"""
new="""// H6 RESEARCH BENCHMARK ONLY. No general event bus, no Webots production ABI.
// A generic plugin call to dJointDestroy first invokes the pre-free callback
// on standalone joints. The callback must not dereference an already freed j.
static void (*h6ContactPreDestroy)(dJointID) = NULL;
static void (*h6ContactPostDestroy)(dJointID) = NULL;
extern "C" void h6SetContactJointDestroyHooks(void (*before)(dJointID),
                                              void (*after)(dJointID))
{
    h6ContactPreDestroy = before;
    h6ContactPostDestroy = after;
}
void dJointDestroy (dxJoint *j)
{
    dAASSERT (j);
    if (!(j->flags & dJOINT_INGROUP)) {
        // The pre-hook may lock the registry mutex and remove the raw joint ID.
        // Its matching post-hook releases that lock *after* the ODE free.
        if (h6ContactPreDestroy)
            h6ContactPreDestroy(j);
        FinalizeAndDestroyJointInstance(j, true);
        if (h6ContactPostDestroy)
            h6ContactPostDestroy(j); // raw address only, no dereference
    }
}"""
if s.count(old)!=1:raise SystemExit(f"H6_HOOK_REFUSED joint destructor anchors={s.count(old)}")
p.write_text(s.replace(old,new))
print("H6_ODE_HOOK_FILE",p.relative_to(root),hashlib.sha256(p.read_bytes()).hexdigest())
print("H6_ODE_HOOK_APPLIED",PIN)
