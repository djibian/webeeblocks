"""Isolated embedded Windows native Grand Prix variable evaluator.

The existing evaluator source is executed unchanged. No authority/attestation
fallback to the historical U evaluator or to ambient Python is available.
"""
import json
import os
from pathlib import Path
import runpy
import sys


def main():
    sys.dont_write_bytecode = True
    directory = Path(__file__).resolve().parent
    root = directory.parents[1]
    expected = root / "runtime/python/webeeblocks-gp-python.exe"
    if sys.platform == "win32" and Path(sys.executable).resolve() != expected.resolve():
        raise RuntimeError("Packaged route evaluator interpreter mismatch")
    webots = Path(os.environ["WEBOTS_HOME"]).resolve(strict=True)
    if (webots / "resources/version.txt").read_text().strip() != "R2025a":
        raise RuntimeError("Webots R2025a strictly required")
    api = webots / "lib/controller/python"
    if not (api / "controller/__init__.py").is_file():
        raise RuntimeError("Webots native controller API missing")
    sys.path[:0] = [str(root), str(api)]
    from controller import Supervisor
    from tools.grand_prix.evaluator_publisher_v2 import (
        SCENE_POLICY_CLASSROOM_STATIC, serve_native,
    )
    if SCENE_POLICY_CLASSROOM_STATIC != "classroom-static-v1":
        raise RuntimeError("Classroom static policy no longer exact")
    if sys.argv[1:] == ["--verify-imports"]:
        print(json.dumps({
            "python": sys.version.split()[0], "isolated": sys.flags.isolated,
            "no_site": sys.flags.no_site,
            "policy": SCENE_POLICY_CLASSROOM_STATIC,
            "exe": str(expected), "controller_api": str(api),
        }), flush=True)
        return
    # The real Webots controller passes the canonical CoursePlan.identifier
    # through controllerArgs; do not rewrite sys.argv or bypass the native gate.
    runpy.run_path(str(directory / "evaluator_impl.py"), run_name="__main__")


if __name__ == "__main__":
    main()
