#!/usr/bin/env python3
"""Strict H6 A/P/B/F four-arm qualification. No claim for historical #637."""
import importlib.util, json, math, pathlib, sys
out=pathlib.Path(sys.argv[1])
source=pathlib.Path(sys.argv[2])
spec=importlib.util.spec_from_file_location("h6_base",source)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def check(ok,why):
 if not ok: raise RuntimeError("H6 P4 REFUSED "+why)
modes=("A","P","B","F")
branches={name:m.parse_branch(out/name,name) for name in modes}
e={name:m.read_events(out/name)[0] for name in modes}
first=branches["A"]
fields=("enabled","nold_current","pos","v","omega","force","torque","mass","I","quat")
for key in fields:
 check(all(branches[name]["boundary_native"].get(key)==first["boundary_native"].get(key) for name in modes),
       "preintervention unequal "+key)
for name in modes:
 b=branches[name]
 check(b["old_contacts_armed_at_reset"]==[3,4],name+" missing exact old contacts")
 check(b["old_contacts_geometry"]==first["old_contacts_geometry"],name+" contact geometry different")
 check(b["four_motor_effective_omega_before_intervention"]==first["four_motor_effective_omega_before_intervention"],
       name+" motor difference")
 check(all(x==0.0 for x in b["four_motor_effective_omega_before_intervention"].values()),name+" spinning motor")
 check((out/name/"process_exit_code.txt").read_text().strip()=="0",name+" exit failed")
 check((out/name/"controller.jsonl").read_text().splitlines()[-1]=="H6_CONTROLLER end_of_one_shot_experiment",
       name+" Supervisor unfinished")
expected_solver={"A":[3,4],"P":[3,4],"B":[],"F":[]}
for name,ids in expected_solver.items():
 check(sorted(branches[name]["solver_old_joint_ids"])==ids,name+" unexpected old solver IDs")
check(not any(v["event"] in ("placebo_scan","intervention_drop","webots_reset_cleanup") for v in e["A"]),
      "A intervention not passive")
check(len([v for v in e["P"] if v["event"]=="placebo_scan" and v.get("count")=="2"])==1,
      "P missing placebo traversal")
check(not any(v["event"] in ("intervention_drop","webots_reset_cleanup") for v in e["P"]),
      "P mutated contacts")
check(len([v for v in e["B"] if v["event"]=="intervention_drop" and v.get("count")=="2"])==1,
      "B did not target two contacts")
check(not any(v["event"]=="webots_reset_cleanup" for v in e["B"]),"B used Webots fix")
check(not any(v["event"]=="intervention_drop" for v in e["F"]),"F used B intervention")
check(len([v for v in e["F"] if v["event"]=="webots_reset_cleanup" and v.get("removed")=="2"])==1,
      "F did not clean two contacts on reset")
w={name:m.norm(branches[name]["angular_velocity_after_next_integration_rad_s"]) for name in modes}
check(w["A"]>0.25 and abs(w["A"]-w["P"])<=1e-12,"placebo angular mismatch")
check(w["B"]<=1e-9 and w["F"]<=1e-9,"intervention angular effect failed")
for name in ("A","P"):
 check(m.norm(branches[name]["old_contacts_aggregate_torque_Nm"])>1e-4,
       name+" missing dynamic torque")
for name in ("B","F"):
 check(m.norm(branches[name]["old_contacts_aggregate_torque_Nm"])<1e-12,
       name+" residual old torque")
result={"scope":"Webots R2025a isolated H6 synthetic fixture",
        "arms":{name:{"omega_rad_s":w[name],
                       "old_solver_ids":branches[name]["solver_old_joint_ids"],
                       "old_torque_Nm":branches[name]["old_contacts_aggregate_torque_Nm"]} for name in modes},
        "p4":"PROVEN experimentally in synthetic H6 fixture under observed-state and intervention controls",
        "hidden_state":"not exhaustively proven equal across processes",
        "historical_637":"UNPROVEN", "ordinary_physics_regression":"UNPROVEN",
        "fix":"Webots candidate clears reset body's contact groups before reenabling it",
        "complete":True}
(out/"p4_qualification.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
