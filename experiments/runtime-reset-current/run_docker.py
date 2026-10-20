"""One direct-actuator acquisition in the canonical R2025a image, no CI Gate."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'tools/ci')]
import buffered_runner as buffered
import run_progression_autonomous_mission as runner

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=runner.ARTIFACT_ROOT
    if out.exists():raise RuntimeError('retain every acquisition; no replacement')
    headers=Path(os.environ['WEBOTS_ENGINE_SOURCE']).resolve()
    source_sha=subprocess.check_output(['git','-C',str(headers),'rev-parse','HEAD'],text=True).strip()
    if source_sha!='c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b':raise RuntimeError('wrong engine headers')
    subprocess.run(['git','-C',str(headers),'diff','--exit-code'],check=True)
    source=ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'
    original=source.read_bytes()
    old_world=runner.observed_world
    def world(text):
        text=old_world(text)
        tail=('\nRobot {\n  name "CI autonomous read-only state observer"\n'
          '  controller "ci_autonomous_reset_observer"\n  supervisor TRUE\n'
          '  synchronization TRUE\n}\n')
        if not text.endswith(tail):raise RuntimeError('world observer shape changed')
        return text[:-len(tail)].replace('WorldInfo {','WorldInfo {\n  physics "reset637_current"',1)
    runner.observed_world=world
    plugin=ROOT/'plugins/physics/reset637_current'
    if plugin.exists():raise RuntimeError('unexpected plugin directory')
    def build():
        plugin.mkdir(parents=True)
        shutil.copyfile(HERE/'observer.cpp',plugin/'observer.cpp')
        probe='#include "WbMotor.hpp"\n#include "WbPropeller.hpp"\nextern "C" double read_current(WbMotor *m){return m->currentVelocity();}\nextern "C" double read_thrust(WbPropeller *p){return p->currentThrust();}\nextern "C" double read_torque(WbPropeller *p){return p->currentTorque();}\n'
        (out/'accessors.cpp').write_text(probe)
        command=r'''set -eu
flags="-I/usr/local/webots/include -I/usr/local/webots/include/ode"
for directory in $(find /engine/src/webots -type d); do flags="$flags -I$directory"; done
for directory in /usr/local/webots/include/qt/*; do flags="$flags -I$directory -I$directory/$(basename "$directory")"; done
g++ -std=c++17 -fPIC -O2 -S $flags /workspace/ci-artifacts/progression-autonomous-mission/accessors.cpp -o /workspace/ci-artifacts/progression-autonomous-mission/accessors.s
g++ -std=c++17 -fPIC -O2 -shared $flags /workspace/experiments/runtime-reset-current/observer.cpp -L/usr/local/webots/lib/webots -lQt6Core -o /workspace/plugins/physics/reset637_current/libreset637_current.so
objdump -d --disassemble=_ZN7WbMotor19runKinematicControlEdRd /usr/local/webots/bin/webots-bin > /workspace/ci-artifacts/progression-autonomous-mission/motor-engine-disassembly.txt
objdump -d --disassemble=_ZN11WbPropeller14prePhysicsStepEd /usr/local/webots/bin/webots-bin > /workspace/ci-artifacts/progression-autonomous-mission/propeller-engine-disassembly.txt
sha256sum /usr/local/webots/bin/webots-bin > /workspace/ci-artifacts/progression-autonomous-mission/engine-sha256.txt
'''
        (out/'plugin-command.sh').write_text(command)
        built=runner.run(['docker','run','--rm','-v',f'{ROOT}:/workspace','-v',f'{headers}:/engine:ro',runner.WEBOTS_IMAGE,'bash','-lc',command],capture=True)
        (out/'plugin-build.log').write_text(built.stdout or '')
        if built.returncode:return built
        if not re.search(r'read_current:.*?movsd\s+640\(%rdi\)',(out/'accessors.s').read_text(),re.S):raise RuntimeError('wrong current accessor ABI')
        if '0x280(%rax)' not in (out/'motor-engine-disassembly.txt').read_text():raise RuntimeError('binary current ABI not verified')
        modified=buffered.transform(original.decode()).encode()
        (out/'runtime-original.c').write_bytes(original)
        (out/'runtime-instrumented.c').write_bytes(modified)
        try:
            source.write_bytes(modified)
            result=runner.run(['docker','run','--rm','-v',f'{ROOT}:/workspace','-w','/workspace/controllers/crazyflie_runtime_v2',runner.WEBOTS_IMAGE,'bash','-lc','make clean && make'],capture=True)
        finally:source.write_bytes(original)
        (out/'provenance.json').write_text(json.dumps({'scope':'direct native getters, experimental not CI Gate','git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'image':runner.WEBOTS_IMAGE,'source_sha':source_sha,'source_restored':source.read_bytes()==original,'build_exit':result.returncode,'sha256':{str(p.relative_to(ROOT)):sha(p) for p in [source,source.with_suffix(''),HERE/'observer.cpp',HERE/'buffered.h',plugin/'libreset637_current.so']}},indent=2)+'\n')
        return result
    runner.build_runtime_for_probe=build
    original_validator=runner.validate_observer_trace
    def validate(path,**kwargs):
        buffered.join_native(out)
        return original_validator(path,**kwargs)
    runner.validate_observer_trace=validate
    old_run=subprocess.run
    def measured_run(*args,**kwargs):
        arguments=list(args);command=arguments[0] if arguments else kwargs.get('args')
        anchor='mkdir -p "$artifact_dir" /root/.config/Cyberbotics'
        if isinstance(command,list) and command and command[0]=='docker' and anchor in command[-1]:
            before=command[-1]
            if before.count(anchor)!=1:raise RuntimeError('ambiguous browser identity insertion')
            after=before.replace(anchor,anchor+'\ngoogle-chrome --version > "$artifact_dir/browser-version.txt"\nsha256sum /tmp/google-chrome.deb /opt/google/chrome/chrome > "$artifact_dir/browser-sha256.txt"')
            (out/'browser-command-original.sh').write_text(before)
            (out/'browser-command-executed.sh').write_text(after)
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
        (out/'outer-result.json').write_text(json.dumps({'result':result,'exception':error,'source_restored':source.read_bytes()==original,'planned':1,'retry':False})+'\n')
        for p in HERE.iterdir():
            if p.is_file():shutil.copyfile(p,out/p.name)
        (out/'manifest.json').write_text(json.dumps({str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'},indent=2)+'\n')
        if plugin.exists():shutil.rmtree(plugin)
    if error:raise RuntimeError(error)
    return result

if __name__=='__main__':raise SystemExit(main())
