#!/usr/bin/env python3
"""Native R2025a A5 information-aliasing experiment, deliberately NOT pupil flight.

Two physically attested worlds differ only by an early L cue; late decision
rays were first sampled under cardinal headings using real Multi-ranger
sensor devices on the ORIGINAL Crazyflie. This probes oblique searches at a\nfixed pose, not nearby translations or return-to-cue trajectories.\nThis is not a claim of memory
necessity under arbitrary movement or a human classroom PASS.
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
import prepare_classroom_altitude_scene_ack as classroom

ROOT = classroom.ROOT
OUT = ROOT / "ci-artifacts/progression-reactive-L-memory-alias"
LETTERS = "AB"
SOURCE_CONTROLLER = 'controller "crazyflie_classroom_v2"'
PROBE_CONTROLLER = 'controller "progression_reactive_L_memory_alias_probe"'
SOURCE_WINDOW = 'window "altitude_scene_ack_probe"'
MARKER = "# WEBEEBLOCKS_A5_MEMORY_ALIAS_NATIVE_CI_ONLY"
PROJECT = "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
SAMPLE = re.compile(
    r"WEBEEBLOCKS_A5_ALIAS_SAMPLE variant=([AB]) phase=(early|late|detour) turn=([0-9]{1,2}) "
    r"front=([0-9.]+) left=([0-9.]+) right=([0-9.]+) "
    r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) time=([0-9.]+)"
)
DONE = re.compile(
    r"WEBEEBLOCKS_A5_ALIAS_DONE variant=([AB]) early=true late_scans=16 detour_sample=true "
    r"teleport_only=true motorized_flight=false"
)
FATAL = "WEBEEBLOCKS_A5_ALIAS_FATAL"

def scene_path(letter):
    return ROOT / f"worlds/scenes/reactive-L-memory-alias-{letter.lower()}-proto.wbo"

def compose(letter, scene=None):
    if type(letter) is not str or letter not in LETTERS or len(letter) != 1:
        raise ValueError("only explicit A/B information-alias prototype worlds")
    base = classroom.compose(classroom.SOURCE.read_text(encoding="utf-8"))
    scene = (scene_path(letter).read_text(encoding="utf-8")
             if scene is None else scene)
    identity = f"DEF WEBEEBLOCKS_A5_ALIAS_{letter}_SCENE Group"
    if (base.count(SOURCE_CONTROLLER) != 1 or base.count(SOURCE_WINDOW) != 1
        or base.count(classroom.MARKER) != 1
        or scene.count(identity) != 1
        or scene.count(" Solid {") != 3
        or scene.count("boundingObject Box") != 3
        or "Robot {" in scene
        or f'A5_ALIAS_{letter}_CUE_ARM' not in scene
        or f'A5_ALIAS_{letter}_CUE_TIP' not in scene
        or f'A5_ALIAS_{letter}_TERMINAL' not in scene
        or any(f"DEF WEBEEBLOCKS_A5_ALIAS_{other}_SCENE" in scene
               for other in LETTERS if other != letter)):
        raise ValueError("not a unique three-Solid native A5 alias scene")
    body = base.replace(SOURCE_CONTROLLER, PROBE_CONTROLLER, 1).replace(
        SOURCE_WINDOW, 'window ""', 1).replace(classroom.MARKER, MARKER, 1)
    if (body.count(PROBE_CONTROLLER) != 1 or
        SOURCE_CONTROLLER in body or SOURCE_WINDOW in body or
        "DEF WEBEEBLOCKS_A5_ALIAS_" in body or
        'controller "crazyflie_runtime_v2"' in body):
        raise ValueError("cannot uniquely retain the original Crazyflie")
    return body.rstrip() + "\n" + scene.rstrip() + "\n"

def run_one(letter):
    body = compose(letter)
    name = letter.lower()
    world = ROOT / f"worlds/ci_a5_memory_alias_{name}.wbt"
    project = ROOT / f"worlds/.ci_a5_memory_alias_{name}.wbproj"
    folder = OUT / letter
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "webots.log"
    if world.exists() or project.exists():
        raise FileExistsError("native alias CI refuses to overwrite a world")
    proc = None
    try:
        world.write_text(body, encoding="utf-8")
        project.write_text(PROJECT, encoding="utf-8")
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log.open("w", encoding="utf-8") as stream:
            proc = subprocess.Popen(
                ["timeout", "-k", "5s", "85s", "xvfb-run", "-a",
                 "webots", "--stdout", "--stderr", "--batch", "--mode=fast",
                 str(world)], cwd=ROOT, env=env, stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 78
            while time.monotonic() < deadline:
                stream.flush()
                source = log.read_text(encoding="utf-8", errors="replace")
                if DONE.search(source) or FATAL in source or proc.poll() is not None:
                    break
                time.sleep(.25)
    finally:
        if proc:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if world.exists():
            if world.read_text(encoding="utf-8") != body:
                raise RuntimeError("refuse to remove altered Webots alias world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != PROJECT:
                raise RuntimeError("refuse to remove altered Webots project")
            project.unlink()
    source = log.read_text(encoding="utf-8", errors="replace")
    rows = SAMPLE.findall(source)
    terminal = DONE.findall(source)
    if (FATAL in source or len(rows) != 18 or terminal != [letter] or
        [(v, phase, int(idx)) for v, phase, idx, *_ in rows] !=
        [(letter, "early", 0)] +
        [(letter, "late", i) for i in range(16)] +
        [(letter, "detour", 0)]):
        raise AssertionError("missing exact native A5 alias sensor proof " + str(log))
    samples = []
    previous_t = -1.0
    for v, phase, yaw_id, *values in rows:
        front, left, right, x, y, z, t = map(float, values)
        yaw_id = int(yaw_id)
        if (not all(math.isfinite(num) for num in
                    (front, left, right, x, y, z, t)) or
            t <= previous_t or min(front, left, right) < 0 or
            max(front, left, right) > 2.001 or
            abs(x - (1.5 if phase != "early" else 0)) > .035 or
            abs(y - (.60 if phase == "detour" else 0)) > .035 or abs(z - .50) > .09):
            raise AssertionError("invalid original native sensor, pose or timestamp")
        previous_t = t
        samples.append({"phase":phase, "turn_quarter":yaw_id,
                        "front":front, "left":left, "right":right,
                        "x":x, "y":y, "z":z, "time":t,
                        "yaw_deg": 180.0 if phase == "detour" else yaw_id * 22.5})
    (folder / "samples.json").write_text(
        json.dumps({"variant":letter,
                    "method":"R2025a original Crazyflie native sensors; Supervisor pose isolation",
                    "real_motor_flight":False,
                    "physical_cue_attested":True,
                    "samples":samples}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"WEBEEBLOCKS_A5_ALIAS_NATIVE_OBSERVED variant={letter} "
          f"early_left_m={samples[0]['left']:.9f} "
          "late_oblique_scans=16 pupil_flight=UNPROVEN", flush=True)
    return samples

def main():
    data = {v:run_one(v) for v in LETTERS}
    near = data["A"][0]["left"]
    far = data["B"][0]["left"]
    if not (.10 < near < 1.5 and .10 < far < 1.8 and
            far-near > .35):
        raise AssertionError("real early L cue is not discriminating")
    # Adversarial pupil-toolbox hypothesis: one can move to (1.50,+0.60),
    # face west using only 90-degree turns, and read FRONT instead of storing
    # the original L clue. The supervisor ISOLATES the sensing geometry only.
    # No motorized detour, command acceptance, collision-free route, return,
    # or pupil Blockly program is proven by this measurement.
    a_detour, b_detour = data["A"][17], data["B"][17]
    detour_delta = abs(a_detour["front"] - b_detour["front"])
    detour = {
        "schema": "webeeblocks-a5-cardinal-detour-native-v1",
        "method": "R2025a original Crazyflie range_front at supervisor-set pose",
        "position_m": {"x": 1.50, "y": 0.60, "z": 0.50},
        "yaw_deg": 180,
        "student_turns_required_deg": [90, 90],
        "front_A_m": a_detour["front"],
        "front_B_m": b_detour["front"],
        "difference_m": detour_delta,
        "discrimination_threshold_m": .35,
        "discriminating": detour_delta > .35,
        "motorized_detour_proven": False,
        "collision_free_detour_proven": False,
        "pupil_program_without_memory_proven": False,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cardinal-detour.json").write_text(
        json.dumps(detour, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("WEBEEBLOCKS_A5_CARDINAL_DETOUR_NATIVE_OBSERVED " +
          json.dumps(detour, sort_keys=True), flush=True)
    deltas = []
    for idx in range(1, 17):
        for direction in ("front","left","right"):
            a, b = data["A"][idx][direction], data["B"][idx][direction]
            deltas.append(abs(a-b))
    if not deltas or max(deltas) > .035:
        # A scientifically useful negative result must survive the failed job.
        # Keep all six revealing rays' true A/B readings, without converting
        # the false alias hypothesis into a passing experiment.
        revealing = []
        for index, delta in enumerate(deltas):
            if delta <= .035:
                continue
            scan_index, direction_index = divmod(index, 3)
            direction = ("front", "left", "right")[direction_index]
            a = data["A"][scan_index + 1][direction]
            b = data["B"][scan_index + 1][direction]
            revealing.append({
                "yaw_deg": scan_index * 22.5,
                "direction": direction,
                "variant_A_m": a,
                "variant_B_m": b,
                "difference_m": delta,
            })
        refutation = {
            "schema": "webeeblocks-a5-alias-refutation-native-v1",
            "outcome": "REFUTED",
            "threshold_m": .035,
            "maximum_difference_m": max(deltas) if deltas else None,
            "early_left_difference_m": far - near,
            "late_scans_per_variant": 16,
            "original_range_sensors": ["front", "left", "right"],
            "revealing_rays": revealing,
            "sensor_physics_native": True,
            "motorized_student_program_proven": False,
            "student_turns_90deg_only_not_falsified": True,
        }
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "refutation.json").write_text(
            json.dumps(refutation, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("WEBEEBLOCKS_A5_ALIAS_NATIVE_REFUTED " +
              json.dumps({"maximum_difference_m": refutation["maximum_difference_m"],
                          "revealing_rays": revealing}, sort_keys=True),
              flush=True)
        raise AssertionError("late R2025a rays still reveal earlier variant: " +
                             repr(deltas))
    evidence = {
        "schema":"webeeblocks-a5-alias-prototype-native-v1",
        "early_left_difference_m":far-near,
        "late_max_native_ray_delta_m":max(deltas),
        "sixteen_native_22p5_degree_rotations":True,
        "all_three_original_range_sensors_compared":True,
        "same_late_physical_solid_and_two_visual_pads":True,
        "not_motorized":True,
        "not_pupil_oralce_or_AST_qualification":True,
        "backtracking_or_local_translations_not_falsified":True,
        "variable_required_for_all_strategies_NOT_PROVEN":True,
        "classroom_student_PASS":False,
        "variants":data
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(
        json.dumps(evidence,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("WEBEEBLOCKS_A5_ALIAS_PROTOTYPE_NATIVE_PASS "
          f"early_difference_m={far-near:.6f} "
          f"late_max_delta_m={max(deltas):.9f} "
          "scope=local_perception_only motor_flight=UNPROVEN",flush=True)

if __name__ == "__main__":
    main()
