#!/usr/bin/env python3
"""One bounded native R2025a #665 GDB acquisition, no product CI oracle."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.layout_u import generate, world_text
from tools.ci.run_grand_prix_u_geometry import IMAGE

OUT = ROOT/'ci-artifacts/qt665-native-gdb'
HOME = Path('/usr/local/webots')
EXPECTED = {
    'webots-bin': 'e45a90b580a00f50dc08746e6f43d1a86a83fcf1b23f55538737309154150545',
    'QtWidgets': '868b516dde6d020badc7243facd48f880b0d606c76e46e50427c1c744a2c1024',
    'QtCore': 'ac391204135f1435ca1c97a7f92e6f94d9d369f6b12fb823923496360a272bd8',
}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def run_checked(command, seconds):
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=seconds)
    if proc.returncode:
        raise RuntimeError(f'{command[0]}: {proc.returncode}: {proc.stdout[-800:]}')

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    record = dict(schema=1, claim='native parent-safe full ELF same-frame causal discriminator (NON-GATE)',
                  status='PREPARING', platform=platform.platform(),
                  image=os.environ.get('QT665_EXPECTED_IMAGE'),
                  raw_core_uploaded=False, product_oracles_modified=False)
    world = ROOT/'worlds/ci_qt665_gdb_once.wbt'
    proxy = HOME/'.qt665-one-shot-wrapper'
    log = OUT/'gdb.log'
    try:
        if (HOME/'resources/version.txt').read_text().strip() != 'R2025a':
            raise RuntimeError('wrong native Webots version')
        if record['image'] != IMAGE:
            raise RuntimeError('wrong pinned Docker image')
        record['executables'] = {k: shutil.which(k) for k in ('gdb','Xvfb','xvfb-run')}
        if not all(record['executables'].values()):
            raise RuntimeError('GDB / Xvfb unavailable')
        files = {'webots-bin':HOME/'bin/webots-bin',
                 'QtWidgets':HOME/'lib/webots/libQt6Widgets.so.6.5.3',
                 'QtCore':HOME/'lib/webots/libQt6Core.so.6.5.3',
                 'QtGui':HOME/'lib/webots/libQt6Gui.so.6.5.3'}
        record['native_inputs'] = {k: {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
                                   for k,p in files.items()}
        for k,v in EXPECTED.items():
            if record['native_inputs'][k]['sha256'] != v:
                raise RuntimeError('historical executable/Qt SHA256 mismatch: '+k)
        record['gdb_version'] = subprocess.check_output(
            ['gdb','--version'],text=True,timeout=10).splitlines()[0]
        record['environment_before_wrapper'] = {key:os.environ.get(key) for key in
            ('WEBOTS_HOME','DISPLAY','QT_QPA_PLATFORM','QT_QPA_PLATFORM_PLUGIN_PATH',
             'LIBGL_ALWAYS_SOFTWARE')}
        before=OUT/'packages-before.txt'
        after=OUT/'packages-after.txt'
        if before.exists() and after.exists():
            initial=dict(line.split('\t',1) for line in before.read_text().splitlines() if '\t' in line)
            installed=dict(line.split('\t',1) for line in after.read_text().splitlines() if '\t' in line)
            record['debugger_package_changes'] = {k:[v,installed.get(k)] for k,v in initial.items()
                                                  if installed.get(k)!=v}
        # Copy wrapper to same directory so its Webots-home resolution is stable.
        # Change only the final native-ELF execution into an exec of GDB.
        original = (HOME/'webots').read_text()
        launch_block = (
            'if command -v primusrun >/dev/null 2>&1; then\n'
            '  primusrun "$webots_home/bin/webots-bin" "$@" &\n'
            'else\n'
            '  "$webots_home/bin/webots-bin" "$@" &\n'
            'fi'
        )
        if original.count(launch_block)!=1:
            raise RuntimeError('pinned R2025a wrapper native launch block mismatch')
        if shutil.which('primusrun'):
            raise RuntimeError('unexpected primusrun: cannot preserve launch equivalence')
        injected = (
            'gdb -q -nx -batch -iex "set auto-load off" '
            '-iex "set debuginfod enabled off" '
            '-ex "set print frame-arguments none" -ex "set print entry-values no" '
            '-ex "source /workspace/experiments/qt-progress-lifetime-665/native-gdb/qt_lifetime_gdb.py" '
            '-ex "info breakpoints" -ex run -ex "info breakpoints" '
            '--args "$webots_home/bin/webots-bin" "$@" &'
        )
        proxy.write_text(original.replace(launch_block,injected))
        proxy.chmod(0o700)
        record['wrapper'] = {'original_sha256':sha(HOME/'webots'),
                             'proxy_sha256':sha(proxy),'substitutions':1,
                             'target':'original /usr/local/webots/bin/webots-bin'}
        record['tracer_sha256'] = sha(ROOT/'experiments/qt-progress-lifetime-665/native-gdb/qt_lifetime_gdb.py')
        layout = generate(4,2.)
        world.write_text(world_text(layout,controller='grand_prix_u_flight',
                         window='<none>',evaluator=True).replace(
                         'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/','webots://'))
        record['world_sha256'] = sha(world)
        record['world_layout_id'] = layout.identifier
        # Same native controller preparation as original Grand Prix runner.
        run_checked([sys.executable,str(ROOT/'tools/grand_prix/prepare_u_runtime.py')],90)
        run_checked(['make','-C',str(ROOT/'controllers/grand_prix_u_flight')],90)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix='qt665-native-state-') as temp:
            env=os.environ.copy()
            env.update(WEBOTS_HOME=str(HOME),LIBGL_ALWAYS_SOFTWARE='true',
                       WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
                       LP_NUM_THREADS='1')
            for variable,folder in [('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),
                                    ('XDG_RUNTIME_DIR','runtime')]:
                directory=Path(temp)/folder
                directory.mkdir(mode=0o700)
                env[variable]=str(directory)
            command=['timeout','--signal=TERM','--kill-after=5s','105s',
                     'xvfb-run','-a','/bin/bash',str(proxy),
                     '--stdout','--stderr','--batch','--mode=fast',
                     '--no-rendering','--port='+str(port),str(world)]
            record['launch']=command
            record['display']='fresh Xvfb via xvfb-run -a'
            record['launch_environment']={k:env.get(k) for k in
                ('WEBOTS_HOME','LIBGL_ALWAYS_SOFTWARE','LP_NUM_THREADS',
                 'QT_QPA_PLATFORM','QT_QPA_PLATFORM_PLUGIN_PATH')}
            start=time.monotonic()
            with log.open('wb') as stream:
                try:
                    proc=subprocess.run(command,env=env,cwd=ROOT,stdout=stream,
                                        stderr=subprocess.STDOUT,timeout=120)
                    record['exit']=proc.returncode
                except subprocess.TimeoutExpired:
                    record['exit']='PYTHON_TIMEOUT'
            record['duration_seconds']=round(time.monotonic()-start,2)
        lines=log.read_text(errors='replace').splitlines()
        events=[]
        for line in lines:
            if line.startswith('WBB_QT665 '):
                try: events.append(json.loads(line[10:]))
                except json.JSONDecodeError:
                    record['invalid_gdb_event']=True
        counts={kind:sum(e.get('kind')==kind for e in events)
                for kind in sorted({e.get('kind') for e in events})}
        record['event_counts']=counts
        record['symbol_coverage']=[e for e in events if e.get('kind')=='coverage_live'][:2]
        record['gaps']=[e for e in events if e.get('kind')=='gap'][:20]
        record['lifetime_witness']=[e for e in events
                                   if 'destroyed_within_setvalue' in e.get('kind','')][:10]
        record['signal_stops']=[e for e in events if e.get('kind')=='signal'][:5]
        record['ready_observed']=any('WEBEEBLOCKS_RUNTIME_V2 READY' in line for line in lines)
        record['segv_observed']=any(e.get('name')=='SIGSEGV' for e in record['signal_stops'])
        record['live_symbol_resolution_verified']=bool(
            record['symbol_coverage'] and record['symbol_coverage'][0].get('all_resolved'))
        record['status']=('ACQUIRED' if counts.get('enter',0)>0 and
                          record['live_symbol_resolution_verified'] and
                          not record.get('invalid_gdb_event') else 'UNQUALIFIED_COVERAGE')
        # Reject false positives: the real native completion callback must retire
        # the exact old dialog inside Qt setValue, then maximum must access the
        # exact old bar before return without an intervening destructor.
        retire = [x for x in events if x.get('kind') == 'retire_within_setvalue']
        maxima = [x for x in events if x.get('kind') == 'bar_maximum_after_retire']
        returns = [x for x in events if x.get('kind') == 'return']
        deaths = [x for x in events if x.get('kind') in (
            'bar_destroyed_within_setvalue', 'dialog_destroyed_within_setvalue')]
        gaps = [x for x in events if x.get('kind') == 'gap']
        signals = [x for x in events if x.get('kind') == 'signal']
        proof = []
        for a in retire:
            for b in maxima:
                if not (a.get('id') == b.get('id') and a.get('bar') == b.get('bar')
                        and a.get('dialog') == b.get('dialog') and a['n'] < b['n']):
                    continue
                for c in returns:
                    if (c.get('id') == a.get('id') and b['n'] < c['n']
                            and c.get('retired') is True
                            and c.get('destroyed_bar') is False
                            and c.get('destroyed_dialog') is False):
                        proof.append({'id':a['id'], 'bar':a['bar'], 'dialog':a['dialog'],
                                      'retire_n':a['n'], 'maximum_n':b['n'], 'return_n':c['n']})
        passed = bool(proof and not deaths and not gaps and not signals
                      and record['status'] == 'ACQUIRED' and record['ready_observed']
                      and record['exit'] in (0,124))
        record['causal'] = dict(verdict='PASS' if passed else 'UNPROVEN',
            witnessed=proof[:3], retire_count=len(retire), max_after_retire=len(maxima),
            destruction_during_setvalue_count=len(deaths), gap_count=len(gaps),
            signal_count=len(signals))
        record['status'] = ('FULL_ELF_CAUSAL_PASS' if passed else 'FULL_ELF_CAUSAL_UNPROVEN')
        (OUT/'gdb.sha256').write_text(sha(log)+'  gdb.log\n')
        print('QT665_NATIVE_GDB '+json.dumps({k:record[k] for k in
              ('status','event_counts','live_symbol_resolution_verified',
               'segv_observed','ready_observed')},sort_keys=True),flush=True)
        if record['status']!='FULL_ELF_CAUSAL_PASS':
            sys.exit(2)
    except Exception as exc:
        record['status']='PREPARATION_OR_EXECUTION_FAILED'
        record['error']=f'{type(exc).__name__}: {exc}'[:1000]
        print('QT665_PREPARATION_FAILED '+record['error'],file=sys.stderr,flush=True)
        sys.exit(3)
    finally:
        (OUT/'summary.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
        world.unlink(missing_ok=True)
        proxy.unlink(missing_ok=True)

if __name__=='__main__':
    main()
