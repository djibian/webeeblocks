#!/usr/bin/env python3
"""Three genuine R2025a A5 V2 evaluator attempt identities and native failures.

Runs the real scene-local C observer on the original Crazyflie PROTO. The
test-only probe writes two fresh, premature COMPLETION events to the native
customData channel. No hardware, motors, Blockly or successful pupil flight.
"""
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import time

import run_classroom_reactive_L_v2_evaluator_attestation as startup
import run_classroom_reactive_L_sensor_v2 as sensor

ROOT=sensor.ROOT
ARTIFACTS=ROOT/"ci-artifacts/progression-reactive-L-v2-attempt"
PROJECT_TEXT=sensor.PROJECT_TEXT
PROBE='controller "progression_reactive_L_attempt_probe"'
SENSOR='controller "progression_reactive_L_sensor_probe_v2"'
EVAL='controller "progression_reactive_L_v2"'
MARKER="# WEBEEBLOCKS_A5_V2_NATIVE_ATTEMPTS_CI_ONLY"
DRIVER="""
Robot {
  translation 0 0 -2
  name "A5 V2 test-only attempt protocol driver"
  controller "progression_reactive_L_attempt_probe"
  supervisor TRUE
  synchronization TRUE
}
"""


def compose(letter):
    text=startup.compose_with_evaluator(letter)
    if (text.count(SENSOR)!=1 or text.count(EVAL)!=1 or
        'controller "<none>"' in text or
        text.count('name "Crazyflie WebeeBlocks"')!=1):
        raise AssertionError("original native witness identities changed")
    text=text.replace(SENSOR,'controller "<none>"',1)
    result=text.rstrip()+"\n"+MARKER+"\n"+DRIVER
    if (result.count(PROBE)!=1 or result.count(EVAL)!=1 or
        SENSOR in result or result.count(MARKER)!=1 or
        result.count('controller "<none>"')!=1):
        raise AssertionError("attempt witness changed school identities")
    return result


def run_one(letter):
    source=compose(letter)
    suffix=letter.lower()
    world=ROOT/f"worlds/ci_reactive_L_attempt_{suffix}.wbt"
    project=ROOT/f"worlds/.ci_reactive_L_attempt_{suffix}.wbproj"
    log=ARTIFACTS/letter/"webots.log"
    log.parent.mkdir(parents=True,exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing to overwrite real A5 Webots files")
    proc=None
    try:
        world.write_text(source,encoding="utf-8")
        project.write_text(PROJECT_TEXT,encoding="utf-8")
        print(f"A5_V2_REAL_ATTEMPT_WORLD_SHA256 variant={letter} "+
              hashlib.sha256(source.encode("utf-8")).hexdigest(),flush=True)
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as output:
            proc=subprocess.Popen(
                ["timeout","-k","5s","95s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=fast",str(world)],
                cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,
                start_new_session=True)
            until=time.monotonic()+87
            done=f"WEBEEBLOCKS_A5_V2_ATTEMPT_PROBE_DONE variant={letter}"
            while time.monotonic()<until:
                output.flush()
                content=log.read_text(encoding="utf-8",errors="replace")
                if (done in content or
                    "WEBEEBLOCKS_A5_V2_ATTEMPT_PROBE_FATAL" in content or
                    "WEBEEBLOCKS_A5_V2_FATAL" in content or
                    proc.poll() is not None):
                    break
                time.sleep(.25)
    finally:
        if proc is not None:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait(timeout=6)
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if world.exists():
            if world.read_text(encoding="utf-8")!=source:
                raise RuntimeError("refuse deletion of altered A5 witness world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8")!=PROJECT_TEXT:
                raise RuntimeError("refuse deletion of altered A5 Webots project")
            project.unlink()

    data=log.read_text(encoding="utf-8",errors="replace")
    ready=f"WEBEEBLOCKS_A5_V2_NATIVE_C_READY scene={letter} oracle=progression-reactive-L-v2"
    expected=[
        f"WEBEEBLOCKS_A5_V2_RESULT attempt={i} status=not-achieved stage=0 variant={letter}"
        for i in (1,2)]
    probe=[
        f"WEBEEBLOCKS_A5_V2_ATTEMPT_PROBE_RESULT variant={letter} "
        f"attempt={i} status=not-achieved cause=premature-complete"
        for i in (1,2)]
    evidence=[
        f"WEBEEBLOCKS_A5_V2_ATTEMPT attempt={i}" for i in (1,2)]
    evidence.append(f"WEBEEBLOCKS_A5_V2_ATTEMPT_PROBE_DONE variant={letter} "
                    "two_real_native_attempts=true fresh_attempt_marker=true host_reset=NOT_TESTED no_pupil_flight=true")
    for token in [ready,*expected,*probe,*evidence]:
        if data.count(token)!=1:
            raise AssertionError("missing/duplicate exact native attempt: "+
                                 repr(token)+" log="+str(log)+" tail="+data[-2500:])
    if (data.index(expected[0])>=data.index(expected[1]) or
        data.index(probe[0])>=data.index(probe[1]) or
        "WEBEEBLOCKS_A5_V2_FATAL" in data or
        "WEBEEBLOCKS_A5_V2_ATTEMPT_PROBE_FATAL" in data or
        re.search(r"WEBEEBLOCKS_A5_V2_RESULT .*status=achieved",data)):
        raise AssertionError("A5 native attempt protocol compromised: "+
                             str(log)+" tail="+data[-2500:])
    print(f"A5_V2_REAL_ATTEMPTS variant={letter} first=not-achieved "
          "fresh_second=not-achieved host_reset=NOT_TESTED flight=NOT_TESTED",flush=True)


def main():
    for variant in "ABC":
        run_one(variant)
    print("WEBEEBLOCKS_A5_V2_NATIVE_ATTEMPT_NEGATIVE_CONFIRMED "
          "variants=A_B_C fresh_attempts=2_each host_reset=NOT_TESTED pupil_flight=NOT_TESTED",
          flush=True)


if __name__=="__main__":
    main()
