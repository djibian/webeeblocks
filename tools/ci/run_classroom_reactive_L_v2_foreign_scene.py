#!/usr/bin/env python3
"""A5 Draft native Webots: reject mixed physical A4/A5 before mission READY.

Six real R2025a worlds: A5 A/B/C multiplied by the released A4 A/B WBO.
The independent C A5 observer must reject the added official A4 colliders.
Neither the pupil's Blockly nor A5 flight physics is modified in this test.
"""
from pathlib import Path
import hashlib
import json

import run_classroom_reactive_L_sensor_v2 as sensor
from run_classroom_reactive_L_v2_evaluator_attestation import compose_with_evaluator

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "ci-artifacts/progression-reactive-L-v2-foreign-a4"
FATAL = "WEBEEBLOCKS_A5_V2_FATAL native scene geometry/identity"
MARKER = "# WEBEEBLOCKS_A5_V2_FOREIGN_A4_REAL_COLLIDERS_CI_ONLY"


def compose(letter, foreign):
    if type(letter) is not str or letter not in "ABC" or len(letter) != 1:
        raise ValueError("untrusted A5 variant")
    if type(foreign) is not str or foreign not in "AB" or len(foreign) != 1:
        raise ValueError("untrusted A4 foreign variant")
    baseline = compose_with_evaluator(letter)
    if (baseline.count('controller "progression_reactive_L_v2"') != 1 or
            baseline.count('controller "progression_reactive_L_sensor_probe_v2"') != 1 or
            "WEBEEBLOCKS_DECISION_A_SCENE" in baseline or
            "WEBEEBLOCKS_DECISION_B_SCENE" in baseline or
            MARKER in baseline):
        raise ValueError("A5 baseline already mixed or modified")
    alien = (ROOT / f"worlds/scenes/decision-h-{foreign.lower()}-v1.wbo"
             ).read_text(encoding="utf-8")
    identity = f"DEF WEBEEBLOCKS_DECISION_{foreign}_SCENE Group"
    controller = 'controller "progression_decision_h_v1"'
    if (alien.count(identity) != 1 or
            alien.count(" Solid {") != 6 or
            alien.count("boundingObject Box") != 6 or
            alien.count(controller) != 1 or
            alien.count('supervisor TRUE') != 1):
        raise ValueError("foreign physical A4 scene is not official")
    # Keep the genuine A4 geometry and its six colliders, but silence the
    # irrelevant second evaluator in this test-only world. The A5 evaluator
    # alone is responsible for fail-closed native scene provenance.
    alien = alien.replace(controller, 'controller "<none>"', 1)
    mixed = baseline.rstrip() + "\n" + MARKER + "\n" + alien.rstrip() + "\n"
    expected_boxes = (7 if letter == "C" else 5) + 6
    if (mixed.count(identity) != 1 or
            mixed.count(" Solid {") != expected_boxes or
            mixed.count("boundingObject Box") != expected_boxes or
            mixed.count('controller "progression_reactive_L_v2"') != 1 or
            mixed.count(MARKER) != 1):
        raise ValueError("invalid mixed A4/A5 physical scene")
    return mixed


def run_one(letter, foreign):
    original_compose, original_artifacts, original_fatal = (
        sensor.compose, sensor.ARTIFACTS, sensor.FATAL)
    mixed = compose(letter, foreign)
    # Existing R2025a runner owns the temporary world and atomically checks
    # its contents before cleanup. Nested proof directories do not collide.
    location = ARTIFACTS / f"{letter}{foreign}"
    sensor.compose = lambda incoming: mixed if incoming == letter else (
        _refuse_unexpected(incoming))
    sensor.ARTIFACTS = location
    sensor.FATAL = FATAL
    try:
        try:
            sensor.run_one(letter)
        except AssertionError:
            pass  # The positive sensor runner will refuse the negative world.
    finally:
        sensor.compose = original_compose
        sensor.ARTIFACTS = original_artifacts
        sensor.FATAL = original_fatal
    log = location / letter / "webots.log"
    if not log.is_file():
        raise AssertionError("missing real R2025a mixed-world log: " + str(log))
    data = log.read_text(encoding="utf-8", errors="replace")
    if (data.count(FATAL) != 1 or
            "WEBEEBLOCKS_A5_V2_NATIVE_C_READY" in data or
            "WEBEEBLOCKS_A5_V2_RESULT" in data or
            # The separate test-only range probe may finish its observations
            # after the independent A5 evaluator has already refused READY.
            any("ERROR:" in item for item in data.splitlines())):
        raise AssertionError(
            f"native A5 failed to refuse official A4 {foreign} before READY: "
            + str(log) + " tail=" + data[-1500:])
    digest = hashlib.sha256(mixed.encode("utf-8")).hexdigest()
    print(f"A5_FOREIGN_A4_REJECTED a5={letter} a4={foreign} "
          f"world_sha256={digest} before_ready=true real_colliders=true",
          flush=True)
    return {"a5": letter, "a4": foreign, "before_ready": True,
            "world_sha256": digest, "real_colliders": True,
            "pupil_wbb": False, "motorized_flight": False}


def _refuse_unexpected(value):
    raise ValueError(f"unexpected variant during mixed-world native test: {value!r}")


def main():
    results = [run_one(v, a4) for v in "ABC" for a4 in "AB"]
    if len(results) != 6 or not all(row["before_ready"] for row in results):
        raise AssertionError("all six physical mixed missions must fail closed")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "summary.json").write_text(
        json.dumps({"schema": "webeeblocks-a5-foreign-a4-rejection-v1",
                    "webots": "R2025a", "mixed_worlds": 6,
                    "real_colliders_per_a4": 6,
                    "not_pupil_flight_or_product_acceptance": True,
                    "results": results},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("A5_FOREIGN_A4_ALL_REJECTED A+A A+B B+A B+B C+A C+B",
          flush=True)


if __name__ == "__main__":
    main()
