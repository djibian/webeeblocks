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


def run_native(home, tcp=False):
    version = (home/'resources/version.txt').read_text().strip()
    if version != 'R2025a':
        raise RuntimeError('required Webots R2025a unavailable: '+version)
    OUT.mkdir(parents=True, exist_ok=True)
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
    manifest = {p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in OUT.rglob('*') if p.is_file() and p != OUT/'sha256.json'}
    (OUT/'sha256.json').write_text(json.dumps(manifest, indent=2)+'\n')



def run_full_route_matrix_native(home):
    """Falsify all 12 canonical geometries with actual R2025a L/H contacts.

    The existing probe implementations own their real observations, refusal
    rules and per-case 120-s caps. Never replace missing proof with a mock.
    """
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('full native matrix needs pinned Webots R2025a')
    from tools.grand_prix.route_courses_v2 import reference_course
    from tools.ci import run_grand_prix_v2_contact_native as contact
    from tools.ci import run_grand_prix_v2_h_native as h_probe

    indices = tuple(range(12))
    contact.native_run(home, indices)
    h_probe.native_run(home, indices, output_root=OUT / 'route-h-native')
    expected = [reference_course(index).identifier for index in indices]
    for source in (contact.OUT, OUT / 'route-h-native'):
        summaries = list(source.glob('invocation-*/summary.json'))
        if len(summaries) != 1:
            raise RuntimeError('missing or ambiguous full native matrix summary')
        summary_path = summaries[0]
        summary = json.loads(summary_path.read_text())
        results = summary.get('results') if type(summary) is dict else None
        if (summary.get('webots') != 'R2025a' or type(results) is not list
                or [r.get('configuration') for r in results
                    if type(r) is dict] != expected or len(results) != 12):
            raise RuntimeError('incomplete full native matrix')
        for position, (identifier, record) in enumerate(zip(expected, results)):
            expected_file = f'{position:02d}-{identifier}/native.json'
            if record.get('evidence_file') != expected_file:
                raise RuntimeError('native matrix evidence path mismatch')
            file = summary_path.parent / expected_file
            if (not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()
                    != record.get('evidence_sha256')):
                raise RuntimeError('native matrix evidence digest mismatch')
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {file.relative_to(OUT).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
                for file in OUT.rglob('*') if file.is_file() and file != OUT / 'sha256.json'}
    (OUT / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')


def run_evaluator_native_only(home):
    """Own both exact native route-evaluator witnesses in a separate CI leg.

    No soft PASS: production pilot and byte-identical probe must compile;
    idle READY/revocation and flight/LAND/RESET must both finish R2025a.
    """
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('required native R2025a evaluator unavailable')
    env = os.environ.copy()
    env.update(WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true',
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    from tools.ci.run_grand_prix_route_evaluator_native import run_native as run_evaluator
    evidence = OUT / 'route-evaluator-native'
    evidence.mkdir(parents=True, exist_ok=True)
    with (evidence / 'production-pilot-build.log').open('w') as log:
        subprocess.run(['make', '-C', str(ROOT / 'controllers/grand_prix_route_flight')],
                       env=env, stdout=log, stderr=subprocess.STDOUT,
                       timeout=90, check=True)
    run_evaluator(home, env)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--tcp', action='store_true')
    parser.add_argument('--evaluator-only', action='store_true')
    parser.add_argument('--full-matrix-only', action='store_true')
    args = parser.parse_args()
    print('GP_U_GEOMETRY_ENTRY native='+str(args.native), flush=True)
    subprocess.run([sys.executable, str(ROOT/'tools/ci/test_grand_prix_u_geometry.py')], check=True)
    subprocess.run([sys.executable, str(ROOT/'tools/ci/test_grand_prix_route_solid_v2.py')], check=True)
    if args.evaluator_only and args.full_matrix_only:
        raise ValueError('native matrix and evaluator modes are exclusive')
    if args.tcp and (not args.native or args.evaluator_only or args.full_matrix_only):
        raise ValueError('--tcp requires full --native geometry')
    if args.native:
        if args.evaluator_only:
            run_evaluator_native_only(Path(os.environ['WEBOTS_HOME']))
        elif args.full_matrix_only:
            run_full_route_matrix_native(Path(os.environ['WEBOTS_HOME']))
        else:
            run_native(Path(os.environ['WEBOTS_HOME']), args.tcp)
        return
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
    with tempfile.TemporaryDirectory(prefix=('gp-u-evaluator-' if args.evaluator_only else
                                              'gp-v2-matrix-' if args.full_matrix_only else
                                              'gp-u-geometry-')) as temporary:
        cid=Path(temporary)/'container.cid'
        args=['docker','run','--rm','--cidfile',str(cid),'--entrypoint','/bin/bash',
              '-e','WEBOTS_HOME=/usr/local/webots',
              '-e',f'WEBEEBLOCKS_GP_WEBOTS_IMAGE={IMAGE}',
              '-v',f'{ROOT}:/workspace',
              '-v',f'{assets / "projects"}:/usr/local/webots/projects:ro','-w','/workspace',
              IMAGE,'-lc',
              "python3 -u -c 'import sys; print(\"GP_U_CONTAINER_PYTHON\",sys.version,flush=True)'\n"
              # Independent native campaigns: U/L/H geometry retains its
              # historical 1350 s container cap. Evaluator READY/revocation
              # and flight/LAND/RESET have their own mandatory Runtime job
              # (900 s cap), without changing any per-case native timeout.
              + ('timeout -k 5s 900s xvfb-run -a python3 -u tools/ci/run_grand_prix_u_geometry.py --native --evaluator-only'
                 if args.evaluator_only else
                 'timeout -k 5s 1350s xvfb-run -a python3 -u tools/ci/run_grand_prix_u_geometry.py --native --full-matrix-only'
                 if args.full_matrix_only else
                 'timeout -k 5s 1350s xvfb-run -a python3 -u tools/ci/run_grand_prix_u_geometry.py --native')]
        try:
            with (OUT/'docker.log').open('w') as log:
                log.write('GP_U_CONTAINER_START image='+IMAGE+'\n');log.flush()
                subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1400)
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
