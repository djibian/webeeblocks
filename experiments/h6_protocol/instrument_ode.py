#!/usr/bin/env python3
"""H6 protocol: deliberately minimal research-only ODE entrance gate.

No plugin ABI guarantees, no global solver barrier, no scalable tombstone policy.
Never ship this as production; it is a falsification fixture for P0/P1.
"""
import hashlib,subprocess,sys
from pathlib import Path
PIN="c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
if len(sys.argv)!=2:raise SystemExit("usage: instrument_ode.py PINNED_WEBOTS_TREE")
root=Path(sys.argv[1])
assert subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()==PIN
assert not subprocess.check_output(["git","-C",str(root),"status","--porcelain"],text=True).strip()
p=root/"src/ode/ode/src/ode.cpp"
s=p.read_text()
old="""void dJointDestroy (dxJoint *j)
{
    dAASSERT (j);
    if (!(j->flags & dJOINT_INGROUP)) {
        FinalizeAndDestroyJointInstance(j, true);
    }
}"""
new="""// H6 OWNERSHIP PROTOCOL FALSIFICATION ONLY.
// Admission happens before j->flags or ANY ODE dereference. Two explicit paths,
// never a thread-local "Webots privileged" flag (plugins run in same thread).
static std::recursive_mutex h6AdmissionMutex;
static std::unordered_map<dxJoint *, int> h6EngineLive;
static std::unordered_set<dxJoint *> h6InDestruction;
static std::unordered_set<dxJoint *> h6Retired;
static void (*h6BeforeFree)(dJointID,int)=nullptr;
static int h6Policy=0; // P0 external no-op; P1 external true deletion.
static unsigned long h6ReusedAddresses=0;
static unsigned long h6Denied=0, h6Duplicate=0, h6Effective=0;
extern "C" void h6SetPolicy(int v) {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    dIASSERT(v==0 || v==1);
    h6Policy=v;
}
extern "C" void h6SetBeforeFree(void (*f)(dJointID,int)) {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    h6BeforeFree=f;
}
extern "C" unsigned long h6CountReused() {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    return h6ReusedAddresses;
}
extern "C" unsigned long h6CountDenied() {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    return h6Denied;
}
extern "C" unsigned long h6CountDuplicates() {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    return h6Duplicate;
}
extern "C" unsigned long h6CountEffective() {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    return h6Effective;
}
extern "C" size_t h6CountTracked() {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    return h6EngineLive.size();
}
// Atomic construction + registration at the ODE-owned gate, unlike a
// dJointCreateContact(); register(j) sequence with an exposure window.
extern "C" dJointID h6CreateEngineContact(dWorldID w,const dContact *c,int buffer) {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    dIASSERT(buffer==0 || buffer==1);
    dxJoint *j=dJointCreateContact(w,nullptr,c);
    if (h6Retired.erase(j)) ++h6ReusedAddresses; // ABA explicitly observed.
    dIASSERT(h6EngineLive.find(j)==h6EngineLive.end());
    h6EngineLive[j]=buffer;
    return j;
}
static bool h6DestroyGate(dxJoint *j, bool engine) {
    std::lock_guard<std::recursive_mutex> lock(h6AdmissionMutex);
    // Raw pointer is never dereferenced for a known registered/destroying/id.
    if (h6InDestruction.count(j) || h6Retired.count(j)) {
        ++h6Duplicate;
        return false;
    }
    const auto it=h6EngineLive.find(j);
    if (it!=h6EngineLive.end()) {
        if (!engine && h6Policy==0) {
            ++h6Denied;
            return false;
        }
        const int buffer=it->second;
        h6InDestruction.insert(j);
        // Reentrant callback sees DELETING; even P1 nested calls are denied.
        if (h6BeforeFree) h6BeforeFree(j,buffer);
        h6EngineLive.erase(j); // unregister before ODE frees.
        FinalizeAndDestroyJointInstance(j,true);
        h6InDestruction.erase(j);
        h6Retired.insert(j);
        ++h6Effective;
        return true;
    }
    if (!engine) {
        // An unrelated plugin-owned joint retains EXACT preexisting ODE rules.
        // This cannot protect an arbitrary stale plugin-owned pointer.
        dAASSERT(j);
        if (!(j->flags & dJOINT_INGROUP))
            FinalizeAndDestroyJointInstance(j,true);
        return true;
    }
    // An unknown engine joint must NEVER be freed in this protocol.
    return false;
}
// This is the explicit internal path. Plugin callbacks executing in an
// "engine scope" still enter via regular dJointDestroy and obey P0/P1.
extern "C" int h6EngineDestroyContact(dJointID j) {
    return h6DestroyGate(j,true)?1:0;
}
void dJointDestroy (dxJoint *j)
{
    h6DestroyGate(j,false);
}"""
assert s.count(old)==1,"precise dJointDestroy anchor changed"
s="#include <mutex>\n#include <unordered_map>\n#include <unordered_set>\n"+s.replace(old,new)
p.write_text(s)
print("H6_PROTO_PATCHED",hashlib.sha256(p.read_bytes()).hexdigest())
