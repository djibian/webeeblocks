"""Exactly one no-extra-controller browser acquisition; never a health verdict."""
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'tools/ci'),str(ROOT/'experiments/runtime-reset-phase')]
import run_progression_autonomous_mission as runner
from instrument import instrument
from analyze import summarize

def transform(source):
    modified=instrument(source)
    for marker in ('RESET_PHASE_BEGIN','RESET_PHASE_SAMPLE'):
        old='fprintf(stderr, PREFIX " '+marker
        assert modified.count(old)==1
        modified=modified.replace(old,'fprintf(diag_phase, PREFIX " '+marker)
    anchors={
      '#include "simulation_clock.h"':'#ifndef _GNU_SOURCE\n#define _GNU_SOURCE\n#endif\n#include "simulation_clock.h"',
      'int main(void) {':'#include "../../experiments/runtime-reset-buffered/buffered.h"\n\nint main(void) {',
      '  send_text(PREFIX " READY");':'  diag_open();\n  send_text(PREFIX " READY");',
      '    const double x = position[0];':'    diag_sample(self_node, now, position, rpy, gyro_values, m1,m2,m3,m4);\n    const double x = position[0];',
      '      response_error(active_id, "RESET_TIMEOUT");':'      diag_dump();\n      response_error(active_id, "RESET_TIMEOUT");',
      '          trace_reset(x, y, z, origin_x, origin_y, origin_z);':'          diag_dump();\n          trace_reset(x, y, z, origin_x, origin_y, origin_z);',
    }
    for old,new in anchors.items():
        if modified.count(old)!=1:raise ValueError('ambiguous buffered anchor: '+old)
        modified=modified.replace(old,new)
    return modified

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def combine(phase,webots):
    """Place actual protocol responses after their buffered samples, by exact id."""
    responses=re.findall(r'^WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (OK|ERR RESET_TIMEOUT)$',webots,re.M)
    result=[];seen=set()
    groups=re.split(r'(?=WEBEEBLOCKS_RUNTIME_V2 RESET_PHASE_BEGIN )',phase)
    for group in groups:
        if not group.strip():continue
        match=re.match(r'WEBEEBLOCKS_RUNTIME_V2 RESET_PHASE_BEGIN id=(\d+) ',group)
        if not match:raise ValueError('missing buffered receipt')
        ident=match[1]
        terminal=[r for r in responses if r[0]==ident]
        if len(terminal)!=1 or ident in seen:raise ValueError('missing/duplicate actual response')
        seen.add(ident)
        result.append(group.rstrip()+'\nWEBEEBLOCKS_RUNTIME_V2 RESPONSE '+ident+' '+terminal[0][1]+'\n')
    return ''.join(result)

def main():
    out=runner.ARTIFACT_ROOT
    if out.exists():raise RuntimeError('refuse to erase acquisition')
    source=ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'
    original=source.read_bytes()
    old_observed=runner.observed_world
    def world(text):
        observed=old_observed(text)
        tail=('\nRobot {\n  name "CI autonomous read-only state observer"\n'
              '  controller "ci_autonomous_reset_observer"\n  supervisor TRUE\n'
              '  synchronization TRUE\n}\n')
        assert observed.endswith(tail)
        return observed[:-len(tail)]
    runner.observed_world=world
    def build():
        modified=transform(original.decode()).encode()
        (out/'runtime-original.c').write_bytes(original)
        (out/'runtime-instrumented.c').write_bytes(modified)
        shutil.copyfile(HERE/'buffered.h',out/'buffered.h')
        try:
            source.write_bytes(modified)
            result=runner.run(['docker','run','--rm','-v',f'{ROOT}:/workspace','-w',
                '/workspace/controllers/crazyflie_runtime_v2',runner.WEBOTS_IMAGE,
                'bash','-lc','make clean && make'],capture=True)
        finally:source.write_bytes(original)
        provenance={'scope':'buffered Runtime self-observation; no extra synchronized observer',
          'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'image':runner.WEBOTS_IMAGE,'source_restored':source.read_bytes()==original,
          'build_exit':result.returncode,'sha256':{p.name:sha(p) for p in (out/'runtime-original.c',out/'runtime-instrumented.c',HERE/'buffered.h',Path(__file__))}}
        if result.returncode==0:provenance['executable_sha256']=sha(source.with_suffix(''))
        (out/'buffered-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        return result
    runner.build_runtime_for_probe=build
    old_run=subprocess.run
    def measured_run(*args,**kwargs):
        arguments=list(args)
        command=arguments[0] if arguments else kwargs.get('args')
        anchor='DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null'
        if isinstance(command,list) and command and command[0]=='docker' and anchor in command[-1]:
            assert command[-1].count(anchor)==1
            before=command[-1]
            after=before.replace(anchor,anchor+'\n'
              'google-chrome --version > /workspace/ci-artifacts/progression-autonomous-mission/browser-version.txt\n'
              'sha256sum /tmp/google-chrome.deb /opt/google/chrome/chrome > /workspace/ci-artifacts/progression-autonomous-mission/browser-sha256.txt')
            (out/'browser-command-original.sh').write_text(before)
            (out/'browser-command-measured.sh').write_text(after)
            command=[*command[:-1],after]
            if arguments:arguments[0]=command
            else:kwargs['args']=command
        return old_run(*arguments,**kwargs)
    subprocess.run=measured_run
    os.environ.update(WEBEEBLOCKS_RESET_PHASE_TRACE='0',WEBEEBLOCKS_RESET_PHASE_DEFER_STEPS='0')
    result=1;error=None
    try:result=runner.main()
    except Exception as exc:error=repr(exc)
    finally:
        subprocess.run=old_run
        out.mkdir(parents=True,exist_ok=True)
        (out/'outer-result.json').write_text(json.dumps({'runner_exit':result,'exception':error,
           'source_restored':source.read_bytes()==original,'planned':1,'retry':False})+'\n')
        for name in ('run.py','PROTOCOL.md'):shutil.copyfile(HERE/name,out/name)
        (out/'sha256.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='sha256.json'},indent=2)+'\n')
    if error:raise RuntimeError(error)
    if result:return result
    combined=combine((out/'buffered-phase.log').read_text(),(out/'webots.log').read_text())
    summary=summarize(combined)
    assert len(summary['resets'])==14 and all(r['terminal'].endswith(' OK') for r in summary['resets'])
    print('BUFFERED_NATIVE_RESULT',json.dumps(summary),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
