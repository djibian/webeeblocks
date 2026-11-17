#!/usr/bin/env python3
"""Prepare private motor/PID A5 factor A/B worlds without changing product files.

The original Crazyflie and Webots physics are retained. The private controller
is an isolated linked copy of the locked runtime, with a strict scene gate.
This is a physical feasibility probe, not Blockly or native mission acceptance.
"""
from pathlib import Path
import hashlib
import prepare_classroom_altitude_scene_ack as classroom

ROOT=classroom.ROOT
MARKER="# WEBEEBLOCKS_A5_FACTOR_MOTOR_CI_ONLY"
PROJECT_TEXT="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
SOURCE_CONTROLLER='controller "crazyflie_classroom_v2"'
PILOT_CONTROLLER='controller "progression_reactive_L_factor_motor_pilot"'
SOURCE_WINDOW='window "altitude_scene_ack_probe"'
PILOT_WINDOW='window "a5_alias_motor_probe"'

def scene_file(variant):
    return ROOT/("worlds/scenes/reactive-L-factor-hnear-g"+("left" if variant=="A" else "right")+"-proto.wbo")

def paths(variant):
    return (ROOT/f"worlds/ci_a5_factor_motor_{variant.lower()}.wbt",
            ROOT/f"worlds/.ci_a5_factor_motor_{variant.lower()}.wbproj")

def compose(variant,scene=None):
    if not isinstance(variant,str) or len(variant)!=1 or variant not in "AB":
        raise ValueError("A5 motor feasibility only permits A/B")
    start=classroom.SOURCE.read_text(encoding="utf-8")
    world=classroom.compose(start)
    body=scene_file(variant).read_text(encoding="utf-8") if scene is None else scene
    expected=f"DEF WEBEEBLOCKS_A5_FACTOR_G{'L' if variant=='A' else 'R'}_SCENE Group"
    if (world.count(SOURCE_CONTROLLER)!=1 or world.count(SOURCE_WINDOW)!=1
        or world.count(classroom.MARKER)!=1 or
        world.count('Crazyflie {\n  name "Crazyflie WebeeBlocks"')!=1
        or body.count(expected)!=1 or
        body.count(" Solid {")!=7 or body.count("boundingObject Box")!=7
        or "Robot {" in body or 'controller "' in body or
        any(f"DEF WEBEEBLOCKS_A5_FACTOR_G{v}_SCENE" in body
            for v in "LR" if v!=('L' if variant=='A' else 'R'))):
        raise ValueError("untrusted original classroom world or A5 factor obstacle")
    world=world.replace(SOURCE_CONTROLLER,PILOT_CONTROLLER,1)
    world=world.replace(SOURCE_WINDOW,PILOT_WINDOW,1)
    world=world.replace(classroom.MARKER,MARKER,1)
    world=world.replace("Floor { size 4 4 }","Floor { size 12 6 }",1)
    text=world.rstrip()+"\n"+body.rstrip()+"\n"
    if (text.count(MARKER)!=1 or text.count(PILOT_CONTROLLER)!=1 or
        text.count(PILOT_WINDOW)!=1 or SOURCE_CONTROLLER in text or
        SOURCE_WINDOW in text or
        'controller "crazyflie_runtime_v2"' in text):
        raise ValueError("native pilot must be unique and test-only")
    return text

def native_feeder_world(variant,mode):
    # Only a generated private WBT carries this marker. Product worlds retain
    # their original title and never opt into the command feeder.
    if mode not in ("positive","blind") or (mode=="blind" and variant!="B"):
        raise ValueError("invalid native G test mode")
    text=compose(variant)
    original='  title "WebeeBlocks — accueil"'
    if text.count(original)!=1:
        raise ValueError("cannot uniquely attest source WorldInfo title")
    marker=f'  title "WEBEEBLOCKS_A5_FACTOR_NATIVE_{mode}"'
    return text.replace(original,marker,1)

def prepare(variant,feeder_mode=None):
    world,project=paths(variant)
    if world.exists() or project.exists() or world.is_symlink() or project.is_symlink():
        raise FileExistsError("refusing to overwrite preexisting A5 native flight")
    data=(compose(variant) if feeder_mode is None else
          native_feeder_world(variant,feeder_mode))
    world.write_text(data,encoding="utf-8")
    project.write_text(PROJECT_TEXT,encoding="utf-8")
    print("WEBEEBLOCKS_A5_FACTOR_MOTOR_WORLD_SHA256 "+
          hashlib.sha256(data.encode()).hexdigest(),flush=True)

def cleanup(variant,original=None):
    world,project=paths(variant)
    if world.is_symlink() or project.is_symlink():
        raise RuntimeError("A5 native world became redirected")
    if world.exists():
        data=compose(variant) if original is None else original
        if world.read_text(encoding="utf-8")!=data:
            raise RuntimeError("refuse cleanup of modified A5 native world")
        world.unlink()
    if project.exists():
        source=project.read_text(encoding="utf-8")
        # Webots may write harmless GUI perspective settings; never treat
        # these as mission or physical authority. Archive changed bytes first.
        if source!=PROJECT_TEXT:
            if len(source)>65536 or not source.startswith(
                "Webots Project File version R2025a\n") or (
                "robotWindow: Crazyflie WebeeBlocks" not in source):
                raise RuntimeError("unexpected A5 Webots project transformation")
        project.unlink()
