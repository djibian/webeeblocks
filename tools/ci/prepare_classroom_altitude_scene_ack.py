#!/usr/bin/env python3
"""CI-only native SCENE handshake world from the exact classroom source.

The launcher keeps the real Crazyflie PROTO, its sensors and physics, but
selects the isolated school flight process and a read-only WWI test page.
Unlike the startup-only test, no altitude scene is preloaded: Webots must
receive SCENE altitude-v1 and SCENE orientation-v1, and import each scene
before either dedicated evaluator can start.
"""
from pathlib import Path
import argparse
import hashlib

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "worlds/crazyflie_classroom_start.wbt"
WORLD = ROOT / "worlds/ci_classroom_altitude_scene_ack.wbt"
PROJECT = ROOT / "worlds/.ci_classroom_altitude_scene_ack.wbproj"
BOUNDARY = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN"
TRAILER = "# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_END"
MARKER = "# WEBEEBLOCKS_CLASSROOM_ALTITUDE_SCENE_ACK_CI_ONLY"


def compose(start: str) -> str:
    if (not start.startswith("#VRML_SIM R2025a utf8\n") or
        start.count("DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {") != 1 or
        start.count('name "Crazyflie WebeeBlocks"') != 1 or
        start.count('controller "crazyflie_runtime_v2"') != 2 or
        start.count('window "blockly_v2"') != 1 or
        "DEF WEBEEBLOCKS_ALTITUDE_SCENE" in start or
        "DEF WEBEEBLOCKS_ORIENTATION_SCENE" in start or
        "DEF WEBEEBLOCKS_LEGACY_SCENE" in start):
        raise ValueError("ambiguous classroom source or preloaded scene")
    prefix, divider, evaluator = start.partition(BOUNDARY)
    if not divider or not evaluator.strip().endswith(TRAILER):
        raise ValueError("original sequence evaluator boundary missing")
    if evaluator.count('controller "crazyflie_runtime_v2"') != 1:
        raise ValueError("cannot uniquely remove legacy evaluator process")
    prefix = prefix.replace('controller "crazyflie_runtime_v2"',
                            'controller "crazyflie_classroom_v2"', 1)
    prefix = prefix.replace('window "blockly_v2"',
                            'window "altitude_scene_ack_probe"', 1)
    created = prefix.rstrip() + "\n\n" + MARKER + "\n"
    if (created.count('controller "crazyflie_classroom_v2"') != 1 or
        'controller "crazyflie_runtime_v2"' in created or
        "Progression sequence evaluator" in created or
        "DEF WEBEEBLOCKS_ALTITUDE_SCENE" in created or
        "DEF WEBEEBLOCKS_ORIENTATION_SCENE" in created or
        'window "altitude_scene_ack_probe"' not in created):
        raise ValueError("native scene probe could preload evaluator or change craft")
    return created


def cleanup() -> None:
    if WORLD.exists():
        content = WORLD.read_text(encoding="utf-8")
        if content.count(MARKER) != 1:
            raise ValueError("refusing cleanup of unknown world")
        WORLD.unlink()
    if PROJECT.exists():
        content = PROJECT.read_text(encoding="utf-8")
        if content != "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n":
            raise ValueError("refusing cleanup of unknown project file")
        PROJECT.unlink()


def prepare() -> None:
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("native SCENE witness refuses to overwrite other files")
    world = compose(SOURCE.read_text(encoding="utf-8"))
    WORLD.write_text(world, encoding="utf-8")
    PROJECT.write_text("Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n",
                       encoding="utf-8")
    print("WEBEEBLOCKS_CLASSROOM_ALTITUDE_ACK_WORLD_SHA256 " +
          hashlib.sha256(world.encode("utf-8")).hexdigest(), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "clean"))
    if parser.parse_args().action == "clean":
        cleanup()
    else:
        prepare()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
