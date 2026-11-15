#!/usr/bin/env python3
"""CI-only Webots R2025a A6 motor flight: authentic product PID, test scene gate.

The full-flight path uses real runtime-v2 TAKEOFF/MOVE/LAND and original
Crazyflie PROTO; only scene admission is test-specific. Never publish as an
A6 pupil profile or physical qualification.
"""
from pathlib import Path
import hashlib
import json
import prepare_classroom_altitude_scene_ack as classroom

ROOT=classroom.ROOT
SOURCE=classroom.SOURCE
WORLD=ROOT/"worlds/ci_classroom_count_h_motor_flight.wbt"
PROJECT=ROOT/"worlds/.ci_classroom_count_h_motor_flight.wbproj"
ARTIFACT=ROOT/"ci-artifacts/progression-count-h-motor"
MARKER="# WEBEEBLOCKS_COUNT_H_MOTOR_CI_ONLY"
PROJECT_BYTES="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
SCENES={n:ROOT/f"worlds/scenes/count-h-{n}-v1.wbo" for n in (1,2,3)}
SCENE=SCENES[1]
def compose(start=None,scene=None,variant=1):
    if type(variant) is not int or variant not in SCENES:
        raise ValueError('invalid bounded A6 count variant')
    source=SOURCE.read_text(encoding="utf-8") if start is None else start
    world=classroom.compose(source)
    body=SCENES[variant].read_text(encoding="utf-8") if scene is None else scene
    original='Crazyflie {\n  name "Crazyflie WebeeBlocks"'
    if (world.count(original)!=1 or
        world.count('controller "crazyflie_classroom_v2"')!=1 or
        world.count('window "altitude_scene_ack_probe"')!=1 or
        world.count(classroom.MARKER)!=1 or
        body.count(f"DEF WEBEEBLOCKS_COUNT_{variant}_SCENE Group {{")!=1 or
        body.count(" Solid {")!=3*variant+2 or
        body.count("boundingObject Box")!=3*variant+2 or
        'controller "' in body or 'Robot {' in body or
        any(f"DEF WEBEEBLOCKS_COUNT_{n}_SCENE Group" in body
            for n in SCENES if n!=variant)):
        raise ValueError("ambiguous numbered native physical scene or authentic craft")
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

def prepare(variant=1):
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("refusing to overwrite A6 physical test world")
    data=compose(variant=variant)
    WORLD.write_text(data,encoding="utf-8")
    PROJECT.write_text(PROJECT_BYTES,encoding="utf-8")
    print(f"WEBEEBLOCKS_A6_MOTOR_WORLD_VARIANT {variant}",flush=True)
    print("WEBEEBLOCKS_A6_MOTOR_WORLD_SHA256 "+
          hashlib.sha256(data.encode()).hexdigest(),flush=True)

def validate_project_preferences(raw):
    """Only generated Webots R2025a GUI preferences, never mission authority."""
    if len(raw)>65536 or not raw:
        return False
    try:
        data=raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if any(ord(ch)<32 and ch not in "\n\r\t" for ch in data):
        return False
    lines=data.splitlines()
    return (len(lines)>=2 and
            lines[0]=="Webots Project File version R2025a" and
            sum(x.strip()=="robotWindow: Crazyflie WebeeBlocks"
                for x in lines)==1)


def cleanup(artifacts=None):
    # A .wbproj stores UI perspective/preferences; Webots may rewrite it on
    # close. It is not a world, controller or mission-verdict authority.
    # Preserve post-run bytes for audit and reject unknown provenance/content.
    if WORLD.is_symlink() or PROJECT.is_symlink():
        raise ValueError("refuse cleanup of redirected A6 native test path")
    if WORLD.exists():
        data=WORLD.read_text(encoding="utf-8")
        if data.count(MARKER)!=1 or data.count(
            'controller "progression_count_h_school_pilot"')!=1 or (
                'controller "progression_count_h_flight_observer"' in data):
            raise ValueError("refuse cleanup altered native A6 world")
    if PROJECT.exists():
        raw=PROJECT.read_bytes()
        original=PROJECT_BYTES.encode("utf-8")
        altered=raw!=original
        if altered:
            if artifacts is not None:
                evidence=Path(artifacts)
                evidence.mkdir(parents=True,exist_ok=True)
                (evidence/"postrun-webots-project.wbproj").write_bytes(raw)
                (evidence/"postrun-webots-project.json").write_text(
                    json.dumps({
                        "schema":"webeeblocks-a6-webots-gui-preferences-v1",
                        "changed":True,
                        "sha256_after":hashlib.sha256(raw).hexdigest(),
                        "sha256_before":hashlib.sha256(original).hexdigest(),
                        "bytes_after":len(raw),
                        "is_physics_or_mission_authority":False,
                        "valid_gui_metadata":validate_project_preferences(raw)
                    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
            if not validate_project_preferences(raw):
                raise ValueError("refuse cleanup unrecognized native A6 Webots GUI preferences")
    # Unlink ONLY files created by prepare() after validating paths and content.
    if WORLD.exists():
        WORLD.unlink()
    if PROJECT.exists():
        PROJECT.unlink()

if __name__=="__main__":
    import sys
    if len(sys.argv)==3 and sys.argv[1]=="prepare":
        prepare(int(sys.argv[2]))
    elif sys.argv[1:]==["prepare"]:prepare()
    elif sys.argv[1:]==["clean"]:cleanup()
    else:raise SystemExit("expected prepare/clean")
