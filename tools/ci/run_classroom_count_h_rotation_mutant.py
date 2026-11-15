#!/usr/bin/env python3
"""Reject an A6 physical H rotated 90 degrees in genuine Webots R2025a.

Mutates precisely one bounding Solid's world rotation while preserving every
name, local Box size and translational centre. Starts the independent native
observer before any pupil action; a product or pupil pass is never claimed.
"""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

import prepare_classroom_count_h_motor_flight as native

ROOT=native.ROOT
EVIDENCE=ROOT/"ci-artifacts/progression-count-h-rotation-mutant"
WORLD=ROOT/"worlds/ci_classroom_count_h_rotated_negative.wbt"
PROJECT=ROOT/"worlds/.ci_classroom_count_h_rotated_negative.wbproj"
MARKER="# WEBEEBLOCKS_A6_ROTATED_COLLIDER_NEGATIVE_CI_ONLY"
IDENTITY="DEF ACTIVITY6_2_H_1_BAR Solid {\n    translation -0.850 0 0.74\n"
ROTATION="    rotation 0 0 1 1.5707963267948966\n"
OBSERVER=('DEF WEBEEBLOCKS_A6_ROTATION_OBSERVER Robot {\n'
          '  name "A6 independent motor-flight observer"\n'
          '  controller "progression_count_h_flight_observer"\n'
          '  supervisor TRUE\n'
          '  synchronization TRUE\n'
          '}\n')
FATAL="WEBEEBLOCKS_A6_MOTOR_FATAL H collider geometry not native-attested"
READY="WEBEEBLOCKS_A6_MOTOR_READY"
RESULT="WEBEEBLOCKS_A6_MOTOR_RESULT"

def mutant():
    world=native.compose(variant=2)
    if world.count(IDENTITY)!=1 or ROTATION in world:
        raise AssertionError("canonical native H identity or orientation drift")
    rotated=world.replace(IDENTITY,IDENTITY+ROTATION,1)
    if (rotated.count(ROTATION)!=1 or
        rotated.count('DEF WEBEEBLOCKS_COUNT_2_SCENE Group')!=1 or
        rotated.count('name "Crazyflie WebeeBlocks"')!=1 or
        rotated.count('controller "progression_count_h_school_pilot"')!=1 or
        rotated.count("boundingObject Box")!=8):
        raise AssertionError("mutant touched an unrelated mission component")
    return rotated.rstrip()+"\n"+MARKER+"\n"+OBSERVER

def run():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("refuse overwrite of native rotated-H experiment")
    source=mutant()
    WORLD.write_text(source,encoding="utf-8")
    PROJECT.write_text(native.PROJECT_BYTES,encoding="utf-8")
    print("WEBEEBLOCKS_A6_ROTATION_MUTANT_SHA256 "+
          hashlib.sha256(source.encode("utf-8")).hexdigest(),flush=True)
    log=EVIDENCE/"webots.log"
    proc=None
    output=None
    try:
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        output=log.open("w",encoding="utf-8")
        proc=subprocess.Popen(
            ["timeout","-k","5s","35s","xvfb-run","-a","webots",
             "--stdout","--stderr","--batch","--mode=realtime",str(WORLD)],
            cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,
            start_new_session=True)
        deadline=time.monotonic()+34
        while time.monotonic()<deadline:
            evidence=log.read_text(encoding="utf-8",errors="replace")
            if FATAL in evidence or READY in evidence or RESULT in evidence:
                break
            if proc.poll() is not None:
                break
            time.sleep(.2)
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=5)
        if output is not None:
            output.close()
        if WORLD.is_symlink() or PROJECT.is_symlink():
            raise RuntimeError("refuse cleanup of redirected mutant test path")
        if WORLD.read_text(encoding="utf-8")!=source:
            changed=WORLD.read_bytes()
            (EVIDENCE/"altered-physical-world.json").write_text(
                json.dumps({"schema":"a6-rotation-mutant-world-integrity-v1",
                    "original_sha256":hashlib.sha256(source.encode()).hexdigest(),
                    "changed_sha256":hashlib.sha256(changed).hexdigest(),
                    "original_bytes":len(source.encode()),"changed_bytes":len(changed)},
                    sort_keys=True,indent=2)+"\n",encoding="utf-8")
            raise RuntimeError("refuse cleanup: rotated physical world modified")
        gui=PROJECT.read_bytes()
        original=native.PROJECT_BYTES.encode("utf-8")
        if gui!=original:
            (EVIDENCE/"postrun-webots-project.wbproj").write_bytes(gui)
            allowed=native.validate_project_preferences(gui)
            (EVIDENCE/"postrun-webots-project.json").write_text(
                json.dumps({"schema":"a6-rotation-mutant-GUI-preferences-v1",
                    "sha256_before":hashlib.sha256(original).hexdigest(),
                    "sha256_after":hashlib.sha256(gui).hexdigest(),
                    "original_bytes":len(original),"changed_bytes":len(gui),
                    "valid_gui_metadata":allowed,
                    "is_physics_or_mission_authority":False},
                    sort_keys=True,indent=2)+"\n",encoding="utf-8")
            if not allowed:
                raise RuntimeError("refuse cleanup: unrecognized rotated-test GUI preferences")
        WORLD.unlink()
        PROJECT.unlink()
    evidence=log.read_text(encoding="utf-8",errors="replace")
    if evidence.count(FATAL)!=1 or READY in evidence or RESULT in evidence:
        raise AssertionError(
            "90-degree rotated native H not rejected before READY: "+
            evidence[-2400:])
    print("WEBEEBLOCKS_A6_ROTATED_COLLIDER_REJECTED "
          "native=true before_ready=true pupil_flight=NOT_TESTED",flush=True)
    return 0

if __name__=="__main__":
    sys.exit(run())
