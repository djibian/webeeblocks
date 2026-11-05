#!/usr/bin/env python3
"""Strict manual full-course native R2025a H perception probe (#825).

Never runs a student program. Do not confuse a Python fake or nominal geometry
with true sensor evidence, and do not run alongside non-isolated experiments.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.course_static_world_v2 import static_course_world
from tools.grand_prix.route_courses_v2 import reference_course

DEFAULT_INDICES = (0, 5, 6, 11)
OUT = ROOT / "ci-artifacts/grand-prix-v2-h-native"
CLAIM = "full-course-native-H-rays-no-flight-no-contact"
DIRECTIONS = {"front", "back", "left", "right"}


def probe_scene(index):
    course = reference_course(index)
    text = static_course_world(course)
    count = 8 + 3 * course.count
    if (text.count('controller "<none>"') != 1 or
            text.count('window "<none>"') != 1 or
            text.count("DEF GP_V2_L_") != 4 or
            text.count("DEF GP_V2_H_") != 3 * course.count or
            text.count("DEF GP_V2_FINAL_") != 4 or
            text.count("boundingObject Box { size ") != count or
            "GP_ROUTE_EVALUATOR" in text or
            "controllerArgs" in text):
        raise RuntimeError("full native H scene is noncanonical or active")
    return text.replace('controller "<none>"',
                        'controller "grand_prix_v2_h_probe"', 1)


def _rays(readings):
    return (type(readings) is dict and set(readings) == DIRECTIONS and
            all(type(value) in (int, float) and
                0 <= value <= 2.001
                for value in readings.values()))


def check_native(result, course):
    if (type(result) is not dict or result.get("claim") != CLAIM or
            result.get("configuration") != course.identifier or
            result.get("webots") != "R2025a" or result.get("timestep_ms") != 8):
        raise RuntimeError("native H evidence identity mismatch")
    opened = result.get("opened")
    if type(opened) is not list or len(opened) != course.count:
        raise RuntimeError("incomplete open H native evidence")
    for item, gate in zip(opened, course.gates):
        if (type(item) is not dict or
                item.get("leg") != gate.leg_index or
                item.get("box") != f"GP_V2_H_{gate.leg_index}_BEAM" or
                not _rays(item.get("low")) or not _rays(item.get("high"))):
            raise RuntimeError("noncanonical H rays or native collider identity")
        if not (.07 < item["high"]["front"] < .48 and
                item["low"]["front"] > item["high"]["front"] + .15):
            raise RuntimeError("native open H ray discrimination failed")
    terminal = result.get("terminal")
    if (type(terminal) is not dict or
            terminal.get("box") != "GP_V2_FINAL_PANEL" or
            not _rays(terminal.get("low")) or
            not _rays(terminal.get("high")) or
            not .07 < terminal["low"]["front"] < .55 or
            not .07 < terminal["high"]["front"] < .55):
        raise RuntimeError("native terminal H ray evidence missing")


def native_run(home, indexes):
    OUT.mkdir(parents=True, exist_ok=True)
    invocation = Path(tempfile.mkdtemp(prefix="invocation-", dir=OUT)).resolve()
    print("GP_V2_H_NATIVE_RUN_DIR " + str(invocation), flush=True)
    version = home / "resources/version.txt"
    executable = home / "webots"
    if (not version.is_file() or version.read_text().strip() != "R2025a" or
            not executable.is_file() or not os.access(executable, os.X_OK)):
        raise RuntimeError("full Webots R2025a installation required")
    outcomes = []
    for position, index in enumerate(indexes):
        course = reference_course(index)
        case = invocation / f"{position:02d}-{course.identifier}"
        case.mkdir()
        source = probe_scene(index)
        with tempfile.NamedTemporaryFile(
                mode="w", prefix="ci_gp_v2_h_", suffix=".wbt",
                dir=ROOT / "worlds", encoding="utf-8", delete=False) as target:
            target.write(source)
            world = Path(target.name)
        proof = case / "native.json"
        log = case / "native.log"
        env = dict(os.environ, WEBOTS_HOME=str(home),
                   GP_V2_H_NATIVE_INDEX=str(index), GP_V2_H_NATIVE_OUT=str(proof),
                   LIBGL_ALWAYS_SOFTWARE="true",
                   WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE="true")
        process = None
        try:
            with log.open("w") as stream:
                process = subprocess.Popen(
                    [str(executable), "--stdout", "--stderr", "--batch",
                     "--mode=fast", "--minimize", str(world)],
                    cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
                try:
                    status = process.wait(timeout=120)
                except subprocess.TimeoutExpired as error:
                    raise RuntimeError("native Webots H probe timeout") from error
            logs = log.read_text(errors="replace")
            if (status != 0 or "Traceback (most recent call last)" in logs or
                    any(line.startswith("ERROR:") for line in logs.splitlines())):
                raise RuntimeError("native Webots H probe failed: " + str(log))
            if not proof.is_file():
                raise RuntimeError("no native H ray evidence")
            contents = proof.read_bytes()
            record = json.loads(contents)
            check_native(record, course)
            witness = "GP_V2_H_NATIVE " + json.dumps(record, allow_nan=False,
                                                      sort_keys=True)
            if witness not in logs.splitlines():
                raise RuntimeError("H native trace and JSON evidence disagree")
            outcomes.append(dict(configuration=course.identifier,
                                 world_sha256=hashlib.sha256(source.encode()).hexdigest(),
                                 evidence_file=str(proof.relative_to(invocation)),
                                 evidence_sha256=hashlib.sha256(contents).hexdigest()))
            print("PASS native H rays (not contacts/flight) " +
                  course.identifier, flush=True)
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            world.unlink(missing_ok=True)
            world.with_suffix(".wbproj").unlink(missing_ok=True)
    summary = dict(claim=CLAIM, invocation=invocation.name,
                   webots="R2025a", results=outcomes)
    # An incomplete attempt never publishes a PASSED summary. Concurrent
    # invocations cannot reuse another invocation's proof files.
    with tempfile.NamedTemporaryFile(
            mode="w", prefix=".summary-", suffix=".tmp",
            dir=invocation, encoding="utf-8", delete=False) as tmp:
        pending = Path(tmp.name)
        tmp.write(json.dumps(summary, indent=2) + "\n")
    try:
        os.replace(pending, invocation / "summary.json")
    finally:
        pending.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--index", action="append", type=int, default=[])
    parser.add_argument("--all-12", action="store_true")
    args = parser.parse_args(argv)
    if not args.native:
        parser.error("--native required: static checks are never a sensor PASS")
    if args.all_12 and args.index:
        parser.error("--all-12 cannot be combined with --index")
    indices = tuple(range(12)) if args.all_12 else (
        tuple(args.index) if args.index else DEFAULT_INDICES)
    for index in indices:
        reference_course(index)
    home = os.environ.get("WEBOTS_HOME")
    if not home:
        parser.error("WEBOTS_HOME must point to isolated Webots R2025a")
    native_run(Path(home), indices)


if __name__ == "__main__":
    main()
