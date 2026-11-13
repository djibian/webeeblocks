#!/usr/bin/env python3
"""External hard-timeout R2025a evidence: real GUI Robot Window -> WWI -> PAUSE.

Run inside the pinned Webots R2025a Docker container with Google Chrome.
Never exercise this in a flight scene or claim product pause support.
"""
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'ci-artifacts/runtime-v2-webots/native-pause'


def capture_x11_window_evidence(process_group):
    """Observe X11 window titles without clicking, or bypassing dialogs.

    xvfb-run owns the DISPLAY/XAUTHORITY in its child environment. Inspect
    only these two keys; never persist /proc/*/environ or other secrets.
    """
    evidence = ['X11_WINDOW_PROBE_V1']
    found = False
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            pid = int(entry.name)
            if os.getpgid(pid) != process_group:
                continue
            comm = (entry / 'comm').read_text(encoding='utf-8').strip()
            if comm not in ('webots-bin', 'webots'):
                continue
            raw = (entry / 'environ').read_bytes().split(b'\0')
            variables = {}
            for item in raw:
                if item.startswith((b'DISPLAY=', b'XAUTHORITY=')):
                    key, value = item.split(b'=', 1)
                    variables[key.decode('ascii')] = value.decode('utf-8', 'replace')
            if 'DISPLAY' not in variables:
                continue
            found = True
            evidence.append('process=' + comm + ' display=' + variables['DISPLAY'])
            probe_env = os.environ.copy()
            probe_env.update(variables)
            if shutil.which('xwininfo') is None:
                evidence.append('xwininfo=missing (x11-utils prerequisite)')
                continue
            result = subprocess.run(['xwininfo', '-root', '-tree'],
                                    env=probe_env, capture_output=True,
                                    text=True, timeout=3, check=False)
            evidence.append('xwininfo_returncode=' + str(result.returncode))
            evidence.append(result.stdout[-16000:])
            evidence.append(result.stderr[-2000:])
            break
        except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
            continue
    if not found:
        evidence.append('webots-display=unavailable')
    (OUT / 'x11-windows-at-deadline.txt').write_text(
        '\n'.join(evidence) + '\n', encoding='utf-8')


def run():
    home = Path(os.environ.get('WEBOTS_HOME', '/usr/local/webots'))
    version = (home / 'resources/version.txt').read_text().strip()
    if version != 'R2025a':
        raise RuntimeError('unsupported Webots version: ' + version)
    if shutil.which('xvfb-run') is None:
        raise RuntimeError('real GUI Xvfb is mandatory for WWI proof')
    if not Path('/usr/bin/google-chrome').is_file():
        raise RuntimeError('real Chrome Robot Window launcher unavailable')
    OUT.mkdir(parents=True, exist_ok=True)
    browser = ROOT / 'tools/ci/webots_runtime_v2_browser.sh'
    conf = Path.home() / '.config/Cyberbotics/Webots-R2025a.conf'
    conf.parent.mkdir(parents=True, exist_ok=True)
    # R2025a WbGuiApplication::setup() opens the modal Welcome dialog
    # without --batch when either General/theme or General/telemetry is
    # missing. Preseed a private, non-telemetry GUI profile instead of
    # suppressing all dialogs; preserve the real non-batch WWI experiment.
    conf.write_text('[General]\ntheme=webots_night.qss\ntelemetry=false\n'
                    '[RobotWindow]\nbrowser=' + str(browser) +
                    '\nnewBrowserWindow=false\n', encoding='utf-8')
    env = os.environ.copy()
    env.update(
        WEBOTS_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='true',
        WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true',
        WEBEEBLOCKS_CI_ARTIFACT_DIR=str(OUT),
    )
    # GUI requires these private XDG directories. They are not evidence files.
    with tempfile.TemporaryDirectory(prefix='gp-pause-r2025a-') as private:
        for key, name in (
            ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'),
            ('XDG_RUNTIME_DIR', 'runtime'),
        ):
            directory = Path(private) / name
            directory.mkdir(mode=0o700)
            env[key] = str(directory)
        xdg_conf = Path(env['XDG_CONFIG_HOME']) / 'Cyberbotics/Webots-R2025a.conf'
        xdg_conf.parent.mkdir(parents=True, exist_ok=True)
        xdg_conf.write_text(conf.read_text(encoding='utf-8'), encoding='utf-8')
        # The real R2025a GUI reads QSettings NativeFormat/UserScope.
        # In the previous native run X11 proved a blocking 'Welcome to
        # Webots R2025a' modal despite our handwritten INI files.
        # Use the *same Qt5 QSettings writer and the same root path override*
        # as WbPreferences::createInstance(), verify a fresh round-trip, and
        # persist the effective pathname for diagnosis. No user approval or
        # telemetry consent is synthesized: telemetry is explicitly False.
        qt_settings_writer = r"""
import json
import os
import sys
from PyQt5.QtCore import QSettings
if os.geteuid() == 0:
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, '/root/.config/')
settings = QSettings(QSettings.NativeFormat, QSettings.UserScope,
                     'Cyberbotics', 'Webots-R2025a')
settings.setFallbacksEnabled(False)
settings.setValue('General/theme', 'webots_night.qss')
settings.setValue('General/telemetry', False)
settings.setValue('RobotWindow/browser', sys.argv[1])
settings.setValue('RobotWindow/newBrowserWindow', False)
settings.sync()
readback = QSettings(QSettings.NativeFormat, QSettings.UserScope,
                     'Cyberbotics', 'Webots-R2025a')
readback.setFallbacksEnabled(False)
if (settings.status() != QSettings.NoError or
    readback.status() != QSettings.NoError or
    not readback.contains('General/theme') or
    not readback.contains('General/telemetry') or
    readback.value('General/telemetry', type=bool) is not False or
    readback.value('General/theme') != 'webots_night.qss' or
    readback.value('RobotWindow/browser') != sys.argv[1]):
    raise RuntimeError('R2025a Qt user-scope preferences not durable')
print(json.dumps({
    'schema': 'webeeblocks-webots-r2025a-qt-settings-preflight-v1',
    'effective_file': settings.fileName(),
    'theme_present': readback.contains('General/theme'),
    'telemetry_present': readback.contains('General/telemetry'),
    'telemetry_enabled': readback.value('General/telemetry', type=bool),
    'browser_path_matches': readback.value('RobotWindow/browser') == sys.argv[1]
}, sort_keys=True), flush=True)
"""
        qt_probe = subprocess.run(
            ['/usr/bin/python3', '-c', qt_settings_writer, str(browser)],
            env=env, cwd=ROOT, capture_output=True, text=True,
            check=False, timeout=10,
        )
        (OUT / 'qt-settings-preflight.log').write_text(
            'exit_code=' + str(qt_probe.returncode) + '\\n' +
            qt_probe.stdout[:2000] + qt_probe.stderr[-2000:],
            encoding='utf-8',
        )
        if qt_probe.returncode != 0:
            raise RuntimeError('R2025a native Qt settings preflight failed')
        world = ROOT / 'worlds/ci_webots_pause_wwi.wbt'
        # Controlled A/B against R2025a --batch: the exact prior native trace
        # reached REAL_TIME, returned from step(0), and Webots exited cleanly
        # *inside* the first positive step. This hypothesis does not imply PASS;
        # the real GUI, 45 s hard timeout and native postconditions stay strict.
        command = [
            'xvfb-run', '-a', '-e', str(OUT / 'xvfb.log'),
            '-s', '-screen 0 1280x900x24',
            str(home / 'webots'), '--stdout', '--stderr', '--minimize',
            '--mode=realtime', str(world),
        ]
        proc = None
        timed_out = False
        native_pass_observed = False
        wall_started = time.monotonic()
        with (OUT / 'webots.log').open('w', encoding='utf-8') as output:
            try:
                proc = subprocess.Popen(
                    command, cwd=ROOT, env=env, stdout=output,
                    stderr=subprocess.STDOUT, start_new_session=True,
                )
                deadline = wall_started + 45.0
                while proc.poll() is None:
                    # A non-batch GUI can remain open after the controller has
                    # produced its native terminal PASS. Do not wait for GUI
                    # shutdown as a substitute for the verified native proof.
                    try:
                        observed = (OUT / 'webots.log').read_text(
                            encoding='utf-8', errors='replace')
                    except OSError:
                        observed = ''
                    if 'GP_PAUSE_WWI_PASS {' in observed:
                        native_pass_observed = True
                        break
                    if time.monotonic() >= deadline:
                        timed_out = True
                        # Inspect modal/window state before Xvfb shutdown;
                        # this does not dismiss dialogs or manufacture a PASS.
                        capture_x11_window_evidence(proc.pid)
                        # Capture live process names before Xvfb is stopped.
                        try:
                            snapshot = subprocess.run(
                                ['ps', '-eo', 'pid,ppid,pgid,stat,comm'],
                                check=False, capture_output=True, text=True,
                                timeout=2)
                            (OUT / 'processes-at-deadline.txt').write_text(
                                snapshot.stdout, encoding='utf-8')
                        except (OSError, subprocess.TimeoutExpired):
                            pass
                        break
                    time.sleep(0.2)
            finally:
                if proc and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
        code = proc.returncode if proc else None
        wall_seconds = round(time.monotonic() - wall_started, 3)
    transcript = (OUT / 'webots.log').read_text(encoding='utf-8', errors='replace')
    browser_path = OUT / 'browser-launch.log'
    browser_text = browser_path.read_text(encoding='utf-8', errors='replace') if browser_path.exists() else ''
    stages = ('CONTROLLER_START', 'READY_SENT', 'BEGIN_RECEIVED',
              'PAUSE_REQUESTED', 'PAUSE_ATTESTED', 'RESUME_RECEIVED',
              'STALE_RESUME_REJECTED', 'CLOCK_PRE_RESUME',
              'MODE_REALTIME_REQUESTED', 'MODE_REALTIME_CALL_RETURNED',
              'STEP_ZERO_AFTER_RESUME_REQUESTED', 'STEP_ZERO_AFTER_RESUME_RETURNED',
              'MODE_REALTIME_ATTESTED', 'STEP_32_AFTER_RESUME_REQUESTED',
              'STEP_32_AFTER_RESUME_RETURNED', 'CLOCK_RESUMED_DELTA_MS', 'PASS')
    markers = {stage: 'GP_PAUSE_WWI_' + stage in transcript for stage in stages}
    # Diagnostic artefact is never evidence for a PASS; only native PASS
    # together with the real Robot Window launch and exact mode/time checks is.
    diagnostics = {'schema': 'webeeblocks-webots-pause-diagnostic-v1',
                   'webots_exit_code': code, 'browser_launched': bool(browser_text),
                   'browser_invocation': browser_text[:2000], 'stages': markers,
                   'timed_out': timed_out, 'wall_seconds': wall_seconds,
                   'native_pass_marker_observed': native_pass_observed,
                   'gui_terminated_after_native_pass': native_pass_observed and code != 0}
    (OUT / 'diagnostic.json').write_text(json.dumps(diagnostics, sort_keys=True, indent=2) + '\n',
                                         encoding='utf-8')
    if timed_out:
        raise RuntimeError('PAUSE/WWI native process deadline exceeded; inspect '
                           'diagnostic.json, xvfb.log and processes-at-deadline.txt')
    if not browser_text:
        raise RuntimeError('Robot Window browser not launched; inspect diagnostic.json and webots.log')
    if code != 0 and not native_pass_observed:
        raise RuntimeError('Webots nonzero exit ' + str(code) + '; inspect diagnostic.json')

    if 'Segmentation fault' in transcript or 'Traceback (most recent call last)' in transcript:
        raise RuntimeError('native crash/traceback')
    matches = re.findall(r'^GP_PAUSE_WWI_PASS (\{[^\n]+\})$', transcript, re.M)
    if len(matches) != 1 or not native_pass_observed:
        # On clean GUI exit we may read PASS only after the process has already
        # ended. Treat exactly one such native PASS as valid, without admitting
        # any other form of success.
        if len(matches) != 1 or (not native_pass_observed and code != 0):
            raise RuntimeError('missing/ambiguous native proof; consult webots.log and diagnostic.json')
    proof = json.loads(matches[0])
    if not (
        proof.get('schema') == 'webeeblocks-webots-pause-wwi-v1'
        and proof.get('simulation') == 'isolated-r2025a-only'
        and proof.get('frozen_delta_ms') == 0
        and proof.get('pause_wall_seconds', 0) >= 1.0
        and 32 <= proof.get('resumed_simulated_ms', -1) <= 64
        and proof.get('resume_via_robot_window_wwi') is True
        and proof.get('wrong_token_rejected', 0) >= 1
    ):
        raise RuntimeError('unqualified WWI pause result')
    result = dict(proof, webots_version=version, claim='native-transport-feasibility-only')
    (OUT / 'result.json').write_text(
        json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print('PASS isolated actual R2025a Webots PAUSE/step(0)/WWI/REAL_TIME', flush=True)


if __name__ == '__main__':
    run()
