#!/usr/bin/env python3
"""H6 three-pair audit: qualitative claims remain explicitly bounded."""
import hashlib, json, math, re, sys
from pathlib import Path

root=Path(sys.argv[1])
reports=[]
def require(test, why):
 if not test: raise ValueError('H6 REPLICATION REFUSED: '+why)

for n in (1,2,3):
 folder=root/f'ab-run-{n}'
 report=json.loads((folder/'verdict.json').read_text())
 require('invalid_or_missing_data' not in report, f'pair {n}: invalid analyzer data')
 require(report.get('observed_preintervention_boundary_equal') is True,
         f'pair {n}: unequal initial physical fields')
 require(report.get('motor_state_equal') is True and report.get('contact_id_sets_equal') is True,
         f'pair {n}: different motors or contact topology')
 require(report.get('strict_hidden_state_equality_proven') is False,
         f'pair {n}: invalid causal overclaim')
 a,b=report['branches']['A'],report['branches']['B']
 require(a['old_contacts_armed_at_reset']==[3,4] and b['old_contacts_armed_at_reset']==[3,4],
         f'pair {n}: unexpected old joint identity')
 require(sorted(a['solver_old_joint_ids'])==[3,4] and not b['solver_old_joint_ids'],
         f'pair {n}: old solver membership not contrasted')
 require(not a['intervention_events'] and len(b['intervention_events'])==1
         and b['intervention_events'][0]['count']=='2',
         f'pair {n}: intervention not exclusively B-targeted')
 require(all(v==0 for s in (a,b) for v in s['four_motor_effective_omega_before_intervention'].values()),
         f'pair {n}: motor nonzero')
 na=math.sqrt(sum(v*v for v in a['angular_velocity_after_next_integration_rad_s']))
 nb=math.sqrt(sum(v*v for v in b['angular_velocity_after_next_integration_rad_s']))
 require(na>0.1 and nb<1e-8, f'pair {n}: missing angular contrast')
 require(a['old_contacts_integrated_torque_impulse_Nms'] != [0,0,0] and
         b['old_contacts_integrated_torque_impulse_Nms']==[0,0,0],
         f'pair {n}: solver impulse missing')
 for mode in ('A','B'):
  here=folder/mode
  require((here/'process_exit_code.txt').read_text().strip()=='0',f'pair {n} {mode}: exit')
  lines=(here/'native.log').read_text().splitlines()
  require(lines and all(line.startswith('H6 event=') for line in lines),f'pair {n} {mode}: malformed native line')
  # Validate the on-disk H6 single-call records and process-specific identity.
  pids={re.search(r' h6_pid=([0-9]+) h6_ns=[0-9]+$',line).group(1)
        for line in lines if re.search(r' h6_pid=([0-9]+) h6_ns=[0-9]+$',line)}
  require(len(pids)==1 and len(pids)<=len(lines),f'pair {n} {mode}: missing PID')
  require((here/'controller.jsonl').read_text().splitlines()[-1]=='H6_CONTROLLER end_of_one_shot_experiment',
          f'pair {n} {mode}: Supervisor incomplete')
  require((here/'runtime_loaded_files.sha256').read_bytes(),
          f'pair {n} {mode}: missing runtime identity')
 reports.append({'pair':n,'A_rad_s':na,'B_rad_s':nb,
                 'old_contact_torque_Nm':a['old_contacts_aggregate_torque_Nm'],
                 'old_contact_impulse_Nms':a['old_contacts_integrated_torque_impulse_Nms'],
                 'angular_momentum_delta_Nms':a['delta_L_world_Nms'],
                 'A_solver':a['solver_old_joint_ids'],'B_solver':b['solver_old_joint_ids']})

base=reports[0]
for report in reports[1:]:
 require(abs(base['A_rad_s']-report['A_rad_s'])<1e-8 and report['B_rad_s']<1e-8,
         f'replication drift {report["pair"]}')
 require(all(abs(x-y)<1e-9 for x,y in zip(base['old_contact_impulse_Nms'],
                                         report['old_contact_impulse_Nms'])),
         f'replication impulse drift {report["pair"]}')
summary={'pairs':reports,'p1_persistence':'PROVEN in isolated H6 fixture',
         'p2_solver_participation':'PROVEN in isolated H6 fixture',
         'p3_dynamic_effect':'PROVEN as ODE measured joint torque and correlated momentum change in H6',
         'p4_causal_exclusivity':'UNPROVEN across independently launched processes; unmeasured hidden state remains',
         'p5_historical_637':'UNPROVEN; historical 39.652 rad/s NOT replayed',
         'no_production_patch':True}
(root/'replications.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
