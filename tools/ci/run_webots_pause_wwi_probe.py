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
    conf.write_text('[RobotWindow]\nbrowser=' + str(browser) +
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
        world = ROOT / 'worlds/ci_webots_pause_wwi.wbt'
        command = [
            'xvfb-run', '-a', '-s', '-screen 0 1280x900x24',
            str(home / 'webots'), '--stdout', '--stderr', '--batch',
            '--mode=realtime', str(world),
        ]
        proc = None
        with (OUT / 'webots.log').open('w', encoding='utf-8') as output:
            try:
                proc = subprocess.Popen(
                    command, cwd=ROOT, env=env, stdout=output,
                    stderr=subprocess.STDOUT, start_new_session=True,
                )
                try:
                    code = proc.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    raise RuntimeError('PAUSE/WWI native process deadline exceeded')
                if code != 0:
                    raise RuntimeError('Webots nonzero exit ' + str(code))
            finally:
                if proc and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
    transcript = (OUT / 'webots.log').read_text(encoding='utf-8', errors='replace')
    if 'Segmentation fault' in transcript or 'Traceback (most recent call last)' in transcript:
        raise RuntimeError('native crash/traceback')
    matches = re.findall(r'^GP_PAUSE_WWI_PASS (\{[^\n]+\})$', transcript, re.M)
    if len(matches) != 1:
        raise RuntimeError('missing/ambiguous native proof; consult webots.log')
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
