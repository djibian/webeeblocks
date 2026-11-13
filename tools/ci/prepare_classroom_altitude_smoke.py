#!/usr/bin/env python3
"""Generate/clean a *test-only* R2025a world for the native classroom components.

The source classroom start world and the Activity 2 scene are read-only. The
temporary world runs the classroom flight executable and the C altitude oracle
together, without loading a pupil program, importing a scene via WWI, or
modifying the locked physical controller.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START = ROOT / "worlds/crazyflie_classroom_start.wbt"
SCENE = ROOT / "worlds/scenes/altitude-v1.wbo"
OUTPUT = ROOT / "worlds/ci_classroom_altitude_smoke.wbt"
END = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_END"
START_EVALUATOR = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN"


def compose(start: str, scene: str) -> str:
    if not start.startswith("#VRML_SIM R2025a utf8\n"):
        raise ValueError("untrusted source WorldInfo/Webots version")
    if start.count("DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {") != 1:
        raise ValueError("not the typed classroom world")
    if start.count('controller "crazyflie_runtime_v2"') != 2 or (
        start.count('name "Crazyflie WebeeBlocks"') != 1 or
        start.count('window "blockly_v2"') != 1
    ):
        raise ValueError("ambiguous classroom flight/runtime identities")
    prefix, separator, trailing = start.partition(START_EVALUATOR)
    if not separator or not trailing.strip().endswith(END):
        raise ValueError("missing exact legacy sequence evaluator boundary")
    if trailing.count('controller "crazyflie_runtime_v2"') != 1:
        raise ValueError("unexpected legacy evaluator")
    if (
        not scene.startswith("DEF WEBEEBLOCKS_ALTITUDE_SCENE Group {") or
        scene.count('controller "progression_altitude_v1"') != 1 or
        scene.count(" Robot {") != 1 or
        scene.count(" Solid {") != 3 or
        scene.count("boundingObject Box") != 3 or
        scene.count(" Pose {") != 18
    ):
        raise ValueError("invalid isolated altitude native scene identity")

    # Disable only the browser surface for this *startup* witness. Preserve
    # every Crazyflie sensor, geometry, visual deck, and native flight source.
    prefix = prefix.replace('controller "crazyflie_runtime_v2"',
                            'controller "crazyflie_classroom_v2"', 1)
    prefix = prefix.replace('window "blockly_v2"', 'window ""', 1)
    prepared = (
        prefix.rstrip() + "\n\n"
        + "# WEBEEBLOCKS_ALTITUDE_NATIVE_SMOKE_V1\n"
        + scene.rstrip() + "\n"
    )
    if (prepared.count('controller "crazyflie_classroom_v2"') != 1 or
        'controller "crazyflie_runtime_v2"' in prepared or
        prepared.count('controller "progression_altitude_v1"') != 1):
        raise ValueError("test world includes an unexpected controller")
    return prepared


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "clean"))
    args = parser.parse_args()
    if args.command == "clean":
        if OUTPUT.is_file():
            raw = OUTPUT.read_text(encoding="utf-8")
            if raw.count("# WEBEEBLOCKS_ALTITUDE_NATIVE_SMOKE_V1") != 1:
                raise ValueError("refusing to delete an unrecognized test world")
            OUTPUT.unlink()
        return 0
    if OUTPUT.exists():
        raise FileExistsError("refusing to overwrite an existing native smoke world")
    prepared = compose(START.read_text(encoding="utf-8"),
                       SCENE.read_text(encoding="utf-8"))
    OUTPUT.write_text(prepared, encoding="utf-8")
    print("WEBEEBLOCKS_ALTITUDE_SMOKE_WORLD_SHA256 "
          + hashlib.sha256(prepared.encode("utf-8")).hexdigest(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
