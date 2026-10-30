#!/usr/bin/env python3
"""Strict SOURCE-order audit, NOT proof of dynamic R necessity or G sufficiency.

Run only on the exact pin c6793d8...; fail closed on changed source shapes.
Outputs a reproducible observation of control-flow order, not a physical oracle.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PIN = "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
paths = {
    "world": "src/webots/engine/WbSimulationWorld.cpp",
    "cluster": "src/webots/engine/WbSimulationCluster.cpp",
    "ode": "src/webots/ode/WbOdeContext.cpp",
    "solid": "src/webots/nodes/WbSolid.cpp",
    "supervisor": "src/webots/nodes/utils/WbSupervisorUtilities.cpp",
    "app": "src/webots/app/WbApplication.cpp",
    "ode_mt": "src/ode/ode/src/ode_MT/ode_MT.cpp",
}
def must(cond, why):
    if not cond:
        raise RuntimeError("REFUSED: " + why)

def ordered(source, keys, title):
    pos = []
    for key in keys:
        must(source.count(key) >= 1, title + ": missing " + repr(key))
        pos.append(source.index(key))
    must(pos == sorted(pos) and len(set(pos)) == len(pos), title + ": order changed")
    return [{"anchor": key, "line": source[:pos[i]].count("\n") + 1}
            for i, key in enumerate(keys)]

def body(s, start, stop):
    must(s.count(start) == 1 and s.count(stop) >= 1, "ambiguous method boundary " + start)
    fragment = s.split(start, 1)[1].split(stop, 1)[0]
    must(fragment, "empty method " + start)
    return fragment

def main():
    must(len(sys.argv) == 3, "usage: audit_static.py WEBOTS_ROOT OUTPUT_JSON")
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    must(sha == PIN, f"source pin mismatch {sha}")
    src = {k: (root / p).read_text() for k, p in paths.items()}
    # The controller message is processed before physics, not after it.
    world_step = body(src["world"], "void WbSimulationWorld::step() {",
                      "void WbSimulationWorld::pauseStepTimer()")
    pre = ordered(world_step, [
        "robot->processImmediateMessages();",
        "solid->prePhysicsStep(timeStep);",
        "mCluster->step();",
        "solid->postPhysicsStep();",
        "if (mResetRequested) {"], "world timeline")
    cluster_step = body(src["cluster"], "void WbSimulationCluster::step() {",
                        "dSpaceID WbSimulationCluster::space()")
    mid = ordered(cluster_step, [
        "dWorldStepAndSpaceCollide(",
        "swapBuffer();",
        "mContext->emptyEnabledBodyContactJointGroups1();"], "cluster timeline")
    # Need both clean functions. They clean only enabled owners and are called after swap.
    for name in ["emptyEnabledBodyContactJointGroups1", "emptyEnabledBodyContactJointGroups2"]:
        frag = body(src["ode"], "void WbOdeContext::" + name + "() {", "dJointGroupID WbOdeContext::") if name.endswith("2") else body(src["ode"], "void WbOdeContext::" + name + "() {", "void WbOdeContext::emptyEnabledBodyContactJointGroups2()")
        must("if (dBodyIsEnabled(it.key()))" in frag and "dJointGroupEmpty(it.value());" in frag,
             "retired disabled owner preserved in " + name)
    ode_mt = body(src["ode_mt"], "void dWorldStepAndSpaceCollide (", "static void initODE()")
    must(ode_mt.count("_stepFunc(_world, _stepsize);") >= 1, "ODE stepping absent")
    for start in ["    } else {\n        _stepFunc(_world, _stepsize);",
                  "#else\n    _stepFunc(_world, _stepsize);"]:
        must(start in ode_mt, "non-MT ODE ordering changed " + start)
    # In both serial configurations the solve is before the next collision callbacks.
    must(ordered(ode_mt, ["} else {\n        _stepFunc(_world, _stepsize);",
                          "dSpaceCollide(_space, _data, _callback);"], "ODE serial reverse order"),
         "cannot establish ODE solver first")
    sup = src["supervisor"]
    must("case C_SUPERVISOR_SIMULATION_RESET_PHYSICS:" in sup and
         "WbApplication::instance()->resetPhysics();" in sup,
         "global physical reset routing absent")
    node = body(sup, "case C_SUPERVISOR_NODE_RESET_PHYSICS: {",
                "case C_SUPERVISOR_NODE_RESTART_CONTROLLER:")
    must("solidNode->resetPhysics(false);" in node and
         "solidNode->pausePhysics(true);" in node, "node RESET has changed")
    glob = body(src["app"], "void WbApplication::resetPhysics() {", "\n}")
    must("solid->resetPhysics();" in glob and "pausePhysics" not in glob,
         "global RESET behavior changed")
    solid_reset = body(src["solid"], "void WbSolid::resetPhysics(bool recursive) {",
                       "void WbSolid::pausePhysics(bool resumeAutomatically) {")
    must("resetSingleSolidPhysics();" in solid_reset and
         "dBodyEnable(b);" in solid_reset and
         "dJointDestroy(" not in solid_reset, "global RESET destroys contacts or no enable")
    full = body(src["solid"], "void WbSolid::reset(const QString &id) {",
                "void WbSolid::save(const QString &id) {")
    must("dJointGetType(joints[i]) == dJointTypeContact" in full and
         "dJointDestroy(joints[i]);" in full, "full solid reset changed")
    collision = body(src["cluster"], "void WbSimulationCluster::odeNearCallback(",
                     "void WbSimulationCluster::odeSensorRaysUpdate(")
    must(ordered(collision, ["dJointCreateContact(jointWorld, group, &contact[i]);",
                             "dJointAttach(contactJoint, b1, b2);"], "real-contact insertion"),
         "contact insertion order missing")
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "classification": "STATIC_CONTROL_FLOW_PROVEN_ONLY",
        "webots_source_commit": sha,
        "source_sha256": {k: hashlib.sha256(s.encode()).hexdigest() for k, s in src.items()},
        "world_step": pre, "cluster_step": mid,
        "deduction": "Supervisor global reset can run while a previously produced current-buffer contact remains attached; G at retirement cannot clear that contact BEFORE the intervening solver.",
        "limits": ["No executed physics in this audit",
                   "Does not prove an impulse or demonstrate necessity of R",
                   "Node reset temporarily disables bodies: separate physical test required",
                   "MT cluster ordering and callback races require native trace",
                   "Physics plugins and arbitrary node state resets not exhaustively covered"],
        "verdict_R_necessary_in_Webots": "UNPROVEN",
        "verdict_G_alone_physically_sufficient": "UNPROVEN",
    }
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"audit": "PASS", "pin": sha, "output": str(out),
                      "scope": result["classification"]}, sort_keys=True))

if __name__ == "__main__":
    main()
