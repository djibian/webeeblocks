#!/usr/bin/env python3
"""Inject real ODE allocation-identity probe ON TOP of minimal H6 gate.

This explicitly tries two incompatible policies for retired raw pointers:
keep tombstones (reject legitimate allocations at reused address), or clear
on allocation (stale pointer refers to an unrelated live contact). Neither
constitutes a production fix. No ODE symbols are dereferenced after free.
"""
import hashlib,subprocess,sys
from pathlib import Path
if len(sys.argv)!=2:raise SystemExit("usage: instrument_aba.py WEBOTS_TREE")
root=Path(sys.argv[1])
subprocess.run([sys.executable,str(Path(__file__).with_name("instrument_ode.py")),str(root)],check=True)
p=root/"src/ode/ode/src/ode.cpp"
s=p.read_text()
a="dxJoint * dJointCreateContact (dWorldID w, dJointGroupID group,\n                               const dContact *c)\n{"
assert s.count(a)==1,"cannot locate actual contact creation API"
s=s.replace(a,'extern "C" void h6ContactCreated(dJointID);\n'+a)
a="    j->contact = *c;\n    return j;\n}"
assert s.count(a)==1,"cannot identify actual contact factory"
s=s.replace(a,"    j->contact = *c;\n    h6ContactCreated(j);\n    return j;\n}")
a="static unsigned long h6ReusedAddresses=0;"
assert s.count(a)==1,"cannot locate gate state"
s=s.replace(a,a+"""
static int h6EraseTombstoneOnAllocation=0;
extern "C" void h6SetEraseTombstoneOnAllocation(int v) {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    h6EraseTombstoneOnAllocation=v;
}
extern "C" int h6IsRetired(dJointID j) {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    return h6Retired.count(j)!=0;
}
extern "C" void h6ContactCreated(dJointID j) {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    if (h6EraseTombstoneOnAllocation) h6Retired.erase(j);
}
""")
p.write_text(s)
print("H6_ABA_PROBE_SHA256",hashlib.sha256(p.read_bytes()).hexdigest())
