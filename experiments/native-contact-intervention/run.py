#!/usr/bin/env python3
"""Run the fixed #637 intervention in isolated native R2025a processes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def world(p, case):
    pos = list(p['position_m'])
    pos[2] += case['dz_m']
    floor = 'Solid { boundingObject Plane { size 4 4 } }' if case['floor'] else ''
    return f'''#VRML_SIM R2025a utf8
WorldInfo {{ basicTimeStep {p['step_ms']} randomSeed {p['random_seed']}
 optimalThreadCount 1 gravity {p['gravity_m_s2']} ERP {p['ERP']} CFM {p['CFM']} }}
Viewpoint {{ position 0 -1 1 orientation 1 0 0 0.8 }}
{floor}
DEF BODY Robot {{
 translation {' '.join(map(repr, pos))}
 rotation 0 1 0 {p['pitch_rad']}
 name "contact-body" controller "<extern>" supervisor TRUE
 children [ Shape {{ geometry Cylinder {{ radius {p['radius_m']} height {p['height_m']} }} }} ]
 boundingObject Cylinder {{ radius {p['radius_m']} height {p['height_m']} }}
 physics Physics {{ density -1 mass {p['mass_kg']} centerOfMass [ 0 0 0 ]
 inertiaMatrix [ {' '.join(map(repr, p['inertia_diagonal_kg_m2']))}, 0 0 0 ] }}
}}
'''

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--webots-home', required=True, type=Path)
    parser.add_argument('--xvfb', default=shutil.which('Xvfb'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    home, out = args.webots_home.resolve(), args.output.resolve()
    raw = (HERE/'protocol.json').read_bytes()
    p = json.loads(raw)
    assert (home/'resources/version.txt').read_text().strip() == 'R2025a'
    assert digest(home/'bin/webots-bin') == p['webots_bin_sha256']
    if not args.xvfb:
        raise RuntimeError('Xvfb required')
    out.mkdir(parents=True, exist_ok=False)
    (out/'protocol.json').write_bytes(raw)
    (out/'worlds').mkdir()
    env = {k:v for k,v in os.environ.items() if not k.lower().endswith('_proxy')}
    env.update(WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true', LP_NUM_THREADS='1',
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    env['LD_LIBRARY_PATH'] = str(home/'lib/webots') + ':' + env.get('LD_LIBRARY_PATH', '')
    env['PYTHONPATH'] = str(home/'lib/controller/python') + ':' + env.get('PYTHONPATH', '')
    display_port = free_port()
    assert display_port > 6000
    env['DISPLAY'] = '127.0.0.1:' + str(display_port-6000)
    provenance = dict(protocol_sha256=hashlib.sha256(raw).hexdigest(),
                      git_head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'], text=True).strip(),
                      kernel=subprocess.check_output(['uname','-a'], text=True).strip(),
                      input_sha256={f.name:digest(f) for f in HERE.glob('*.py')},
                      webots_bin_sha256=digest(home/'bin/webots-bin'))
    (out/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    results = []
    try:
        with (out/'xvfb.log').open('w') as xlog:
            xvfb = subprocess.Popen([args.xvfb, ':'+str(display_port-6000), '-ac',
                '-nolisten','unix','-nolisten','local','-listen','tcp','-screen','0','1280x1024x24'],
                env=env, stdout=xlog, stderr=subprocess.STDOUT)
            try:
                limit = time.monotonic()+10
                while True:
                    try:
                        with socket.create_connection(('127.0.0.1', display_port), timeout=.2):
                            break
                    except OSError:
                        if time.monotonic() > limit:
                            raise RuntimeError('Xvfb failed to listen; inspect log')
                        time.sleep(.1)
                for case in p['cases']:
                    case_dir = out/case['id']
                    case_dir.mkdir()
                    target = out/'worlds'/f"{case['id']}.wbt"
                    target.write_text(world(p, case))
                    port = free_port()
                    with (case_dir/'webots.log').open('w') as log:
                        process = subprocess.Popen([str(home/'webots'), '--batch','--minimize',
                            '--no-rendering','--mode=fast','--stdout','--stderr','--port='+str(port),str(target)],
                            cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT)
                        try:
                            limit = time.monotonic()+45
                            while 'Waiting for local or remote connection' not in (case_dir/'webots.log').read_text():
                                if process.poll() is not None or time.monotonic()>limit:
                                    raise RuntimeError('extern readiness absent; inspect retained log')
                                time.sleep(.1)
                            with (case_dir/'controller.log').open('w') as clog:
                                subprocess.run([str(home/'webots-controller'), '--protocol=tcp',
                                    '--ip-address=127.0.0.1','--port='+str(port),'--robot-name=contact-body',
                                    str(HERE/'contact_probe.py'),str(out/'protocol.json'),case['id'],str(case_dir/'result.json')],
                                    env=env, stdout=clog, stderr=subprocess.STDOUT, check=True, timeout=30)
                            assert process.wait(timeout=15) == 0
                        finally:
                            if process.poll() is None:
                                process.terminate()
                                try: process.wait(timeout=10)
                                except subprocess.TimeoutExpired:
                                    process.kill()
                                    process.wait()
                    results.append(json.loads((case_dir/'result.json').read_text()))
            finally:
                xvfb.terminate()
                xvfb.wait(timeout=10)
        (out/'results.json').write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')
    finally:
        # Called after closing logs and stopping all direct producers.
        (out/'sha256.json').write_text(json.dumps({str(f.relative_to(out)):digest(f)
            for f in sorted(out.rglob('*')) if f.is_file() and f.name!='sha256.json'}, indent=2)+'\n')
    print('Native one-step acquisition completed; analysis required; no product PASS')

if __name__ == '__main__':
    main()
