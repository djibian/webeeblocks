#!/usr/bin/env python3
"""CI-only Webots R2025a A6 motor flight: authentic product PID, test scene gate.

The full-flight path uses real runtime-v2 TAKEOFF/MOVE/LAND and original
Crazyflie PROTO; only scene admission is test-specific. Never publish as an
A6 pupil profile or physical qualification.
"""
from pathlib import Path
import hashlib
import prepare_classroom_altitude_scene_ack as classroom

ROOT=classroom.ROOT
SOURCE=classroom.SOURCE
WORLD=ROOT/"worlds/ci_classroom_count_h_motor_flight.wbt"
PROJECT=ROOT/"worlds/.ci_classroom_count_h_motor_flight.wbproj"
ARTIFACT=ROOT/"ci-artifacts/progression-count-h-motor"
MARKER="# WEBEEBLOCKS_COUNT_H_MOTOR_CI_ONLY"
PROJECT_BYTES="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
SCENE=ROOT/"worlds/scenes/count-h-1-v1.wbo"
def compose(start=None,scene=None):
    source=SOURCE.read_text(encoding="utf-8") if start is None else start
    world=classroom.compose(source)
    body=SCENE.read_text(encoding="utf-8") if scene is None else scene
    original='Crazyflie {\n  name "Crazyflie WebeeBlocks"'
    if (world.count(original)!=1 or
        world.count('controller "crazyflie_classroom_v2"')!=1 or
        world.count('window "altitude_scene_ack_probe"')!=1 or
        world.count(classroom.MARKER)!=1 or
        body.count("DEF WEBEEBLOCKS_COUNT_1_SCENE Group {")!=1 or
        body.count(" Solid {")!=5 or
        body.count("boundingObject Box")!=5 or
        'controller "' in body or 'Robot {' in body or
        any(f"DEF WEBEEBLOCKS_COUNT_{n}_SCENE Group" in body for n in (2,3))):
        raise ValueError("ambiguous n=1 native physical scene or authentic craft")
    world=world.replace(original,
        'Crazyflie {\n  translation -1.40 0 0.055\n  name "Crazyflie WebeeBlocks"')
    world=world.replace('controller "crazyflie_classroom_v2"',
                        'controller "progression_count_h_school_pilot"')
    world=world.replace('window "altitude_scene_ack_probe"',
                        'window "count_h_flight_probe"')
    world=world.replace(classroom.MARKER,MARKER)
    # A second Robot at initial Webots startup can steal Robot Window focus.
    # Import the independent observer after the sole Crazyflie window starts.
    output=world.rstrip()+"\n"+body.rstrip()+"\n"
    if (output.count('controller "progression_count_h_school_pilot"')!=1 or
        output.count('controller "progression_count_h_flight_observer"')!=0 or
        output.count('controller "progression_count_h_school_pilot"')!=1 or
        output.count('window "count_h_flight_probe"')!=1 or
        output.count(MARKER)!=1 or
        'controller "crazyflie_runtime_v2"' in output or
        'controller "crazyflie_classroom_v2"' in output or
        'DEF WEBEEBLOCKS_ALTITUDE_SCENE' in output or
        'DEF WEBEEBLOCKS_ORIENTATION_SCENE' in output or
        'DEF WEBEEBLOCKS_SEQUENCE_SCENE' in output):
        raise ValueError("unexpected product runtime or contaminating evaluator")
    return output

def prepare():
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("refusing to overwrite A6 physical test world")
    data=compose()
    WORLD.write_text(data,encoding="utf-8")
    PROJECT.write_text(PROJECT_BYTES,encoding="utf-8")
    print("WEBEEBLOCKS_A6_MOTOR_WORLD_SHA256 "+
          hashlib.sha256(data.encode()).hexdigest(),flush=True)

def cleanup():
    if WORLD.exists():
        data=WORLD.read_text(encoding="utf-8")
        if data.count(MARKER)!=1 or data.count(
            'controller "progression_count_h_school_pilot"')!=1 or (
                'controller "progression_count_h_flight_observer"' in data):
            raise ValueError("refuse cleanup altered native A6 world")
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding="utf-8")!=PROJECT_BYTES:
            raise ValueError("refuse cleanup altered native A6 Webots project")
        PROJECT.unlink()

if __name__=="__main__":
    import sys
    if sys.argv[1:]==["prepare"]:prepare()
    elif sys.argv[1:]==["clean"]:cleanup()
    else:raise SystemExit("expected prepare/clean")
