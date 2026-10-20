"""Verify primary ODE-cohort ZIP bytes and recompute original RESET predicates."""
import argparse
import contextlib
import os
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

HERE=Path(__file__).resolve().parent
SOURCE_ROOT=HERE.parents[1]
ROOT=Path.cwd()
sys.path[:0]=[str(HERE),str(SOURCE_ROOT/'experiments/runtime-reset-phase')]
import run
import remote

def verify(item):
    number=item['trial'];directory=Path(item['output']);directory.mkdir(parents=True,exist_ok=False)
    archive=Path(item['zip_path']).resolve()
    if not archive.is_file():raise FileNotFoundError(archive)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest!=''.join(item['digest'].split('sha256:')[1:]):raise ValueError('ZIP digest differs from GitHub')
    out=directory/'raw';out.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:raise ValueError('ZIP CRC mismatch')
        for name in bundle.namelist():remote.child_path(out,name)
        bundle.extractall(out)
    files=remote.verify_manifest(out)
    provenance=json.loads((out/'buffered-provenance.json').read_text())
    if provenance['git_head']!=item['expected_head']:raise ValueError('wrong candidate')
    if provenance['image']!=remote.runner.WEBOTS_IMAGE:raise ValueError('wrong image')
    if provenance['source_restored'] is not True or provenance['build_exit']!=0:raise ValueError('build/source uncertain')
    for name,expected in provenance['sha256'].items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest()!=expected:raise ValueError('provenance byte mismatch')
    if run.transform((out/'runtime-original.c').read_text())!=(out/'runtime-instrumented.c').read_text():raise ValueError('wrong transform')
    if (out/'buffered.h').read_bytes()!=(HERE/'buffered.h').read_bytes():raise ValueError('wrong header')
    if (out/'plugin-reset637_native.c').read_bytes()!=(SOURCE_ROOT/'plugins/physics/reset637_native/reset637_native.c').read_bytes():raise ValueError('wrong physics source')
    if 'CI autonomous read-only state observer' in (out/'world.wbt').read_text():raise ValueError('extra observer')
    identity=json.loads((out/'cohort-trial.json').read_text()) if (out/'cohort-trial.json').exists() else None
    if identity is not None and (identity['trial']!=number or identity['head']!=provenance['git_head'] or str(identity['run'])!=str(item['expected_run'])):raise ValueError('wrong trial identity')
    before=hashlib.sha256((out/'native-reset-state.jsonl').read_bytes()).hexdigest()
    derived=directory/'derived';derived.mkdir()
    for name in ('physics-state.jsonl','consumed-state.jsonl'):os.link(out/name,derived/name)
    run.join_native(derived)
    if before!=hashlib.sha256((derived/'native-reset-state.jsonl').read_bytes()).hexdigest():raise ValueError('derived time join inconsistent')
    combined=run.combine((out/'buffered-phase.log').read_text(),(out/'webots.log').read_text())
    summary=run.summarize(combined)
    analysis=directory/'analysis';analysis.mkdir(exist_ok=True)
    (analysis/'webots.log').write_text(combined)
    (analysis/'native-reset-state.jsonl').write_bytes((out/'native-reset-state.jsonl').read_bytes())
    comparison=remote.compare(analysis,summary)
    result=json.loads((out/'outer-result.json').read_text())
    if result['runner_exit']==0:
        if len(summary['resets'])!=14 or not all(x['terminal'].endswith(' OK') for x in summary['resets']):raise ValueError('success without 14 RESETs')
        names=[json.loads(l)['event'] for l in (out/'browser-events.jsonl').read_text().splitlines()]
        if 'AUTONOMOUS_MISSION_TEST_COMPLETE' not in names or any(n in names for n in ('ERROR','WINDOW_ERROR','UNHANDLED_REJECTION')):raise ValueError('business oracle incomplete')
        if 'WEBEEBLOCKS_AUTONOMOUS_COLLISION attempt=7 ' not in (out/'webots.log').read_text():raise ValueError('missing actual collision7')
    report={
        'trial':number,'artifact':item['id'],'run':item['expected_run'],'head':provenance['git_head'],
        'zip_sha256':digest,'zip_bytes':archive.stat().st_size,'manifest_files':files,
        'outer_result':result,'resets':len(summary['resets']),
        'native_samples':len((out/'physics-state.jsonl').read_text().splitlines())-1,
        'comparison_samples':sum(x['compared'] for x in comparison['resets']),
        'predicate_disagreements':sum(len(x['runtime_false_native_true'])+len(x['runtime_true_native_false']) for x in comparison['resets']),
        'reset7':comparison['resets'][6] if len(comparison['resets'])>6 else None,
        'browser_version':(out/'browser-version.txt').read_text().strip(),
        'browser_sha256':(out/'browser-sha256.txt').read_text().splitlines(),
        'host':identity,
        'scope':'finite observations, not causal correction or disappearance proof'
    }
    (directory/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    (analysis/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zip',type=Path,required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--head',required=True)
    p.add_argument('--run',type=int,required=True)
    p.add_argument('--artifact',type=int,required=True)
    p.add_argument('--trial',type=int,default=0)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    verify({'trial':a.trial,'zip_path':str(a.zip),'digest':'sha256:'+a.sha256,
            'expected_head':a.head,'expected_run':a.run,'id':a.artifact,'output':str(a.output)})
