#!/usr/bin/env python3
"""CI-only classroom A7 flight world, true school PID and Crazyflie PROTO.

The A7 mission's BLUE origin is x=-1.40; this test-only classroom derivative
starts at that physical position BEFORE the native runtime snapshots RESET
origin. It never teleports the craft after startup. Do not claim normal
classroom starter world meets this requirement until product integration.
"""
from pathlib import Path
import hashlib
import prepare_classroom_altitude_scene_ack as classroom

ROOT = classroom.ROOT
WORLD = ROOT / "worlds/ci_classroom_mini_gp_pupil.wbt"
PROJECT = ROOT / "worlds/.ci_classroom_mini_gp_pupil.wbproj"
MARKER = "# WEBEEBLOCKS_A7_REAL_PUPIL_BLOCKLY_CI_ONLY"
PROJECT_TEXT = "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
START = '\nCrazyflie {\n'
SCHOOL = 'controller "crazyflie_classroom_v2"'
WINDOW = 'window "altitude_scene_ack_probe"'


def compose(source):
    result = classroom.compose(source)
    if (result.count(START) != 1 or result.count(SCHOOL) != 1 or
            result.count(WINDOW) != 1 or MARKER in result or
            "WEBEEBLOCKS_MINI_GP_" in result or
            'controller "crazyflie_runtime_v2"' in result or
            "translation -1.4 0 0.015" in result):
        raise ValueError("unexpected school source/physics or scene preloading")
    result = result.replace(START, START + "  translation -1.4 0 0.015\n", 1)
    result = result.replace(WINDOW, 'window "mini_gp_pupil_probe"', 1)
    result = result.rstrip() + "\n" + MARKER + "\n"
    if (result.count(MARKER) != 1 or result.count(SCHOOL) != 1 or
            result.count('window "mini_gp_pupil_probe"') != 1 or
            result.count("  translation -1.4 0 0.015\n") != 1 or
            "DEF WEBEEBLOCKS_MINI_GP_L_SCENE" in result or
            "DEF WEBEEBLOCKS_MINI_GP_R_SCENE" in result):
        raise ValueError("unable to attest safe A7 pupil starting world")
    return result


def prepare():
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("refusing overwrite of another A7 motor trial")
    body = compose(classroom.SOURCE.read_text(encoding="utf-8"))
    WORLD.write_text(body, encoding="utf-8")
    PROJECT.write_text(PROJECT_TEXT, encoding="utf-8")
    print("A7_PUPIL_WORLD_SHA256 " +
          hashlib.sha256(body.encode("utf-8")).hexdigest(), flush=True)


def cleanup():
    if WORLD.exists():
        original = classroom.SOURCE.read_text(encoding="utf-8")
        expected = compose(original)
        if (WORLD.read_text(encoding="utf-8") != expected or
                expected.count(MARKER) != 1):
            raise ValueError("refusing cleanup of mutated A7 world")
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding="utf-8") != PROJECT_TEXT:
            raise ValueError("refusing cleanup of mutated Webots project")
        PROJECT.unlink()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "cleanup"))
    cmd = parser.parse_args().command
    prepare() if cmd == "prepare" else cleanup()
