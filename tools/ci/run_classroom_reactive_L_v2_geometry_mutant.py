#!/usr/bin/env python3
"""Actual R2025a A5 v2 rotated-physical-collider startup counterexample.

Tests the NATIVE evaluator, not a textual AST or a Python approximation.
Baseline A/B/C native startup is required separately in the same Draft job.
No pupil flight, no motors, no scene edits during a flight.
"""
import hashlib
from pathlib import Path

import run_classroom_reactive_L_sensor_v2 as sensor
from run_classroom_reactive_L_v2_evaluator_attestation import (
    compose_with_evaluator,
)

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=ROOT/"ci-artifacts/progression-reactive-L-v2-mutant"
DEF="DEF ACTIVITY5_V2_A_L1_FRONT Solid {"
TRANSLATION="    translation 1.020 0.000 0.550"
ROTATION="    rotation 0 0 1 1.5707963267948966"
FATAL="WEBEEBLOCKS_A5_V2_FATAL native scene geometry/identity"
READY="WEBEEBLOCKS_A5_V2_NATIVE_C_READY scene=A"
RESULT="WEBEEBLOCKS_A5_V2_RESULT attempt="


def rotated_scene(letter):
    if letter!="A":
        raise ValueError("only A physical 90-degree-collider mutation is permitted")
    world=compose_with_evaluator(letter)
    anchor=DEF+"\n"+TRANSLATION+"\n"
    if world.count(anchor)!=1 or ROTATION in world:
        raise AssertionError("canonical source wall is not unique and unrotated")
    malformed=world.replace(anchor,anchor+ROTATION+"\n",1)
    if (malformed.count(DEF)!=1 or malformed.count(ROTATION)!=1 or
        malformed.count('controller "progression_reactive_L_v2"')!=1 or
        malformed.count('controller "progression_reactive_L_sensor_probe_v2"')!=1):
        raise AssertionError("the mutation touched unrelated mission identities")
    return malformed


def main():
    # The native reader must *refuse* this changed world BEFORE advertising
    # startup READY; a direct change to the local Box is not sufficient.
    sensor.ARTIFACTS=EVIDENCE
    sensor.compose=rotated_scene
    mutant=rotated_scene("A")
    print("WEBEEBLOCKS_A5_V2_ROTATION_MUTANT_SHA256 "+
          hashlib.sha256(mutant.encode("utf-8")).hexdigest(),flush=True)
    # The original sensor-only runner may refuse this world because a
    # rotated physical wall changes the observed rays. That is irrelevant:
    # the independent mission observer itself MUST refuse identity.
    try:
        sensor.run_one("A")
    except AssertionError:
        pass
    log=(EVIDENCE/"A"/"webots.log")
    if not log.is_file():
        raise AssertionError("missing genuine native Webots negative log")
    actual=log.read_text(encoding="utf-8",errors="replace")
    if (actual.count(FATAL)!=1 or READY in actual or
        RESULT in actual or "WEBEEBLOCKS_A5_V2_SENSOR_FATAL" in actual):
        raise AssertionError(
            "rotated wall did not fail closed in independent native evaluator: "+
            str(log)+" tail="+actual[-1500:])
    print("WEBEEBLOCKS_A5_V2_ROTATED_COLLIDER_REJECTED "
          "native=true before_ready=true outcome=ABSENT pupil_flight=NOT_TESTED",
          flush=True)


if __name__=="__main__":
    main()
