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

# H6-G experimental extension: a bounded native ODE resource experiment with
# the same bundled libode as the actual Webots R2025a build above.
import subprocess, os
source=pathlib.Path('experiments/h6/ode_retired_buffers_probe.cpp')
home=pathlib.Path('native-webots').resolve()
include=str(home/'include/ode')
lib=str(home/'lib/webots')
out=root/'h6-retired-buffer-native-test'
preflight=subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',
                          '-fsyntax-only','-I',include,str(source)],
                         text=True,capture_output=True)
(root/'logs/retired-native-syntax.log').write_text(preflight.stdout+preflight.stderr)
if preflight.returncode:
    raise SystemExit('R+G REFUSED native C++ probe syntax')
build=subprocess.run(['g++','-std=c++17','-O0','-Wall','-Wextra','-Werror',
                      '-I',include,str(source),'-L',lib,'-Wl,-rpath,'+lib,
                      '-lode','-o',str(out)],text=True,capture_output=True)
(root/'logs/retired-native-build.log').write_text(build.stdout+build.stderr)
if build.returncode:
    raise SystemExit('R+G REFUSED native probe build')
proc=subprocess.run([str(out)],text=True,capture_output=True,timeout=120,
                    env={**os.environ,'LD_LIBRARY_PATH':lib})
(root/'retired-results.jsonl').write_text(proc.stdout)
(root/'logs/retired-native-stderr.log').write_text(proc.stderr)
if proc.returncode:
    raise SystemExit('R+G REFUSED native ODE run')
lines=proc.stdout.splitlines()
if not lines or lines[-1]!='H6_G_NATIVE_PASS':
    raise SystemExit('R+G REFUSED missing native success')
records=[json.loads(x) for x in lines[:-1]]
by_cycle={r['cycle']:r for r in records if r['stage']=='retired_cleanup'}
if set(by_cycle)!={1,64,512,2048,8192}:
    raise SystemExit('R+G REFUSED missing resource checkpoints')
for r in by_cycle.values():
    if not (r['group_joints_total']==2 and r['detached_joints_current']==1 and
            r['contacts_on_B']==0 and r['contacts_on_AC']==1 and
            r['permanent_joints']==1 and r['owner_enabled']==0):
        raise SystemExit('R+G REFUSED contact/resource invariants')
if by_cycle[8192]['heap_bytes']-by_cycle[64]['heap_bytes']>=131072:
    raise SystemExit('R+G REFUSED heap not bounded in 8192-cycle fixture')
if records[-1]['stage']!='destroyed':
    raise SystemExit('R+G REFUSED destruction unobserved')
report={'scope':'ODE bundled with actual Webots R2025a native build',
        'cycles':8192,'group_count_at_final_reset':2,
        'heap_at_cycle_64':by_cycle[64]['heap_bytes'],
        'heap_at_cycle_8192':by_cycle[8192]['heap_bytes'],
        'rss_kb_at_64':by_cycle[64]['rss_kb'],
        'rss_kb_at_8192':by_cycle[8192]['rss_kb'],
        'permanent_joint_preserved':True,'third_contact_preserved':True,
        'ordinary_Webots_nonregression':'UNPROVEN','P5':'UNPROVEN'}
(root/'retired_native_qualification.json').write_text(json.dumps(report,indent=2))
print('H6_RPLUSG_LIFETIME_PASS '+json.dumps(report,sort_keys=True))
