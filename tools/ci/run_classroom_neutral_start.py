"""Native progression from the empty classroom world, plus independent A3 flight.

The historical missions run unchanged first. Activity 3 uses its own test-only
world and controller binary, never the locked physical Crazyflie runtime.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
IMAGE='cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099'

def main()->int:
    # Preserve original Activity 1/2 native proof and its exit code.
    old=subprocess.run(
        [sys.executable,str(ROOT/'tools/ci/run_progression_sequence_mission.py')],
        cwd=ROOT,env={**os.environ,'WEBEEBLOCKS_CI_NEUTRAL_START':'1'},
        check=False)
    if old.returncode:
        return old.returncode
    for command in (
        [sys.executable,'tools/ci/test_progression_orientation_flight_world.py'],
        ['node','--check','plugins/robot_windows/orientation_flight_probe/orientation_flight_probe.js'],
    ):
        check=subprocess.run(command,cwd=ROOT,check=False)
        if check.returncode:
            return check.returncode
    # All native classroom controllers were compiled in the preceding pinned
    # R2025a campaign. Reuse their exact bytes; no source or runtime rebuilding.
    # A separate container makes the A3 physics test independent of A2's probe,
    # with its own Webots world, browser events, native outcome and artifact.
    script=r'''
set -e
python3 /workspace/tools/test_prepare_webots_apt.py
python3 /workspace/tools/prepare_webots_apt.py
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wget ca-certificates >/dev/null
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null
chmod +x /workspace/tools/ci/webots_runtime_v2_browser.sh
mkdir -p /root/.config/Cyberbotics /workspace/ci-artifacts/progression-neutral-start
printf "%s\n" "[RobotWindow]" "browser=/workspace/tools/ci/webots_runtime_v2_browser.sh" \
  "newBrowserWindow=false" > /root/.config/Cyberbotics/Webots-R2025a.conf
python3 /workspace/tools/ci/run_classroom_orientation_flight.py
'''
    return subprocess.run([
        'docker','run','--rm','-e','LIBGL_ALWAYS_SOFTWARE=true',
        '-e','WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true',
        '-e','WEBEEBLOCKS_CI_ARTIFACT_DIR=/workspace/ci-artifacts/progression-neutral-start',
        '-v',str(ROOT)+':/workspace','-w','/workspace',
        IMAGE,'bash','-lc',script
    ],cwd=ROOT,check=False).returncode

if __name__=='__main__':
    raise SystemExit(main())
