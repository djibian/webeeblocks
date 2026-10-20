"""One bounded native browser acquisition with direct engine motor getters."""
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / 'tools/ci')]
import buffered_runner as buffered
import run_progression_autonomous_mission as canonical

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    native, out = args.native.resolve(), args.output.resolve()
    if out.exists(): raise RuntimeError('Never overwrite or replace an acquisition')
    home, assets = native / 'webots', native / 'assets'
    if (home/'resources/version.txt').read_text().strip() != 'R2025a': raise RuntimeError('wrong Webots')
    asset_sha = subprocess.check_output(['git','-C',str(assets),'rev-parse','HEAD'],text=True).strip()
    if asset_sha != 'c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b': raise RuntimeError('wrong headers/assets')
    for path, expected in {
      native/'webots.tar.bz2':'c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38',
      native/'chrome155.deb':'8fbd2ae69cdf7ee98b7513c3396a7b5e06f974f8625fdd590df3091dd0c3e9de',
      native/'chrome/opt/google/chrome/chrome':'cb19b59995072b86cc7f887b3b1c7ab1f63518a7f2ed9f0d33249e1a040e2c76',
    }.items():
        if sha(path) != expected: raise RuntimeError('binary identity refused: '+str(path))
    env = {k:v for k,v in os.environ.items() if not k.lower().endswith('_proxy')}
    env.update(WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true', LP_NUM_THREADS='1',
      WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
      WEBEEBLOCKS_CI_ARTIFACT_DIR=str(out), XDG_CONFIG_HOME=str(out/'config'))
    env['LD_LIBRARY_PATH'] = ':'.join([str(home/'lib/webots'),str(native/'sysroot/usr/lib/x86_64-linux-gnu'),env.get('LD_LIBRARY_PATH','')])
    includes = [p for p in (assets/'src/webots').rglob('*') if p.is_dir()]
    includes += [home/'include', home/'include/ode']
    for p in (home/'include/qt').iterdir(): includes += [p,p/p.name]
    flags = [f'-I{p}' for p in includes]
    canonical.ARTIFACT_ROOT = out
    old_world = canonical.observed_world
    def world(text):
        text = old_world(text)
        tail = ('\nRobot {\n  name "CI autonomous read-only state observer"\n'
          '  controller "ci_autonomous_reset_observer"\n  supervisor TRUE\n'
          '  synchronization TRUE\n}\n')
        if not text.endswith(tail): raise RuntimeError('observer world changed')
        text = text[:-len(tail)].replace('WorldInfo {','WorldInfo {\n  physics "reset637_current"',1)
        return text.replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/',str(assets)+'/')
    canonical.observed_world = world
    source = ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c'
    original = source.read_bytes()
    plugin = ROOT/'plugins/physics/reset637_current'
    if plugin.exists(): raise RuntimeError('unexpected plugin directory')
    def build():
        plugin.mkdir(parents=True)
        shutil.copyfile(HERE/'observer.cpp',plugin/'observer.cpp')
        probe = '#include "WbMotor.hpp"\n#include "WbPropeller.hpp"\nextern "C" double read_current(WbMotor *m){return m->currentVelocity();}\nextern "C" double read_thrust(WbPropeller *p){return p->currentThrust();}\nextern "C" double read_torque(WbPropeller *p){return p->currentTorque();}\n'
        (out/'accessors.cpp').write_text(probe)
        commands = [
          ['g++','-std=c++17','-fPIC','-O2','-S',*flags,str(out/'accessors.cpp'),'-o',str(out/'accessors.s')],
          ['g++','-std=c++17','-fPIC','-O2','-shared',*flags,str(HERE/'observer.cpp'),'-L'+str(home/'lib/webots'),'-lQt6Core','-o',str(plugin/'libreset637_current.so')],
        ]
        for cmd in commands:
            r=subprocess.run(cmd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (out/'plugin-build.log').open('a').write(r.stdout)
            if r.returncode: return r
        assembly=(out/'accessors.s').read_text()
        if not re.search(r'read_current:.*?movsd\s+640\(%rdi\)',assembly,re.S): raise RuntimeError('unexpected current getter ABI')
        disassembly=subprocess.check_output(['objdump','-d','--disassemble=_ZN7WbMotor19runKinematicControlEdRd',str(home/'bin/webots-bin')],text=True)
        (out/'motor-engine-disassembly.txt').write_text(disassembly)
        if '0x280(%rax)' not in disassembly: raise RuntimeError('native motor current ABI not confirmed')
        modified=buffered.transform(original.decode()).encode()
        (out/'runtime-original.c').write_bytes(original)
        (out/'runtime-instrumented.c').write_bytes(modified)
        try:
            source.write_bytes(modified)
            r=subprocess.run(['make','clean'],cwd=source.parent,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            if r.returncode:return r
            return subprocess.run(['make','-j4'],cwd=source.parent,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        finally: source.write_bytes(original)
    canonical.build_runtime_for_probe=build
    old_validator=canonical.validate_observer_trace
    def validate(path,**kwargs):
        buffered.join_native(out)
        return old_validator(path,**kwargs)
    canonical.validate_observer_trace=validate
    def execute_native():
        with socket.socket() as p: p.bind(('127.0.0.1',0)); display=p.getsockname()[1]-6000
        with socket.socket() as p: p.bind(('127.0.0.1',0)); port=p.getsockname()[1]
        env['DISPLAY']='127.0.0.1:'+str(display)
        wrapper=out/'browser.sh'
        wrapper.write_text('#!/bin/sh\nexec '+str(native/'chrome/opt/google/chrome/chrome')+' --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --disable-background-networking --no-first-run --no-default-browser-check --user-data-dir='+str(out/'chrome-profile')+' "$@" >> '+str(out/'browser.log')+' 2>&1\n')
        wrapper.chmod(0o755)
        config=out/'config/Cyberbotics';config.mkdir(parents=True)
        (config/'Webots-R2025a.conf').write_text('[RobotWindow]\nbrowser='+str(wrapper)+'\nnewBrowserWindow=false\n')
        (out/'platform.json').write_text(json.dumps({'scope':'native experiment; NOT pinned Docker or CI Gate','asset_sha':asset_sha,'node':subprocess.check_output(['node','--version'],text=True).strip(),'uname':os.uname().version,'sha256':{str(p):sha(p) for p in [home/'bin/webots-bin',native/'chrome/opt/google/chrome/chrome',source.with_suffix(''),plugin/'libreset637_current.so']},'host_budget_seconds':1500},indent=2)+'\n')
        processes=[]; streams=[]
        def launch(cmd,name):
            f=(out/name).open('w');streams.append(f)
            p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            processes.append(p);return p
        start=time.monotonic();rc=1
        try:
            x=launch([str(native/'sysroot/usr/bin/Xvfb'),':'+str(display),'-ac','-nolisten','unix','-nolisten','local','-listen','tcp','-screen','0','1280x1024x24'],'xvfb.log')
            time.sleep(.5)
            server=launch([sys.executable,str(ROOT/'tools/ci/runtime_wwi_event_server.py'),'--output',str(out/'browser-events.jsonl')],'server.log')
            time.sleep(.5)
            w=launch([str(home/'webots'),'--stdout','--stderr','--batch','--mode=fast','--port='+str(port),str(canonical.TEMP_WORLD)],'native-webots.log')
            while w.poll() is None:
                events=(out/'browser-events.jsonl').read_text() if (out/'browser-events.jsonl').exists() else ''
                if 'AUTONOMOUS_MISSION_TEST_COMPLETE' in events or re.search(r'"event"\s*:\s*"(ERROR|WINDOW_ERROR|UNHANDLED_REJECTION)"',events): rc=0;break
                if time.monotonic()-start>1500:rc=124;break
                if x.poll() is not None or server.poll() is not None:raise RuntimeError('native preparation child exited')
                time.sleep(.25)
            else: rc=w.returncode
        finally:
            for p in reversed(processes):
                if p.poll() is None:
                    os.killpg(p.pid,signal.SIGTERM)
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            for f in streams:f.close()
        return subprocess.CompletedProcess(['native-Webots-R2025a-browser'],rc,(out/'native-webots.log').read_text())
    main_source=inspect.getsource(canonical.main)
    replacements={
      '    if shutil.which("docker") is None:\n        return fail("docker is unavailable")\n':'',
      '        pull = run(["docker", "pull", WEBOTS_IMAGE], capture=True)\n        if pull.returncode:\n            return fail("pinned Webots image could not be prepared", pull.stdout)\n':'',
    }
    for before,after in replacements.items():
        if main_source.count(before)!=1:raise RuntimeError('canonical setup changed')
        main_source=main_source.replace(before,after)
    begin=main_source.index('        result = subprocess.run([\n            "docker", "run"')
    end=main_source.index('        webots_log = result.stdout or ""',begin)
    main_source=main_source[:begin]+'        result = execute_native()\n'+main_source[end:]
    canonical.__dict__['execute_native']=execute_native
    exec(compile(main_source,str(HERE/'native-canonical-main.py'),'exec'),canonical.__dict__)
    # Persist the exact adapted oracle source before executing the one acquisition.
    (HERE/'native-canonical-main.py').write_text(main_source)
    result=1
    try: result=canonical.main()
    finally:
        out.mkdir(parents=True,exist_ok=True)
        for p in HERE.iterdir():
            if p.is_file():shutil.copyfile(p,out/p.name)
        (out/'completion.json').write_text(json.dumps({'result':result,'source_restored':source.read_bytes()==original,'attempts':1,'retry':False})+'\n')
        (out/'manifest.json').write_text(json.dumps({str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and 'chrome-profile' not in p.parts and p.name!='manifest.json'},indent=2)+'\n')
        if plugin.exists():shutil.rmtree(plugin)
    return result

if __name__=='__main__':raise SystemExit(main())
