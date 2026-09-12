#!/usr/bin/env python3
"""Run Firefox broker acceptance, then prepare the existing Chrome file harness."""

from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
subprocess.run(
    [sys.executable, str(ROOT / "tools/ci/run_runtime_v2_firefox_project_files.py")],
    check=True,
)
runpy.run_path(
    str(ROOT / "tools/ci/prepare_runtime_v2_project_files_chrome.py"),
    run_name="__main__",
)
