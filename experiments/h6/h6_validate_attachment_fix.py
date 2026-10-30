#!/usr/bin/env python3
"""Fail-closed distinction between tested H6 R and legacy owner-group F."""
import json, pathlib, sys, hashlib
root=pathlib.Path(sys.argv[1])
j=json.loads((root/'p4-run/p4_qualification.json').read_text())
arms=j.get('arms',{})
if set(arms)!={'A','B','P','F'}: raise SystemExit('R REFUSED missing H6 arms')
a,p,b,r=[arms[k] for k in ('A','P','B','F')]
if not (a['omega_rad_s']>0.25 and p['omega_rad_s']==a['omega_rad_s']
        and b['omega_rad_s']==0 and r['omega_rad_s']==0):
    raise SystemExit('R REFUSED physical four-arm contrast')
script=(pathlib.Path('experiments/h6/payload/source/patch_webots_h6.py')).read_text()
start='void WbOdeContext::clearResetBodyContactJointGroups(dBodyID body)'
end='void WbOdeContext::h6RegisterContact('
if script.count(start)!=1 or script.count(end)!=1: raise SystemExit('R REFUSED generator anchor')
f=script[script.index(start):script.index(end)]
if not ('dJointAttach(joint, 0, 0)' in f and 'dJointGetType(joint) == dJointTypeContact' in f
        and 'dJointGroupEmpty' not in f):
    raise SystemExit('R REFUSED expected attachment-selective cleanup absent')
log=(root/'p4-run/F/native.log').read_text()
if log.count('H6 event=webots_reset_cleanup ')!=1:
    raise SystemExit('R REFUSED no unique Webots intervention')
rpt={'scope':'native Webots R2025a H6 fixture only',
     'commit':(root/'experiment_commit.txt').read_text().strip() if (root/'experiment_commit.txt').exists() else '',
     'intervention':'R: detach contact joints attached to reset body, no group empty',
     'baseline_omega_rad_s':a['omega_rad_s'],
     'placebo_omega_rad_s':p['omega_rad_s'],
     'B_omega_rad_s':b['omega_rad_s'],
     'R_omega_rad_s':r['omega_rad_s'],
     'p4_R_in_H6':'PROVEN',
     'cross_body_ODE':'see separate native E1 run 41040259416',
     'p5_historical':'UNPROVEN',
     'non_regression_general':'UNPROVEN'}
(root/'r_native_qualification.json').write_text(json.dumps(rpt,indent=2)+'\n')
print(json.dumps(rpt,indent=2))
