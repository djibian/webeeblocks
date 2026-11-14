#!/usr/bin/env python3
"""Fail-closed R2025a GUI proof of the actual Grand Prix Route Blockly PAUSE.

Experimental CI only. The production world, real route flight binary, evaluator,
and real Blockly modules are kept unchanged. A temporary HTML copy receives one
test-only browser stimulus, which uses the normal buttons and WWI RobotWindow.
It cannot authorize a mission or bypass native STOP/RESET, deadline or oracles.
"""
import contextlib
import hashlib
import json
import os
import re
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.run_product_vertical_native import compile_native
from tools.grand_prix.launch_linux import ensure_webots_assets, ensure_blockly_assets
sys.path.insert(0, str(ROOT / 'tools/ci'))
from runtime_v2_outcome_assets import prepare as prepare_pinned_assets

OUT = ROOT / 'ci-artifacts/runtime-v2-webots/product-native-pause'
WINDOW_LOSS_MODE = False  # Test-only second actual R2025a/Chrome run.
FIXTURE = ROOT / 'tools/ci/fixtures/grand_prix_route_pause_browser.js'
HTML = ROOT / 'plugins/robot_windows/grand_prix_route_v2/grand_prix_route_v2.html'
BROWSER = ROOT / 'tools/ci/webots_runtime_v2_browser.sh'
SCHEMA = 'gp-route-native-pause-browser-v1'
EXPECTED = (
    'REAL_UI_READY', 'BLOCKLY_PROGRAM_BUILT', 'BEFORE_TAKEOFF_PAUSED',
    'BEFORE_TAKEOFF_RESUMED', 'FROZEN_CLOCK_START', 'FROZEN_CLOCK_END',
    'INFLIGHT_RESUMED', 'STOP_WHILE_TRULY_PAUSED', 'STOP_RELEASED',
    'RESET_CONFIRMED', 'PASS')
QT_SETTINGS = r"""
import sys
from PyQt5.QtCore import QSettings
if __import__('os').geteuid() == 0:
    QSettings.setPath(QSettings.NativeFormat,QSettings.UserScope,'/root/.config/')
p=QSettings(QSettings.NativeFormat,QSettings.UserScope,'Cyberbotics','Webots-R2025a')
p.setFallbacksEnabled(False)
p.setValue('General/theme','webots_night.qss')
p.setValue('General/telemetry',False)
p.setValue('RobotWindow/browser',sys.argv[1])
p.setValue('RobotWindow/newBrowserWindow',False)
p.sync()
r=QSettings(QSettings.NativeFormat,QSettings.UserScope,'Cyberbotics','Webots-R2025a')
r.setFallbacksEnabled(False)
if p.status()!=QSettings.NoError or r.status()!=QSettings.NoError or \
   r.value('General/telemetry',type=bool) is not False or \
   r.value('General/theme')!='webots_night.qss' or \
   r.value('RobotWindow/browser')!=sys.argv[1]:
    raise RuntimeError('Webots R2025a real Qt settings not established')
print('GP_ROUTE_NATIVE_PAUSE_QT_PREFLIGHT_PASS',r.fileName(),flush=True)
"""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def install_official_assets_for_native_probe(home, folder):
    """Populate only missing official R2025a files in this disposable CI container.

    The pinned source, each size/SHA256/Git blob, and the exact localized
    world are verified BEFORE running the real production flight. Never
    replace an existing mismatching resource or substitute a simplified PROTO.
    """
    # The real route generator already emits four offline webots:// EXTERNPROTOs.
    # The shared asset preparer expects the *remote* pinned R2025a form and
    # localizes those four URLs itself. Reconstruct only its temporary input;
    # the resulting world MUST match the canonical route byte for byte.
    canonical = active_course_world(reference_course(5))
    local = 'EXTERNPROTO "webots://'
    remote = ('EXTERNPROTO "https://raw.githubusercontent.com/'
              'cyberbotics/webots/R2025a/')
    if (canonical.count(local) != 4 or canonical.count('webots://') != 4 or
            'raw.githubusercontent.com/cyberbotics/webots/' in canonical):
        raise RuntimeError('unexpected Grand Prix official R2025a PROTO inventory')
    reconstructed = canonical.replace(local, remote)
    if (reconstructed.count(remote) != 4 or
            reconstructed.replace(remote, local) != canonical):
        raise RuntimeError('Grand Prix official PROTO source reconstruction changed scene')
    original = folder / 'route-official-source.wbt'
    original.write_text(reconstructed)
    localized, projects = prepare_pinned_assets(
        folder / 'verified-official-assets', original,
        OUT / 'verified-official-assets.json')
    if localized.read_text() != canonical:
        raise RuntimeError('pinned official localization changed Grand Prix route scene')
    for source in projects.rglob('*'):
        if not source.is_file():
            continue
        destination = home / 'projects' / source.relative_to(projects)
        if destination.is_symlink():
            raise RuntimeError('untrusted Webots asset symlink: ' + str(destination))
        if destination.exists():
            if not destination.is_file() or sha(destination) != sha(source):
                raise RuntimeError('mismatching installed R2025a asset: ' + str(destination))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    ensure_webots_assets(home)
    ensure_blockly_assets()
    return localized


def prepare_project(folder, port):
    project = folder / 'project'
    (project / 'worlds').mkdir(parents=True)
    (project / 'controllers').symlink_to(ROOT / 'controllers', target_is_directory=True)
    plugin_root = project / 'plugins/robot_windows'
    plugin_root.mkdir(parents=True)
    for name in ('blockly', 'blockly_v2'):
        (plugin_root / name).symlink_to(
            ROOT / 'plugins/robot_windows' / name, target_is_directory=True)
    route = plugin_root / 'grand_prix_route_v2'
    route.mkdir()
    shutil.copy2(HTML, route / 'grand_prix_route_v2.html')
    shutil.copy2(HTML.parent / 'setup.js', route / 'setup.js')
    original = (route / 'grand_prix_route_v2.html').read_text()
    if original.count('</body>') != 1 or \
       '<script src="setup.js"></script>' not in original or \
       'src="../blockly_v2/main.js"' not in original:
        raise RuntimeError('Real route Blockly page no longer has canonical anchors')
    (route / 'grand_prix_route_v2.html').write_text(original.replace(
        '</body>', '<script src="grand_prix_pause_browser_probe.js"></script>\n</body>'))
    driver = FIXTURE.read_text()
    if driver.count('__TRACE_PORT__') != 1 or driver.count('__WINDOW_LOSS_MODE__') != 1:
        raise RuntimeError('unbound test-only loopback trace port / native loss mode')
    (route / 'grand_prix_pause_browser_probe.js').write_text(
        driver.replace('__TRACE_PORT__', str(port)).replace(
            '__WINDOW_LOSS_MODE__', 'true' if WINDOW_LOSS_MODE else 'false'))
    world = project / 'worlds/route.wbt'
    world.write_text(active_course_world(reference_course(5)).replace(
        'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', 'webots://'))
    return project, world


def trace_server():
    OUT.mkdir(parents=True, exist_ok=True)
    journal = OUT / 'browser-events.jsonl'
    journal.unlink(missing_ok=True)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != '/trace':
                self.send_error(404)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size < 8192:
                    raise ValueError('invalid event length')
                event = json.loads(self.rfile.read(size))
                if (type(event) is not dict or event.get('schema') != SCHEMA or
                    type(event.get('stage')) is not str or
                    len(event['stage']) > 80 or
                    type(event.get('wall_ms')) is not int):
                    raise ValueError('invalid browser event')
                packet = {'host_wall_s': time.monotonic(), 'event': event}
                with lock:
                    with journal.open('a', encoding='utf-8') as output:
                        output.write(json.dumps(packet, sort_keys=True) + '\n')
                        output.flush()
                        os.fsync(output.fileno())
            except (ValueError, TypeError, json.JSONDecodeError):
                self.send_error(400)
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, journal


def stop_group(process):
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=4)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=4)


def events(journal):
    result = []
    if journal.exists():
        for line in journal.read_text().splitlines():
            result.append(json.loads(line)['event'])
    return result


def verify_native_stop_postconditions(native, items):
    # PAUSE/STOP/RESET proof is NOT a successful Grand Prix mission.
    # The actual 0.4 m flight at its origin crosses the 15 s native takeoff
    # exemption under the 0.60 m minimum, legitimately closing the oracle.
    lines = native.splitlines()
    sent = [e['value'] for e in items if e['stage'] == 'RESET_NATIVE_REQUEST_SENT']
    received = [e['value'] for e in items if e['stage'] == 'RESET_NATIVE_RESPONSE_RECEIVED']
    confirmed = [e['value'] for e in items if e['stage'] == 'RESET_CONFIRMED']
    if (len(sent) != 1 or len(received) != 1 or len(confirmed) != 1 or
            type(confirmed[0]) is not dict or confirmed[0].get('state') != 'PRÊT' or
            type(sent[0]) is not dict or type(received[0]) is not dict or
            type(sent[0].get('id')) is not int or sent[0]['id'] < 1 or
            sent[0].get('pendingBeforeSend') is not True or
            received[0].get('id') != sent[0]['id'] or
            received[0].get('pendingAtArrival') is not True or
            received[0].get('raw') !=
                f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE {sent[0]['id']} OK"):
        raise RuntimeError('native RESET request and exact in-flight ACK not attested')
    reset_trace = [i for i, line in enumerate(lines)
                   if line.startswith('WEBEEBLOCKS_RUNTIME_V2 TRACE RESET ')]
    reset_reply = [i for i, line in enumerate(lines) if line == received[0]['raw']]
    if len(reset_trace) != 1 or len(reset_reply) != 1 or reset_trace[0] >= reset_reply[0]:
        raise RuntimeError('real native RESET postcondition missing')
    closes = [(i, re.fullmatch(
        r"GP_ROUTE_EVALUATOR_CLOSED attempt=1 time_ms=([1-9][0-9]*) "
        r"reason=low-outside-zone detail='low-outside-zone'", line))
        for i, line in enumerate(lines) if line.startswith('GP_ROUTE_EVALUATOR_CLOSED ')]
    losses = [i for i, line in enumerate(lines)
              if line.startswith('GP_ROUTE_SAFETY_LAND ')]
    forced = [(i, re.fullmatch(
        r'GP_U_DEADLINE time_ms=([1-9][0-9]*) command=LAND interrupted_id=-1', line))
        for i, line in enumerate(lines) if line.startswith('GP_U_DEADLINE ')]
    if not closes and not losses and not forced:
        return None  # No negative oracle on this host; RESET remains required.
    admissions = [re.fullmatch(r'GP_U_ADMISSION attempt=1 start_ms=([0-9]+)', line)
                  for line in lines if line.startswith('GP_U_ADMISSION ')]
    ground = [i for i, line in enumerate(lines)
              if line.startswith('GP_U_LAND_GROUND_READY ')]
    land_trace = [i for i, line in enumerate(lines)
                  if line == 'WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1']
    land_ack = [i for i, line in enumerate(lines)
                if line == 'WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 OK']
    if (len(closes) != 1 or closes[0][1] is None or len(losses) != 1 or
            lines[losses[0]] != 'GP_ROUTE_SAFETY_LAND evaluator-unavailable' or
            len(forced) != 1 or forced[0][1] is None or
            len(admissions) != 1 or admissions[0] is None or
            len(ground) != 1 or len(land_trace) != 1 or len(land_ack) != 1):
        raise RuntimeError('unexpected evaluator loss or unverified native failsafe LAND')
    close_ms = int(closes[0][1].group(1))
    admitted_ms = int(admissions[0].group(1))
    land_ms = int(forced[0][1].group(1))
    if (close_ms - admitted_ms < 15000 or close_ms - admitted_ms >= 210000 or
            not (closes[0][0] < losses[0] < forced[0][0] < ground[0] <
                 land_trace[0] < land_ack[0] < reset_trace[0] < reset_reply[0]) or
            not (0 < land_ms - close_ms <= 128)):
        raise RuntimeError('negative oracle / independent LAND / RESET ordering invalid')
    return 'low-outside-zone'  # Native failed mission remains failed.


def verify(log_path, journal, compiled, world):
    items = events(journal)
    stages = [e['stage'] for e in items]
    if 'FAIL' in stages:
        failure = next(e.get('value') for e in items if e['stage'] == 'FAIL')
        raise RuntimeError('real Grand Prix browser failure: ' + repr(failure))
    if not all(stage in stages for stage in EXPECTED):
        raise RuntimeError('native product proof missing stages: ' +
                           repr([stage for stage in EXPECTED if stage not in stages]))
    native_events = [e for e in items if e['stage'] in
                     ('NATIVE_PAUSED','NATIVE_RESUMED')]
    expected_native = (('PAUSED',1), ('RESUMED',1), ('PAUSED',2),
                       ('RESUMED',2), ('PAUSED',3))
    ack_re = re.compile(
        r'^GP_ROUTE_PAUSE_V1 (PAUSED|RESUMED) nonce=([0-9a-f]{32})'
        r' attempt=([1-9][0-9]*) seq=([1-9][0-9]*)$')
    parsed = [ack_re.fullmatch(e['value']) if type(e['value']) is str else None
              for e in native_events]
    if (len(parsed) != len(expected_native) or any(m is None for m in parsed) or
        tuple((m.group(1),int(m.group(4))) for m in parsed) != expected_native or
        len({(m.group(2),m.group(3)) for m in parsed}) != 1):
        raise RuntimeError('native ACK sequence, attempt, nonce or STOP fencing invalid')
    if (sum(e['stage']=='UI_PAUSED' for e in items) != 3 or
        sum(e['stage']=='UI_RESUMED' for e in items) != 2):
        raise RuntimeError('native-ACK/UI debugger states disagree')
    ack_count = len(parsed)
    clock_events = [x for x in items if x['stage'] in
                    ('FROZEN_CLOCK_START','FROZEN_CLOCK_END')]
    clocks = [e['value'] for e in clock_events]
    if (len(clocks) != 2 or any(type(x) not in (int,float) or x < 0 for x in clocks)
        or clocks[0] != clocks[1] or
        clock_events[1]['wall_ms'] - clock_events[0]['wall_ms'] < 1300):
        raise RuntimeError('native mission clock did not stay frozen for real wall time')
    if stages.index('BEFORE_TAKEOFF_PAUSED') >= stages.index('BEFORE_TAKEOFF_RESUMED') or \
       stages.index('STOP_WHILE_TRULY_PAUSED') >= stages.index('RESET_CONFIRMED'):
        raise RuntimeError('browser/WWI trace order invalid')
    native = log_path.read_text(errors='replace')
    if 'WEBEEBLOCKS_RUNTIME_V2 READY' not in native:
        raise RuntimeError('real product binary did not publish runtime READY')
    if 'Segmentation fault' in native:
        raise RuntimeError('native segmentation fault during integration proof')
    negative_oracle = verify_native_stop_postconditions(native, items)
    report = {'schema': 'gp-route-native-pause-e2e-r2025a-v1',
              'claim': 'real-route-binary-real-blockly-robot-window-pause',
              'status': 'NATIVE_E2E_PASS_NOT_PEDAGOGICAL_ACCEPTANCE',
              'webots': 'R2025a', 'world_sha256': sha(world),
              'route_html_sha256': sha(HTML),
              'route_js_sha256': sha(HTML.parent/'setup.js'),
              'flight_binary_sha256': compiled['product_binary_sha256'],
              'browser_fixture_sha256': sha(FIXTURE),
              'native_ack_count': ack_count, 'clock_samples_s': clocks,
              'negative_mission_oracle': negative_oracle,
              'grand_prix_mission_success_claimed': False,
              'evidence_sha256': sha(journal), 'webots_log_sha256': sha(log_path),
              'product_safety_relaxation': False, 'physical_flight_authorized': False}
    (OUT / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('GP_ROUTE_NATIVE_PAUSE_PRODUCT_PASS', json.dumps(report), flush=True)


def probe_real_route_page(port, timeout=32):
    """Use Webots' OWN HTTP server; never serve an imitation page or backend.

    Even with multiple Robots, Webots R2025a opens a Robot Window only when
    the correct Robot is selected. The test may open its legitimate URL
    explicitly, but the real browser must prove native WWI afterward.
    """
    url = (f'http://localhost:{port}/robot_windows/grand_prix_route_v2/'
           'grand_prix_route_v2.html?name=Crazyflie%20WebeeBlocks')
    deadline = time.monotonic() + timeout
    last = 'no HTTP response'
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                status = response.status
                page = response.read(180000).decode('utf8', 'replace')
            if status != 200 or 'grand_prix_pause_browser_probe.js' not in page or \
               'src="../blockly_v2/main.js"' not in page or \
               'src="setup.js"' not in page:
                raise RuntimeError('not the genuine test-bound Grand Prix UI')
            (OUT / 'robot-window-http-preflight.json').write_text(json.dumps({
                'url': url, 'http_status': status, 'native_webots_port': port,
                'html_sha256': hashlib.sha256(page.encode('utf8')).hexdigest(),
                'test_script_present': True,
                'claim': 'real-Webots-HTTP-page-only-not-WWI-success'
            }, sort_keys=True, indent=2) + '\n')
            return url
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            last = type(error).__name__ + ': ' + str(error)
        time.sleep(.25)
    raise RuntimeError('real Webots RobotWindow HTTP preflight timed out: ' + last)


def unused_local_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
        channel.bind(('127.0.0.1', 0))
        return channel.getsockname()[1]


def main():
    home = Path(os.environ.get('WEBOTS_HOME', '/usr/local/webots'))
    if (home / 'resources/version.txt').read_text().strip() != 'R2025a':
        raise RuntimeError('R2025a native exact version required')
    if not Path('/usr/bin/google-chrome').is_file() or \
       shutil.which('xvfb-run') is None or not BROWSER.is_file():
        raise RuntimeError('real Chrome / Xvfb Robot Window unavailable')
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('result.json','browser-launch.log','browser-stdout.log',
                 'webots.log','qt-preflight.log','robot-window-http-preflight.json'):
        (OUT/name).unlink(missing_ok=True)
    compiled = compile_native(home)
    server, journal = trace_server()
    process = browser_process = None
    browser_stdout = None
    try:
        # The temporary world, Webots profiles and Chrome caches MUST outlive
        # their writers. Register process teardown *after* entering the temp
        # context so ExitStack runs it first, even if verification raises.
        # Suppressing rmtree's ENOTEMPTY would hide a live native subprocess.
        with contextlib.ExitStack() as cleanup:
            folder = Path(cleanup.enter_context(
                tempfile.TemporaryDirectory(prefix='gp-route-real-pause-')))
            cleanup.callback(lambda: browser_stdout.close()
                             if browser_stdout is not None else None)
            cleanup.callback(lambda: stop_group(process))
            cleanup.callback(lambda: stop_group(browser_process))
            localized = install_official_assets_for_native_probe(home, folder)
            project, world = prepare_project(folder, server.server_port)
            if world.read_bytes() != localized.read_bytes():
                raise RuntimeError('Grand Prix course differs from pinned official localization')
            (OUT/'world.wbt').write_bytes(world.read_bytes())
            env = dict(os.environ, WEBOTS_HOME=str(home), PYTHONPATH=str(ROOT),
                GP_ROUTE_EVALUATOR_SOURCE=str(ROOT), WBB_GP_PRODUCT_TRACE='1',
                LIBGL_ALWAYS_SOFTWARE='true',
                WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
                WEBEEBLOCKS_CI_ARTIFACT_DIR=str(OUT))
            for key, part in (('XDG_CONFIG_HOME','config'),
                              ('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime')):
                dest = folder / part
                dest.mkdir(mode=0o700)
                env[key] = str(dest)
            browser = BROWSER
            if WINDOW_LOSS_MODE:
                # Webots spawns the REAL Robot Window. A temporary wrapper
                # records its PID before exec; the host later terminates that
                # exact Chrome process, never the simulator or a fake WWI.
                browser = folder / 'browser-window-loss-wrapper.sh'
                browser.write_text(
                    '#!/usr/bin/env bash\nset -euo pipefail\n'
                    'printf "%s\\n" "$" > "$WEBEEBLOCKS_CI_ARTIFACT_DIR/browser-main.pid"\n'
                    'exec "' + str(BROWSER) + '" "$@"\n')
                browser.chmod(0o700)
            proc = subprocess.run(['/usr/bin/python3','-c',QT_SETTINGS,str(browser)],
                                  cwd=ROOT,env=env,text=True,capture_output=True,
                                  timeout=12,check=False)
            (OUT/'qt-preflight.log').write_text(proc.stdout + proc.stderr)
            if proc.returncode != 0:
                raise RuntimeError('real R2025a GUI Qt settings unavailable')
            webots_port=unused_local_port()
            command = ['xvfb-run','-a','-e',str(OUT/'xvfb.log'),
                       '-s','-screen 0 1280x900x24',
                       str(home/'webots'),'--stdout','--stderr','--minimize',
                       f'--port={webots_port}','--mode=realtime',str(world)]
            log = OUT/'webots.log'
            with log.open('w') as output:
                process = subprocess.Popen(command,cwd=project,env=env,
                  stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
                # The two-robot world need not auto-select the Crazyflie.
                # Do not wait 550 s for an implicitly unopened window.
                ready_deadline = time.monotonic() + 90
                while time.monotonic() < ready_deadline:
                    if process.poll() is not None:
                        raise RuntimeError('real Grand Prix Webots ended before READY')
                    if 'WEBEEBLOCKS_RUNTIME_V2 READY' in log.read_text(errors='replace'):
                        break
                    time.sleep(.25)
                else:
                    raise RuntimeError('real Grand Prix native READY unavailable')
                route_url = probe_real_route_page(webots_port)
                # Give Webots the opportunity to open the default selected
                # Robot Window; if none opens, the test driver opens the exact
                # same genuine URL with the approved R2025a Chrome executable.
                automatic_deadline = time.monotonic() + 4
                while time.monotonic() < automatic_deadline:
                    if (OUT/'browser-launch.log').is_file() and \
                       (OUT/'browser-launch.log').stat().st_size > 0:
                        break
                    time.sleep(.2)
                if not (OUT/'browser-launch.log').is_file():
                    browser_stdout = (OUT/'browser-stdout.log').open('w')
                    browser_process = subprocess.Popen(
                        [str(browser), route_url], cwd=project, env=env,
                        stdout=browser_stdout, stderr=subprocess.STDOUT,
                        start_new_session=True)
                ui_deadline = time.monotonic() + 95
                deadline = time.monotonic() + 550
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('real product Webots process ended early')
                    current = events(journal)
                    if any(item['stage']=='FAIL' for item in current):
                        raise RuntimeError('real product browser reported FAIL')
                    if any(item['stage']=='PASS' for item in current):
                        break
                    if (not any(item['stage']=='REAL_UI_READY' for item in current)
                        and time.monotonic() > ui_deadline):
                        raise RuntimeError('real Webots Robot Window failed to reach Blockly READY; '
                                           'inspect browser-stdout and native HTTP preflight')
                    if browser_process is not None and browser_process.poll() is not None:
                        raise RuntimeError('real Chrome exited before Blockly end-to-end PASS')
                    time.sleep(.25)
                else:
                    raise RuntimeError('real product RobotWindow end-to-end hard timeout 550s')
            if not (OUT/'browser-launch.log').exists() or \
               'google-chrome' not in (OUT/'browser-launch.log').read_text():
                # The launcher records the Chrome arguments; it need not repeat
                # the executable path, but must attest a nonempty actual launch.
                if not (OUT/'browser-launch.log').is_file() or \
                   (OUT/'browser-launch.log').stat().st_size == 0:
                    raise RuntimeError('real Grand Prix Chrome Robot Window never launched')
            verify(OUT/'webots.log',journal,compiled,OUT/'world.wbt')
    finally:
        # By this point ExitStack has retired Chrome and Webots and removed
        # their private directory. The trace server remains a separate owner.
        server.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
