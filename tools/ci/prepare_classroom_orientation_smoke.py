#!/usr/bin/env python3
"""Build a *test-only* Webots R2025a world for both native Activity 3 processes.

No student interface, program execution, scene import, flight PASS or physical
controller mutation is involved. Inputs stay versioned and read-only.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
START = ROOT / "worlds/crazyflie_classroom_start.wbt"
SCENE = ROOT / "worlds/scenes/orientation-v1.wbo"
OUTPUT = ROOT / "worlds/ci_classroom_orientation_smoke.wbt"
START_EVALUATOR = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN"
END_EVALUATOR = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_END"
MARKER = "# WEBEEBLOCKS_ORIENTATION_NATIVE_SMOKE_V1"


def compose(start: str, scene: str) -> str:
    if not start.startswith("#VRML_SIM R2025a utf8\n"):
        raise ValueError("incorrect Webots version")
    if start.count("DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {") != 1:
        raise ValueError("ambiguous classroom world")
    if (start.count('controller "crazyflie_runtime_v2"') != 2 or
            start.count('name "Crazyflie WebeeBlocks"') != 1 or
            start.count('window "blockly_v2"') != 1):
        raise ValueError("unexpected original classroom identities")
    prefix, marker, evaluator = start.partition(START_EVALUATOR)
    if (not marker or start.count(START_EVALUATOR) != 1 or
            evaluator.count(END_EVALUATOR) != 1 or
            not evaluator.strip().endswith(END_EVALUATOR) or
            evaluator.count('controller "crazyflie_runtime_v2"') != 1):
        raise ValueError("invalid legacy evaluator boundary")
    if prefix.count('controller "crazyflie_runtime_v2"') != 1:
        raise ValueError("ambiguous original flight controller")

    # Only admit this exact scene identity, one non-colliding C observer, and
    # the original 24 direct visual markers (6 inner arrow glyphs not counted).
    if (not scene.startswith("DEF WEBEEBLOCKS_ORIENTATION_SCENE Group {") or
            scene.count("DEF WEBEEBLOCKS_ORIENTATION_SCENE Group {") != 1 or
            scene.count('controller "progression_orientation_3d"') != 1 or
            scene.count('name "Progression orientation 3D evaluator"') != 1 or
            scene.count(" Robot {") != 1 or
            re.search(r"\bSolid\s*\{|\bboundingObject\b", scene) or
            len(re.findall(r"^    Pose \{ translation ", scene, re.MULTILINE)) != 24 or
            scene.count("geometry Box { size 0.32 0.32 0.004 }") != 1):
        raise ValueError("invalid isolated orientation scene")
    prefix = prefix.replace('controller "crazyflie_runtime_v2"',
                            'controller "crazyflie_classroom_v2"', 1)
    prefix = prefix.replace('window "blockly_v2"', 'window ""', 1)
    prepared = prefix.rstrip() + "\n\n" + MARKER + "\n" + scene.rstrip() + "\n"
    if (prepared.count('controller "crazyflie_classroom_v2"') != 1 or
            prepared.count('controller "progression_orientation_3d"') != 1 or
            'controller "crazyflie_runtime_v2"' in prepared or
            START_EVALUATOR in prepared or
            "WEBEEBLOCKS_LEGACY_EVALUATORS" in prepared):
        raise ValueError("unexpected native processes in smoke world")
    return prepared


def main() -> int:
    arg = argparse.ArgumentParser()
    arg.add_argument("command", choices=("prepare", "clean"))
    args = arg.parse_args()
    if args.command == "clean":
        if OUTPUT.exists():
            if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf8").count(MARKER) != 1:
                raise ValueError("refusing to delete unrecognized world")
            OUTPUT.unlink()
        return 0
    if OUTPUT.exists():
        raise FileExistsError("refusing to overwrite an existing world")
    result = compose(START.read_text(encoding="utf8"),
                     SCENE.read_text(encoding="utf8"))
    OUTPUT.write_text(result, encoding="utf8")
    print("WEBEEBLOCKS_ORIENTATION_SMOKE_WORLD_SHA256 "
          + hashlib.sha256(result.encode("utf8")).hexdigest(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
