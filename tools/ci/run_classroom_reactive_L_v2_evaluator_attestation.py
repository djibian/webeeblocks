#!/usr/bin/env python3
"""Draft-only A5 v2 native evaluator startup attestation in actual R2025a.

Uses the already-qualified sensor-only world generator with ONE additional
nonphysical, read-only scene evaluator Robot. No motorized Blockly mission,
no customData attempt injection and NO pupil-flight PASS.
"""
from pathlib import Path
import re

import run_classroom_reactive_L_sensor_v2 as probe

ROOT=Path(__file__).resolve().parents[2]
ARTIFACTS=ROOT/"ci-artifacts/progression-reactive-L-v2-evaluator"
BASE_COMPOSE=probe.compose
EVAL_ROBOT = '''
Robot {
  translation 0 0 -1
  name "A5 V2 native evaluator (CI only)"
  controller "progression_reactive_L_v2"
  supervisor TRUE
  synchronization TRUE
}
'''

def compose_with_evaluator(letter,source=None,scene=None):
    native=BASE_COMPOSE(letter,source,scene)
    if native.count('controller "progression_reactive_L_sensor_probe_v2"')!=1:
        raise AssertionError("native Crazyflie source changed before evaluator")
    if 'controller "progression_reactive_L_v2"' in native:
        raise AssertionError("unexpected extra evaluator")
    return native.rstrip()+"\n"+EVAL_ROBOT

def main():
    probe.compose=compose_with_evaluator
    probe.ARTIFACTS=ARTIFACTS
    for letter in "ABC":
        probe.run_one(letter)  # genuine original Crazyflie + real sensor rays
        log=(ARTIFACTS/letter/"webots.log").read_text(encoding="utf-8")
        ready=(f"WEBEEBLOCKS_A5_V2_NATIVE_C_READY scene={letter} "
               "oracle=progression-reactive-L-v2")
        if log.count(ready)!=1 or "WEBEEBLOCKS_A5_V2_FATAL" in log:
            raise AssertionError("independent native evaluator refused A5 scene: "+
                                 str(ARTIFACTS/letter/"webots.log"))
        if re.search(r"WEBEEBLOCKS_A5_V2_RESULT attempt=",log):
            raise AssertionError("evaluator fabricated a student attempt")
        print(f"A5_V2_NATIVE_EVALUATOR_READY variant={letter} "
              "geometry_attested=true pupil_flight=NOT_TESTED",flush=True)
    print("WEBEEBLOCKS_A5_V2_EVALUATOR_STARTUP_ATTESTED "
          "A_B_C=true pupil_flight=NOT_TESTED",flush=True)

if __name__=="__main__":
    main()
