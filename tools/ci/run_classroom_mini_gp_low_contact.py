#!/usr/bin/env python3
"""A7 Draft native contact: low obstacle contact must never look like floor.

Four genuine Webots R2025a worlds use the original Crazyflie body at
z=0.015m, touching either CORNER_FRONT or CLOSED_PANEL in the released
L/R scenes. The pupil motors and CI geometry teleporter are disabled;
the genuine independent C mission observer is compiled and running.

This falsifies low-z obstacle classification ONLY, not a pupil motor flight.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import time

import run_classroom_mini_gp_native_observer as observer

ROOT=observer.ROOT
ARTIFACT=ROOT/"ci-artifacts/progression-mini-gp-low-contact"
MARKER="# WEBEEBLOCKS_A7_LOW_PHYSICAL_CONTACT_CI_ONLY"
CRAFT="Crazyflie {\n"
REPLACE='controller "progression_mini_gp_geometry_probe"'
DISABLED='controller "<none>"'
FIRST="WB_MINI_NATIVE_FIRST"
CONTACT="WB_MINI_NATIVE_COLLIDER_CONTACT"


def compose(letter,part):
    if type(letter) is not str or letter not in ("L","R"):
        raise ValueError("invalid A7 letter")
    if type(part) is not str or part not in ("CORNER_FRONT","CLOSED_PANEL"):
        raise ValueError("invalid obstacle identity")
    world=observer.compose(letter)
    if (world.count(CRAFT)!=1 or world.count(REPLACE)!=1 or
            world.count(observer.MARKER)!=1 or MARKER in world or
            world.count('controller "progression_mini_grand_prix_v1"')!=1 or
            world.count('customData "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1"')!=1):
        raise ValueError("untrusted baseline native A7 test scene")
    turn=.20 if letter=="L" else .50
    side=1 if letter=="L" else -1
    x=turn+.22 if part=="CORNER_FRONT" else turn
    y=0 if part=="CORNER_FRONT" else side*1.42
    # This is a physical collision world, NOT a valid blue start or
    # a synthetic contact point. Webots determines all actual contacts.
    placement=f"  translation {x:.3f} {y:.3f} 0.015\n"
    altered=(world.replace(CRAFT,CRAFT+placement,1)
              .replace(REPLACE,DISABLED,1))
    if (altered.count(placement)!=1 or altered.count(DISABLED)!=1 or
            altered.count(" Solid {")!=9 or
            altered.count("boundingObject Box")!=9 or
            altered.count(observer.MARKER)!=1 or MARKER in altered):
        raise ValueError("physical contact mutant is not isolated")
    return altered.rstrip()+"\n"+MARKER+"\n"


def run_one(letter,part):
    body=compose(letter,part)
    case=f"{letter.lower()}_{part.lower()}"
    world=ROOT/f"worlds/ci_mini_gp_low_contact_{case}.wbt"
    project=ROOT/f"worlds/.ci_mini_gp_low_contact_{case}.wbproj"
    log=ARTIFACT/case/"webots.log"
    log.parent.mkdir(parents=True,exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing overwrite of another Webots world")
    proc=None
    try:
        world.write_text(body,encoding="utf-8")
        project.write_text(observer.PROJECT,encoding="utf-8")
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as output:
            proc=subprocess.Popen(
                ["timeout","-k","5s","50s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=fast",str(world)],
                cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline=time.monotonic()+42
            while time.monotonic()<deadline:
                output.flush()
                data=log.read_text(encoding="utf-8",errors="replace")
                if (CONTACT in data or "WB_MINI_NATIVE_FATAL" in data or
                        proc.poll() is not None):
                    break
                time.sleep(.20)
    finally:
        if proc is not None:
            try: os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait(timeout=6)
            # A terminated xvfb-run wrapper may have surviving descendants.
            try: os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError: pass
        if world.exists():
            if world.read_text(encoding="utf-8")!=body:
                raise RuntimeError("refuse cleanup of changed low-contact world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8")!=observer.PROJECT:
                raise RuntimeError("refuse cleanup of changed Webots project")
            project.unlink()
    data=log.read_text(encoding="utf-8",errors="replace")
    contact=re.findall(
        r"WB_MINI_NATIVE_COLLIDER_CONTACT type=([A-Z_]+) "
        r"z=(-?[0-9.]+) node_id=(\d+)",data)
    first=re.findall(
        rf"WB_MINI_NATIVE_FIRST variant={letter} attempt=1 .* contact=(-?\d+)",
        data)
    if (len(contact)!=1 or contact[0][0]!=part or
            not math.isfinite(float(contact[0][1])) or
            abs(float(contact[0][1]))>.025 or
            int(contact[0][2])<=0 or
            first!=["1"] or "status=achieved" in data or
            "WB_MINI_NATIVE_FATAL" in data or
            any("ERROR:" in line for line in data.splitlines())):
        raise AssertionError(
            f"physical {part} at low z not independently rejected: "
            +str(log)+" tail="+data[-1900:])
    digest=hashlib.sha256(body.encode("utf-8")).hexdigest()
    print(f"A7_NATIVE_LOW_CONTACT_REJECTED variant={letter} "
          f"obstacle={part} z={contact[0][1]} "
          f"node_id={contact[0][2]} world_sha256={digest} "
          "true_webots_contact=true motors=off",flush=True)
    return {"variant":letter,"obstacle":part,
            "contact_z_m":float(contact[0][1]),
            "partner_native_id":int(contact[0][2]),
            "world_sha256":digest,"native_observer":True,
            "motorized_flight":False,"pupil_wbb":False}


def main():
    result=[run_one(v,p) for v in "LR" for p in ("CORNER_FRONT","CLOSED_PANEL")]
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    (ARTIFACT/"summary.json").write_text(json.dumps({
        "schema":"webeeblocks-a7-low-obstacle-contact-v1",
        "webots":"R2025a","native_low_obstacle_contacts":4,
        "not_pupil_or_real_flight_evidence":True,"results":result},
        sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("A7_NATIVE_LOW_CONTACT_ALL_REJECTED L/R corner and panel",flush=True)


if __name__=="__main__":
    main()
