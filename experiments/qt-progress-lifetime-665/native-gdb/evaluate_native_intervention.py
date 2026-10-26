#!/usr/bin/env python3
"""Strictly classify controlled full-binary intervention, not natural callback."""
import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--gdb-log',type=Path,required=True)
p.add_argument('--summary',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
events=[json.loads(l[len('WBB_QT665 '):]) for l in a.gdb_log.read_text(errors='replace').splitlines() if l.startswith('WBB_QT665 ')]
summary=json.loads(a.summary.read_text())
pick=lambda name:[x for x in events if x.get('kind')==name]
issues=[]
for name in ('setup','coverage_live','selected_maximum','injected_native_retirement','maximum_returned'):
    if len(pick(name))!=1:issues.append(name+'_not_exactly_once')
if pick('injection_gap') or pick('eligibility_gap'):issues.append('gdb_intervention_gap')
if pick('coverage_live') and not pick('coverage_live')[0]['all_resolved']:issues.append('unresolved_breakpoints')
if all(pick(x) for x in ('selected_maximum','injected_native_retirement','maximum_returned')):
    selected,removed,returned=(pick(x)[0] for x in ('selected_maximum','injected_native_retirement','maximum_returned'))
    if not (selected['bar']==removed['bar']==returned['bar'] and selected['dialog']==removed['dialog']):
        issues.append('object_id_changed')
    if not (selected['n']<removed['n']<returned['n']):issues.append('wrong_order')
    if not(all((removed['inactive'],removed['guarded'],removed['inside_setvalue'],returned['inside_setvalue']))
           and not any((removed['dead_bar'],removed['dead_dialog'],returned['dead_bar'],returned['dead_dialog']))):
        issues.append('object_or_frame_not_safe')
    deaths=[x for x in pick('destroy') if x.get('object') in (selected['bar'],selected['dialog'])]
    if not any(x.get('target')=='bar' for x in deaths):issues.append('bar_not_drained')
    if not any(x.get('target')=='dialog' for x in deaths):issues.append('dialog_not_drained')
    if any(x['n']<=returned['n'] or x['inside_setvalue'] for x in deaths):issues.append('premature_destruction')
if not summary.get('ready_observed'):issues.append('ready_not_observed')
if summary.get('exit')!=124:issues.append('unexpected_exit')
manifest={'kind':'QT665_CONTROLLED_NATIVE_WEBOTS_GDB_INTERVENTION','verdict':'PASS' if not issues else 'UNPROVEN',
          'issues':issues,'evidence_counts':{k:len(pick(k)) for k in ('selected_maximum','injected_native_retirement','maximum_returned','destroy','injection_gap')},
          'elf_sha256':summary.get('native_inputs',{}).get('webots-bin',{}).get('sha256'),
          'world_sha256':summary.get('world_sha256'),
          'scope':'Artificial GDB-directed native method call; NOT a natural downloader callback or product adoption.'}
a.out.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(json.dumps(manifest,sort_keys=True))
sys.exit(1 if issues else 0)
