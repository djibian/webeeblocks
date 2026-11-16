#!/usr/bin/env python3
"""A7 Draft-only R2025a negative: the mission observer must reject 64-ms worlds.

The only change from each accepted L/R native scene is WorldInfo.basicTimeStep.
The physics geometry and controller identity remain unchanged. This is not a
motorized or pupil-program test; it qualifies a fail-closed admission boundary.
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
ARTIFACT = ROOT / "ci-artifacts/progression-mini-gp-wrong-timestep"
MARKER = "# WEBEEBLOCKS_A7_WRONG_TIMESTEP_CI_ONLY"
FATAL = "WB_MINI_NATIVE_FATAL invalid timestep=64 expected=32"


def compose(letter):
    if type(letter) is not str or letter not in ("L", "R"):
        raise ValueError("invalid A7 variant")
    original = observer.compose(letter)
    if (original.count("basicTimeStep 32") != 1 or
            "basicTimeStep 64" in original or MARKER in original or
            original.count(observer.MARKER) != 1 or
            original.count('controller "progression_mini_grand_prix_v1"') != 1 or
            original.count(" Solid {") != 9 or
            original.count("boundingObject Box") != 9):
        raise ValueError("unexpected canonical A7 native scene")
    changed = original.replace("basicTimeStep 32", "basicTimeStep 64", 1)
    changed = changed.rstrip() + "\n" + MARKER + "\n"
    if (changed.count("basicTimeStep 64") != 1 or
            "basicTimeStep 32" in changed or
            changed.count(" Solid {") != 9 or
            changed.count("boundingObject Box") != 9 or
            changed.count('controller "progression_mini_grand_prix_v1"') != 1 or
            changed.count(observer.MARKER) != 1 or
            changed.count(MARKER) != 1):
        raise ValueError("wrong-step mutation altered the accepted scene")
    return changed


def run_one(letter):
    source = compose(letter)
    suffix = letter.lower()
    world = ROOT / f"worlds/ci_mini_gp_wrong_step_{suffix}.wbt"
    project = ROOT / f"worlds/.ci_mini_gp_wrong_step_{suffix}.wbproj"
    log = ARTIFACT / letter / "webots.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refuse overwrite of an existing R2025a experiment")
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
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if world.exists():
            if world.read_text(encoding="utf-8") != source:
                raise RuntimeError("refuse cleanup of altered wrong-step world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != observer.PROJECT:
                raise RuntimeError("refuse cleanup of altered Webots project")
            project.unlink()

    data = log.read_text(encoding="utf-8", errors="replace")
    if (data.count(FATAL) != 1 or
            "WB_MINI_NATIVE_READY" in data or
            "WB_MINI_NATIVE_ATTEMPT" in data or
            "WB_MINI_NATIVE_RESULT" in data or
            any("ERROR:" in line for line in data.splitlines())):
        raise AssertionError(f"wrong native timestep admitted or ambiguous: {log}")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    print(f"A7_WRONG_TIMESTEP_REJECTED variant={letter} "
          f"timestep_ms=64 before_ready=true world_sha256={digest}", flush=True)
    return {"variant": letter, "wrong_timestep_ms": 64, "before_ready": True,
            "world_sha256": digest, "motorized_flight": False,
            "pupil_program_tested": False}


def main():
    results = [run_one(letter) for letter in "LR"]
    if len(results) != 2 or not all(row["before_ready"] for row in results):
        raise AssertionError("both native Mini GP variants must reject 64-ms")
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    (ARTIFACT / "summary.json").write_text(
        json.dumps({"schema": "webeeblocks-a7-wrong-timestep-rejection-v1",
                    "webots": "R2025a", "not_release_evidence": True,
                    "results": results}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    print("A7_WRONG_TIMESTEP_BOTH_REJECTED L,R at 64ms before READY", flush=True)


if __name__ == "__main__":
    main()
