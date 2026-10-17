"""Re-run the full unchanged Activity 1/2 oracle campaign from the empty launch.

The original legacy-world campaign remains in its own artifact directory.
"""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
raise SystemExit(subprocess.run(
    [sys.executable, str(root / 'tools/ci/run_progression_sequence_mission.py')],
    cwd=root, env={**os.environ, 'WEBEEBLOCKS_CI_NEUTRAL_START': '1'},
    check=False).returncode)
