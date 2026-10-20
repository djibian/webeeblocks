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
      'int main(void) {':'#include "../../experiments/runtime-reset-current/buffered.h"\n\nint main(void) {',
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

def join_native(out):
    raw=[json.loads(l) for l in (out/'physics-state.jsonl').read_text().splitlines() if json.loads(l).get('type')=='sample']
    consumed=[json.loads(l) for l in (out/'consumed-state.jsonl').read_text().splitlines()][1:]
    native={round(row['time'],9):row for row in raw}
    if len(native)!=len(raw):raise ValueError('duplicate physics timestamp')
    rows=[]
    for row in consumed:
        n=native.get(round(row['time'],9))
        if n is None:raise ValueError('missing ODE timestamp')
        if n['candidate_overflow']:raise ValueError('contact candidates truncated')
        n={**n,'custom_data':row['custom_data']}
        rows.append(n)
    header={'type':'header','version':1,'step_ms':32,'scope':'read-only-native-state-not-runtime-ack'}
    (out/'native-reset-state.jsonl').write_text('\n'.join(json.dumps(x) for x in [header,*rows])+'\n')

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
