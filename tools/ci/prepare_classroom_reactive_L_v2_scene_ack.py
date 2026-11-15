#!/usr/bin/env python3
"""CI-only genuine A5 V2 native SCENE/SCENE_OK variant switching.

Starts from the exact empty classroom world and the original Crazyflie PROTO.
Every A/B/C scene and its evaluator are imported by the school-only C++ native
selector through the nonce-bound WWI interface, never preloaded in this world.
This is not a flown Blockly pupil .wbb, hardware or teacher authorization.
"""
from pathlib import Path
import hashlib
import prepare_classroom_altitude_scene_ack as classroom

ROOT=classroom.ROOT
WORLD=ROOT/"worlds/ci_reactive_L_v2_scene_ack.wbt"
PROJECT=ROOT/"worlds/.ci_reactive_L_v2_scene_ack.wbproj"
PROJECT_TEXT="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
MARKER="# WEBEEBLOCKS_A5_V2_SCENE_ACK_NATIVE_CI_ONLY"


def compose(start=None):
    source=classroom.SOURCE.read_text(encoding="utf-8") if start is None else start
    base=classroom.compose(source)
    if base.count(classroom.MARKER)!=1 or base.count(
        'window "altitude_scene_ack_probe"')!=1:
        raise ValueError("ambiguous base classroom scene source")
    world=base.replace(classroom.MARKER,MARKER).replace(
        'window "altitude_scene_ack_probe"',
        'window "reactive_l_v2_scene_ack_probe"')
    if (world.count(MARKER)!=1 or
        world.count('window "reactive_l_v2_scene_ack_probe"')!=1 or
        world.count('controller "crazyflie_classroom_v2"')!=1 or
        "WEBEEBLOCKS_REACTIVE_L_V2_A_SCENE" in world or
        "WEBEEBLOCKS_REACTIVE_L_V2_B_SCENE" in world or
        "WEBEEBLOCKS_REACTIVE_L_V2_C_SCENE" in world or
        "WEBEEBLOCKS_REACTIVE_L_V2_EVALUATOR" in world or
        'controller "crazyflie_runtime_v2"' in world):
        raise ValueError("A5 CI scene ACK must not preload a variant or observer")
    return world


def prepare():
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("refuse to overwrite an existing native Webots world")
    body=compose()
    WORLD.write_text(body,encoding="utf-8")
    PROJECT.write_text(PROJECT_TEXT,encoding="utf-8")
    print("WEBEEBLOCKS_A5_V2_SCENE_ACK_WORLD_SHA256 "+
          hashlib.sha256(body.encode("utf-8")).hexdigest(),flush=True)


def cleanup():
    if WORLD.exists():
        body=WORLD.read_text(encoding="utf-8")
        if body!=compose():
            raise RuntimeError("refuse cleanup of modified native A5 world")
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding="utf-8")!=PROJECT_TEXT:
            raise RuntimeError("refuse cleanup of altered Webots project")
        PROJECT.unlink()


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("prepare","clean"))
    action=parser.parse_args().action
    if action=="prepare":prepare()
    else:cleanup()
