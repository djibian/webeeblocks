#!/usr/bin/env python3
"""PRIVATE A7 hypothesis: can later genuine rays distinguish shifted terminal H?

The published L/R Mini Grand Prix assets and their native mission oracle are
READ ONLY. Supervisor pose samples are not motorized flight or a pupil PASS.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time

import run_classroom_mini_gp_geometry as baseline

ROOT = baseline.ROOT
ARTIFACT = ROOT / "ci-artifacts/a7-terminal-information"
ORIGINAL = ROOT / "worlds/scenes/mini-grand-prix-l-v1.wbo"
MARKER = "# A7_TERMINAL_INFORMATION_PRIVATE_NATIVE_ONLY"
STAGES = (("early_far", -1.25, 0.0, 0.0),
          ("early_near", -0.90, 0.0, 0.0),
          ("late_far", 0.20, 0.40, math.pi/2),
          ("late_near", 0.20, 0.60, math.pi/2))
CHANNELS = ("front", "back", "left", "right", "up")
FATAL = "A7_TERMINAL_INFO_FATAL"
RAY = re.compile(
    r"(?m)^A7_TERMINAL_INFO_SAMPLE variant=([NF]) "
    r"stage=(early_far|early_near|late_far|late_near) "
    r"front=([0-9.]+) back=([0-9.]+) left=([0-9.]+) "
    r"right=([0-9.]+) up=([0-9.]+) "
    r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=([0-9.]+) yaw=([0-9.]+)$"
)
DONE = re.compile(r"(?m)^A7_TERMINAL_INFO_DONE variant=([NF]) samples=4 "
                  r"native=true supervisor_only=true motorized=false pupil_wbb=false$")

EVALUATOR = (
    '    Robot {\n'
    '      name "Mini Grand Prix native evaluator"\n'
    '      controller "progression_mini_grand_prix_v1"\n'
    '      supervisor TRUE\n'
    '      synchronization TRUE\n'
    '    }\n'
)

def transform_scene(variant):
    """Build a DIFFERENT temporary scene; never edit the real A7 .wbo."""
    if type(variant) is not str or variant not in ("N", "F"):
        raise ValueError("near/far private variants only")
    source = ORIGINAL.read_text(encoding="utf8")
    # All nine native Solid boxes must remain; only the four closed-H
    # positions and the 17 visual pad/checker poses move as one rigid target.
    assert source.count(" Solid {") == 9
    assert source.count(" 1.420 ") == 4
    assert source.count("translation 0.200 0.950 0.002") == 1
    replacements = [
        (" 1.420 ", f" {1.22 if variant == 'N' else 1.62:.3f} ", 4),
        ("translation 0.200 0.950 0.002",
         f"translation 0.200 {0.75 if variant == 'N' else 1.15:.3f} 0.002", 1),
    ]
    shift = -.20 if variant == "N" else .20
    for y in (.854, .918, .982, 1.046):
        old = f" {y:.6f} 0.0042"
        new = f" {y + shift:.6f} 0.0042"
        replacements.append((old, new, 4))
    for old, new, expected in replacements:
        if source.count(old) != expected:
            raise AssertionError(f"source scene unexpected: {old} expected {expected}")
        source = source.replace(old, new)
    if source.count(" Solid {") != 9 or source.count("boundingObject Box") != 9:
        raise AssertionError("terminal variant lost an obstacle")
    return source


def compose(variant):
    # This trusted existing helper first verifies the ORIGINAL L scene
    # shape, evaluator and physical H count before any private substitution.
    scene = transform_scene(variant)
    world = baseline.compose("L", scene=scene)
    old = 'controller "progression_mini_gp_geometry_probe"'
    new = 'controller "a7_terminal_info_probe"'
    if world.count(old) != 1 or world.count(EVALUATOR) != 1:
        raise AssertionError("cannot isolate private native controller")
    world = world.replace(old, new, 1).replace(EVALUATOR, "", 1)
    world += MARKER + "\n"
    if (world.count(new) != 1 or old in world or
        'controller "progression_mini_grand_prix_v1"' in world or
        world.count(" Solid {") != 9 or
        world.count("boundingObject Box") != 9 or
        world.count("WEBEEBLOCKS_MINI_GP_L_SCENE Group") != 1):
        raise AssertionError("private test world not isolated")
    return world


def validate(observed):
    """Fail closed. Mocks used by unittest do not constitute native evidence."""
    if set(observed) != {"N", "F"}:
        raise AssertionError("missing world variant")
    for v in ("N", "F"):
        if set(observed[v]) != {s for s, _, _, _ in STAGES}:
            raise AssertionError("missing or repeated phase")
        for stage, _, _, _ in STAGES:
            rays = observed[v][stage]
            if set(rays) != set(CHANNELS):
                raise AssertionError("missing/extra multiranger channels")
            if any(type(rays[ch]) not in (int, float) or
                   not math.isfinite(rays[ch]) or not 0 <= rays[ch] <= 2.001
                   for ch in CHANNELS):
                raise AssertionError("nonfinite/out-of-range native reading")
    for stage in ("early_far", "early_near"):
        for ch in CHANNELS:
            delta = abs(observed["N"][stage][ch] - observed["F"][stage][ch])
            if delta > .025:
                raise AssertionError(f"terminal information leaks early: {stage}/{ch} {delta}")
    for stage in ("late_far", "late_near"):
        near = observed["N"][stage]["front"]
        far = observed["F"][stage]["front"]
        if not (.15 < near < 1.8 and .15 < far < 1.8 and .25 <= far-near <= .55):
            raise AssertionError(f"terminal range not discriminable late: {stage} {near}/{far}")
    return True


def run_one(variant):
    folder = ARTIFACT / variant
    folder.mkdir(parents=True, exist_ok=True)
    source = compose(variant)
    world = ROOT / f"worlds/ci_a7_terminal_info_{variant.lower()}.wbt"
    wbproj = ROOT / f"worlds/.ci_a7_terminal_info_{variant.lower()}.wbproj"
    project_text = baseline.PROJECT_TEXT
    log = folder / "webots.log"
    if any(p.exists() or p.is_symlink() for p in (world, wbproj)):
        raise FileExistsError("refuse to overwrite any test world")
    proc = None
    try:
        world.write_text(source, encoding="utf8")
        wbproj.write_text(project_text, encoding="utf8")
        (folder / "world.sha256").write_text(
            hashlib.sha256(source.encode()).hexdigest()+"\n", encoding="utf8")
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log.open("w", encoding="utf8") as out:
            proc = subprocess.Popen(
                ["timeout", "-k", "5s", "85s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(world)],
                cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 78
            while time.monotonic() < deadline:
                out.flush()
                data = log.read_text(encoding="utf8", errors="replace")
                if FATAL in data or DONE.search(data) or proc.poll() is not None:
                    break
                time.sleep(.25)
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait(timeout=5)
        for path, expected in ((world, source), (wbproj, project_text)):
            if path.exists():
                if path.is_symlink() or path.read_text(encoding="utf8") != expected:
                    raise RuntimeError("refuse unsafe cleanup after mutation")
                path.unlink()
    data = log.read_text(encoding="utf8", errors="replace")
    rows = RAY.findall(data)
    if FATAL in data or DONE.findall(data) != [variant] or len(rows) != len(STAGES):
        print(data[-6000:], file=sys.stderr, flush=True)
        raise AssertionError("real terminal sensor evidence incomplete")
    observed = {}
    for row, (stage, x, y, yaw) in zip(rows, STAGES):
        found_variant, found_stage, *numbers = row
        values = list(map(float, numbers))
        if (found_variant != variant or found_stage != stage or len(values) != 9 or
            not all(math.isfinite(v) for v in values) or
            abs(values[5]-x)>.035 or abs(values[6]-y)>.035 or
            abs(values[7]-.50)>.09 or abs(values[8]-yaw)>.001):
            raise AssertionError("attested native stage/pose/yaw mismatch")
        observed[stage] = dict(zip(CHANNELS, values[:5]))
    (folder / "samples.json").write_text(
        json.dumps({"variant": variant, "rays": observed, "supervisor_only": True,
                    "motorized": False, "pupil_wbb": False}, sort_keys=True, indent=2)+"\n",
        encoding="utf8")
    return observed


def main():
    evidence = {v:run_one(v) for v in ("N", "F")}
    validate(evidence)
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    (ARTIFACT/"summary.json").write_text(json.dumps({
        "native_real_rays": True, "early_hidden_at_selected_poses": True,
        "late_front_discriminates_at_selected_poses": True,
        "global_indistinguishability": False, "motorized": False,
        "pupil_wbb": False, "oracle": False
    }, indent=2, sort_keys=True)+"\n",encoding="utf8")
    print("A7_TERMINAL_INFO_NATIVE_PASS early=2 late=2 five_rays=true "
          "supervisor_only=true motorized=false pupil_wbb=false", flush=True)


if __name__ == "__main__":
    main()
