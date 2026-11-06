#!/usr/bin/env python3
"""Required real-R2025a static geometry evidence; never fabricates a flight PASS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tempfile
import re

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.layout_u import generate, world_text

# M2: default Linux Webots B parent-safe runtime, exact OCI identity. No fallback
# to the upstream image; the historical image remains an upstream source pin.
IMAGE = 'ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca'
SOURCE = 'c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b'
OUT = ROOT/'ci-artifacts/grand-prix-u-geometry'


def cases():
    # Cover all three counts and every side, plus variations in position.
    selected, seen = [], set()
    for seed in range(64):
        layout = generate(seed)
        key = (len(layout.gates), tuple(g.side for g in layout.gates))
        if key not in seen:
            seen.add(key)
            selected.append(seed)
    return selected


def run_contact_campaign(home):
    """Exactly the existing four L-contact cases and mixed-GD H evidence.

    A dedicated REQUIRED CI job runs all native cases on its own isolated
    checkout. Splitting the sequential 1350-s campaign never skips a probe.
    """
    # Extend the first native mixed-GD contact to one GG/GD/DG/DD course,
    # spanning variable lengths and gate counts. Every case is required;
    # preserve all historical U/deadline/pose/range assertions as well.
    from tools.ci.run_grand_prix_v2_contact_native import (
        DEFAULT_INDICES, native_run as run_contact,
    )
    run_contact(home, DEFAULT_INDICES)
    # The complete GD mixed-length world must also yield real low/high H rays
    # for every open gate and the closed terminal obstacle. No H result from a
    # Python fake, old summary or another invocation qualifies this campaign.
    # The existing geometry artifact retains its per-run native JSON/log bytes.
    from tools.ci.run_grand_prix_v2_h_native import native_run as run_h
    run_h(home, (5,), output_root=OUT / 'route-h-native')


def write_manifest():
    manifest = {p.relative_to(OUT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in OUT.rglob('*') if p.is_file() and p != OUT / 'sha256.json'}
    (OUT / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')


def run_native(home, tcp=False, *, partition='all'):
    version = (home/'resources/version.txt').read_text().strip()
    if version != 'R2025a':
        raise RuntimeError('required Webots R2025a unavailable: '+version)
    if partition not in ('all', 'core', 'contacts'):
        raise ValueError('unknown mandatory native partition')
    OUT.mkdir(parents=True, exist_ok=True)
    if partition == 'contacts':
        run_contact_campaign(home)
        write_manifest()
        return
    env = os.environ.copy()
    env.update(WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true',
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    summaries = []
    for seed in cases():
        layout = generate(seed)
        target = ROOT/'worlds/ci_gp_u_geometry.wbt'
        project = target.with_name('.ci_gp_u_geometry.wbproj')
        source = world_text(layout, controller='<extern>' if tcp else 'grand_prix_u_geometry_probe',
                            window='<none>', evaluator=False)
        target.write_text(source.replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', 'webots://'))
        logpath = OUT/f'{layout.identifier}.log'
        native_data=OUT/f'{layout.identifier}-native.json'
        native_data.unlink(missing_ok=True)
        env['GP_U_GEOMETRY_OUT']=str(native_data)
        proc = None
        try:
            with logpath.open('w') as log:
                # R2025a omits the modal world-loading progress dialog while
                # minimized. Keep rendering enabled for native perception.
                proc = subprocess.Popen([str(home/'webots'), '--stdout', '--stderr', '--batch',
                                         '--mode=fast', '--minimize', '--port=1257', str(target)],
                                        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                if tcp:
                    limit = time.monotonic()+30
                    while proc.poll() is None and time.monotonic() < limit:
                        if 'Waiting for local or remote connection' in logpath.read_text():
                            break
                        time.sleep(.1)
                    else:
                        raise RuntimeError('extern controller readiness not established')
                    with (OUT/f'{layout.identifier}-controller.log').open('w') as controller_log:
                        subprocess.run([str(home/'webots-controller'), '--protocol=tcp',
                                        '--ip-address=127.0.0.1', '--port=1257',
                                        '--robot-name=Crazyflie WebeeBlocks',
                                        str(ROOT/'controllers/grand_prix_u_geometry_probe/grand_prix_u_geometry_probe.py'),
                                        str(seed), '2'], env=env, stdout=controller_log,
                                       stderr=subprocess.STDOUT, timeout=45, check=True)
                if proc.wait(timeout=60) != 0:
                    raise RuntimeError('native world failed: '+str(logpath))
            text = logpath.read_text()
            if tcp:
                text += (OUT/f'{layout.identifier}-controller.log').read_text()
            # The local sandbox cannot bind AF_UNIX. --tcp uses the official
            # extern-controller transport; record the rejected local listener,
            # and allow only that exact diagnosed error in this explicit mode.
            errors = [line for line in text.splitlines() if line.startswith('ERROR:')]
            if tcp:
                errors = [line for line in errors if not (line.startswith('ERROR: Cannot listen to the local server (server name = ')
                          and "QLocalServer::listen: Unknown error 1" in line)]
            if errors or 'Traceback (most recent call last)' in text:
                raise RuntimeError('native errors: '+str(logpath))
            records = [json.loads(line.split('GP_U_GEOMETRY ',1)[1]) for line in text.splitlines()
                       if line.startswith('GP_U_GEOMETRY ')]
            result=json.loads(native_data.read_text()) if native_data.exists() else None
            if (result is None or result['configuration']!=layout.identifier or
                    result['claim']!='static-native-perception-only' or
                    len(result['gates'])!=len(layout.gates) or len(result['terminal'])!=3 or
                    result['timestep_ms']!=8 or any(record!=result for record in records)):
                raise RuntimeError('missing exact native perception evidence')
            summaries.append(result)
            print('PASS static native R2025a '+layout.identifier, flush=True)
        finally:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            target.unlink(missing_ok=True)
            project.unlink(missing_ok=True)
    (OUT/'summary.json').write_text(json.dumps(dict(claim='static-perception-only',
        webots_version=version, webots_image=os.environ.get('WEBEEBLOCKS_GP_WEBOTS_IMAGE'),
        webots_binary_sha256=hashlib.sha256((home/'bin/webots-bin').read_bytes()).hexdigest(), tcp=tcp,
        results=summaries), indent=2)+'\n')
    # Deadline source is a separate bounded increment; retain every existing
    # geometry assertion and add native authority evidence when present.
    if (ROOT/'controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp').exists():
        from run_grand_prix_u_deadline_native import run_native as run_deadline
        run_deadline(home)
    if partition == 'all':
        run_contact_campaign(home)
    write_manifest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--tcp', action='store_true')
    parser.add_argument('--partition', choices=('all', 'core', 'contacts'),
                        default='all')
    args = parser.parse_args()
    partition = args.partition
    print('GP_U_GEOMETRY_ENTRY native='+str(args.native)+' partition='+partition, flush=True)
    subprocess.run([sys.executable, str(ROOT/'tools/ci/test_grand_prix_u_geometry.py')], check=True)
    subprocess.run([sys.executable, str(ROOT/'tools/ci/test_grand_prix_route_solid_v2.py')], check=True)
    if args.native:
        run_native(Path(os.environ['WEBOTS_HOME']), args.tcp, partition=partition)
        return
    if args.tcp:
        raise ValueError('--tcp requires --native')
    if not shutil.which('docker'):
        raise RuntimeError('Docker absent; required native evidence unavailable')
    assets = ROOT/'.ci-grand-prix-u-webots'
    if not assets.exists():
        subprocess.run(['git','clone','--depth=1','--filter=blob:none','--sparse','--branch','R2025a',
                        'https://github.com/cyberbotics/webots.git',str(assets)], check=True)
        subprocess.run(['git','-C',str(assets),'sparse-checkout','set','projects/robots/bitcraze/crazyflie',
                        'projects/objects/backgrounds','projects/objects/floors','projects/appearances',
                        'projects/default'], check=True)
    if subprocess.check_output(['git','-C',str(assets),'rev-parse','HEAD'],text=True).strip() != SOURCE:
        raise RuntimeError('unexpected R2025a source')
    subprocess.run(['docker','pull',IMAGE], check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    # Explicit entry point and startup diagnostics separate preparation from
    # geometry. Always retain a file before Docker can block or fail.
    with tempfile.TemporaryDirectory(prefix='gp-u-geometry-') as temporary:
        cid=Path(temporary)/'container.cid'
        args=['docker','run','--rm','--cidfile',str(cid),'--entrypoint','/bin/bash',
              '-e','WEBOTS_HOME=/usr/local/webots',
              '-e',f'WEBEEBLOCKS_GP_WEBOTS_IMAGE={IMAGE}',
              '-v',f'{ROOT}:/workspace',
              '-v',f'{assets / "projects"}:/usr/local/webots/projects:ro','-w','/workspace',
              IMAGE,'-lc',
              "python3 -u -c 'import sys; print(\"GP_U_CONTAINER_PYTHON\",sys.version,flush=True)'\n"
              # Seven geometry + five time + fifty-six existing runtime probes,
              # plus five blocking-file composition/transition probes.
              # Simulation deadlines and every per-case assertion are unchanged.
              'timeout -k 5s 1200s xvfb-run -a python3 -u tools/ci/run_grand_prix_u_geometry.py --native --partition '+partition]
        try:
            with (OUT/'docker.log').open('w') as log:
                log.write('GP_U_CONTAINER_START image='+IMAGE+'\n');log.flush()
                subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1260)
        finally:
            if cid.exists():
                identifier=cid.read_text().strip()
                if not re.fullmatch('[0-9a-f]{64}',identifier):
                    raise RuntimeError('invalid owned container identity; cleanup unproven')
                state=subprocess.run(['docker','inspect','--format','{{.State.Running}}',identifier],
                                     capture_output=True,text=True,timeout=10)
                if state.returncode==0 and state.stdout.strip()=='true':
                    stop=subprocess.run(['docker','stop','--time','5',identifier],
                                        capture_output=True,text=True,timeout=20)
                    if stop.returncode:raise RuntimeError('owned container retirement unproven')


if __name__ == '__main__': main()
