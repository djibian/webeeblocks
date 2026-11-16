#!/usr/bin/env python3
"""A7 Draft: reject physical A4 scene families mixed into the native L/R world.

Each of four real Webots R2025a worlds contains one intact A7 scene and a
complete genuine A4 world of six physical Solids. The evaluator must fail BEFORE READY,
not after an accidental collision or a pupil-generated completion marker.
This is an observer provenance counterexample, NOT a flown pupil program.
"""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import time

import run_classroom_mini_gp_native_observer as observer

ROOT = observer.ROOT
ARTIFACT = ROOT / "ci-artifacts/progression-mini-gp-foreign-scene"
MARKER = "# WEBEEBLOCKS_A7_FOREIGN_A4_SCENE_REFUSAL_CI_ONLY"
FATAL = "WB_MINI_NATIVE_FATAL invalid native scene, colliders or observer"


def compose(letter, foreign):
    if type(letter) is not str or letter not in ("L", "R"):
        raise ValueError("invalid A7 variant")
    if type(foreign) is not str or foreign not in ("A", "B"):
        raise ValueError("invalid A4 foreign scene")
    source = observer.compose(letter)
    if (source.count(observer.MARKER) != 1 or
            "WEBEEBLOCKS_DECISION_A_SCENE" in source or
            "WEBEEBLOCKS_DECISION_B_SCENE" in source or MARKER in source):
        raise ValueError("already polluted A7 baseline")
    identity = "WEBEEBLOCKS_DECISION_" + foreign + "_SCENE"
    # Reuse the actual released A4 scene with SIX real colliders. Merely
    # adding an A4-looking DEF would not prove that the A7 evaluator refuses
    # a second physically legitimate mission. The extra A4 evaluator is
    # inactive in this CI-only mutant: only the A7 observer decides admission.
    alien = (ROOT / "worlds/scenes" /
             ("decision-h-" + foreign.lower() + "-v1.wbo")).read_text(
                 encoding="utf-8")
    a4_controller = 'controller "progression_decision_h_v1"'
    if (alien.count("DEF " + identity + " Group {") != 1 or
            alien.count(" Solid {") != 6 or
            alien.count("boundingObject Box") != 6 or
            alien.count(a4_controller) != 1 or
            alien.count('Robot {') != 1):
        raise ValueError("untrusted genuine A4 physical asset")
    alien = alien.replace(a4_controller, 'controller "<none>"', 1)
    result = source.rstrip() + "\n" + MARKER + "\n" + alien
    if (result.count("DEF " + identity + " Group {") != 1 or
            result.count("boundingObject Box") != 15 or
        result.count(" Solid {") != 15 or
        result.count('controller "<none>"') != 1 or
        result.count('controller "progression_mini_grand_prix_v1"') != 1 or
        result.count('controller "progression_mini_gp_geometry_probe"') != 1 or
            result.count(observer.MARKER) != 1 or result.count(MARKER) != 1):
        raise ValueError("malformed independent A4 contamination")
    return result


def run_one(letter, foreign):
    source = compose(letter, foreign)
    id_code = letter.lower() + foreign.lower()
    world = ROOT / f"worlds/ci_mini_gp_foreign_{id_code}.wbt"
    project = ROOT / f"worlds/.ci_mini_gp_foreign_{id_code}.wbproj"
    log = ARTIFACT / id_code / "webots.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refuse to overwrite prior native A7 world")
    proc = None
    try:
        world.write_text(source, encoding="utf-8")
        project.write_text(observer.PROJECT, encoding="utf-8")
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log.open("w", encoding="utf-8") as output:
            proc = subprocess.Popen(
                ["timeout", "-k", "5s", "75s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(world)],
                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 65
            while time.monotonic() < deadline:
                output.flush()
                data = log.read_text(encoding="utf-8", errors="replace")
                if (FATAL in data or "WB_MINI_NATIVE_READY" in data or
                        proc.poll() is not None):
                    break
                time.sleep(.25)
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=7)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=7)
        if world.exists():
            if world.read_text(encoding="utf-8") != source:
                raise RuntimeError("refuse cleanup of mutated A7 foreign world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != observer.PROJECT:
                raise RuntimeError("refuse cleanup of mutated A7 Webots project")
            project.unlink()

    data = log.read_text(encoding="utf-8", errors="replace")
    if (data.count(FATAL) != 1 or
            "WB_MINI_NATIVE_READY" in data or
            "WB_MINI_NATIVE_ATTEMPT" in data or
            "WB_MINI_NATIVE_RESULT" in data or
            any("ERROR:" in line for line in data.splitlines())):
        raise AssertionError(f"foreign A4 was not rejected before A7 READY: {log}")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    print(f"A7_FOREIGN_A4_REJECTED a7={letter} a4={foreign} "
          f"world_sha256={digest} before_ready=true", flush=True)
    return {"a7": letter, "a4": foreign, "pass": True,
            "before_ready": True, "world_sha256": digest,
            "motorized_flight": False, "pupil_wbb": False}


def main():
    results = [run_one(letter, foreign) for letter in "LR" for foreign in "AB"]
    if len(results) != 4 or not all(row["pass"] for row in results):
        raise AssertionError("all four native combinations must fail closed")
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    (ARTIFACT / "summary.json").write_text(
        json.dumps({"schema": "webeeblocks-a7-foreign-a4-rejection-v1",
                    "webots": "R2025a", "real_foreign_colliders": True,
                    "not_release_evidence": True, "results": results},
                   sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("A7_FOREIGN_A4_NATIVE_ALL_REJECTED L+A,L+B,R+A,R+B", flush=True)


if __name__ == "__main__":
    main()
