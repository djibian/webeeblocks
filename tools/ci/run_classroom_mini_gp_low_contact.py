#!/usr/bin/env python3
"""A7 Draft Webots physical test: real low-z contact with two obstacles on L/R.

The genuine R2025a geometry probe teleports an unpowered Crazyflie through
seven real near-floor approaching offsets. It emits separate real obstacle-side
contact evidence, and issues fresh native attempt tokens to the independent C
A7 oracle. To pass, the C oracle must classify at least one corresponding
floor-height point as a REAL obstacle collision, never a benign floor point.
Not a pupil, PID or autonomous flight qualification.
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
OLD='customData "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1"'
NATIVE="WB_MINI_NATIVE_COLLIDER_CONTACT"
PROBE="WEBEEBLOCKS_A7_LOW_CONTACT_PHYSICAL"
END="WEBEEBLOCKS_A7_LOW_CONTACT_PROBE_END"


def compose(letter,part):
    if type(letter) is not str or letter not in ("L","R"):
        raise ValueError("invalid A7 letter")
    if type(part) is not str or part not in ("CORNER_FRONT","CLOSED_PANEL"):
        raise ValueError("invalid obstacle identity")
    source=observer.compose(letter)
    new=f'customData "WEBEEBLOCKS_A7_LOW_CONTACT_{part}_V1"'
    if (source.count(OLD)!=1 or source.count(observer.MARKER)!=1 or
            source.count('controller "progression_mini_gp_geometry_probe"')!=1 or
            source.count('controller "progression_mini_grand_prix_v1"')!=1 or
            source.count(" Solid {")!=9 or MARKER in source):
        raise ValueError("untrusted physical A7 baseline")
    result=source.replace(OLD,new,1).rstrip()+"\n"+MARKER+"\n"
    if (result.count(new)!=1 or OLD in result or
            result.count(" Solid {")!=9 or
            result.count("boundingObject Box")!=9 or
            result.count(observer.MARKER)!=1):
        raise ValueError("untrusted low-contact probe mutation")
    return result


def run_one(letter,part):
    source=compose(letter,part)
    case=f"{letter.lower()}_{part.lower()}"
    world=ROOT/f"worlds/ci_mini_gp_low_contact_{case}.wbt"
    project=ROOT/f"worlds/.ci_mini_gp_low_contact_{case}.wbproj"
    log=ARTIFACT/case/"webots.log"
    log.parent.mkdir(parents=True,exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing overwrite of another Webots world")
    proc=None
    try:
        world.write_text(source,encoding="utf-8")
        project.write_text(observer.PROJECT,encoding="utf-8")
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as output:
            proc=subprocess.Popen(
                ["timeout","-k","5s","55s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=fast",str(world)],
                cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline=time.monotonic()+46
            while time.monotonic()<deadline:
                output.flush()
                data=log.read_text(encoding="utf-8",errors="replace")
                if (END in data or "WB_MINI_NATIVE_FATAL" in data or
                        "WEBEEBLOCKS_A7_NATIVE_FATAL" in data or
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
            try: os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError: pass
        if world.exists():
            if world.read_text(encoding="utf-8")!=source:
                raise RuntimeError("refuse cleanup of altered near-floor world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8")!=observer.PROJECT:
                raise RuntimeError("refuse cleanup of altered Webots project")
            project.unlink()
    data=log.read_text(encoding="utf-8",errors="replace")
    hits=re.findall(
        r"WB_MINI_NATIVE_COLLIDER_CONTACT type=([A-Z_]+) "
        r"z=(-?[0-9.]+) node_id=(\d+)",data)
    physical=re.findall(
        rf"WEBEEBLOCKS_A7_LOW_CONTACT_PHYSICAL variant={letter} "
        rf"obstacle={part} z=(-?[0-9.]+) contact_node_id=(\d+) contact_count=(\d+)",
        data)
    summary=re.findall(
        rf"WEBEEBLOCKS_A7_LOW_CONTACT_PROBE_END variant={letter} "
        rf"obstacle={part} low_contacts=(\d+) obstacle_id=(\d+) motors=OFF",
        data)
    native=[(kind,float(z),int(node)) for kind,z,node in hits
            if kind==part and math.isfinite(float(z))
            and abs(float(z))<=.025 and int(node)>0]
    if (not native or not physical or len(summary)!=1 or
            int(summary[0][0])<1 or
            native[0][2]!=int(summary[0][1]) or
            int(physical[0][1])<=0 or
            "status=achieved" in data or
            "WB_MINI_NATIVE_FATAL" in data or
            "WEBEEBLOCKS_A7_NATIVE_FATAL" in data or
            any("ERROR:" in line for line in data.splitlines())):
        raise AssertionError(
            f"real low-floor {part} not detected by both supervisors: "
            +str(log)+" tail="+data[-2800:])
    digest=hashlib.sha256(source.encode("utf-8")).hexdigest()
    print(f"A7_NATIVE_LOW_CONTACT_REJECTED variant={letter} "
          f"obstacle={part} z={native[0][1]:.9f} "
          f"node_id={native[0][2]} world_sha256={digest} "
          "two_native_supervisors=true motors=off",flush=True)
    return {"variant":letter,"obstacle":part,"native_contact_z_m":native[0][1],
            "collider_node_id":native[0][2],"world_sha256":digest,
            "low_contacts":int(summary[0][0]),
            "native_independent_observer":True,
            "motorized_flight":False,"pupil_wbb":False}


def main():
    cases=[run_one(v,p) for v in "LR"
           for p in ("CORNER_FRONT","CLOSED_PANEL")]
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    (ARTIFACT/"summary.json").write_text(json.dumps({
        "schema":"webeeblocks-a7-low-obstacle-contact-v2",
        "webots":"R2025a","native_low_obstacle_contacts":4,
        "not_pupil_or_real_flight_evidence":True,"cases":cases},
        sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("A7_NATIVE_LOW_CONTACT_ALL_REJECTED L/R corner and panel",flush=True)


if __name__=="__main__":
    main()
