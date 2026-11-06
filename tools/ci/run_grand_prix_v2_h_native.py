#!/usr/bin/env python3
"""Strict manual full-course native R2025a H perception probe (#825).

Never runs a student program. Do not confuse a Python fake or nominal geometry
with true sensor evidence, and do not run alongside non-isolated experiments.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.course_static_world_v2 import static_course_world
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes

DEFAULT_INDICES = (0, 5, 6, 11)
OUT = ROOT / "ci-artifacts/grand-prix-v2-h-native"
CLAIM = "full-course-native-H-rays-and-contact-no-flight"
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


def check_contacts(result, course):
    """Require real beam and terminal collisions plus physically free open H."""
    beams = {box.name: box for box in open_h_boxes(course)}
    boxes = [beams[f"GP_V2_H_{gate.leg_index}_BEAM"]
             for gate in course.gates]
    boxes.append(next(box for box in terminal_boxes(course.route)
                      if box.name == "GP_V2_FINAL_PANEL"))
    witnesses = result.get("contact_witnesses") if type(result) is dict else None
    if (result.get("contact_source") != "Robot+Solid.getContactPoints R2025a" or
            type(witnesses) is not list or len(witnesses) != len(boxes)):
        raise RuntimeError("missing native H physical contact witness")
    used_ids = set()
    last_ms = -1
    for index, (box, record) in enumerate(zip(boxes, witnesses)):
        if (type(record) is not dict or set(record) !=
                {"target", "target_node_id", "passage", "free", "collision"} or
                record["target"] != box.name or
                type(record["target_node_id"]) is not int or
                record["target_node_id"] <= 0 or
                record["target_node_id"] in used_ids):
            raise RuntimeError("wrong native H collider identity")
        used_ids.add(record["target_node_id"])
        if (index == len(boxes) - 1 and record["passage"] is not None):
            raise RuntimeError("terminal H must not assert open passage")
        phases = ("free", "collision") if index == len(boxes) - 1 else (
            "passage", "free", "collision")
        observed_hit = False
        for phase in phases:
            observations = record[phase]
            if type(observations) is not list or len(observations) != 3:
                raise RuntimeError("incomplete native H physical contact phase")
            for sample in observations:
                if (type(sample) is not dict or set(sample) !=
                        {"time_ms", "contacts", "target_contacts"} or
                        type(sample["time_ms"]) is not int or
                        sample["time_ms"] <= last_ms or
                        sample["time_ms"] % 8 or
                        type(sample["contacts"]) is not list or
                        type(sample["target_contacts"]) is not list or
                        len(sample["contacts"]) > 2048 or
                        len(sample["target_contacts"]) > 2048):
                    raise RuntimeError("stale or malformed native H contact tick")
                last_ms = sample["time_ms"]
                for point in sample["contacts"] + sample["target_contacts"]:
                    if (type(point) is not dict or set(point) != {"point", "node_id"} or
                            type(point["node_id"]) is not int or
                            not -(2**31) <= point["node_id"] < 2**31 or
                            type(point["point"]) is not list or
                            len(point["point"]) != 3 or
                            any(type(v) not in (int, float) or
                                not math.isfinite(v) for v in point["point"])):
                        raise RuntimeError("invalid native H contact point")
                if phase != "collision":
                    if sample["contacts"] or sample["target_contacts"]:
                        raise RuntimeError("native open H passage/baseline not free")
                    continue
                for point in sample["target_contacts"]:
                    if point["node_id"] != record["target_node_id"]:
                        raise RuntimeError("native H Solid contact own ID mismatch")
                    xyz = point["point"]
                    if (abs(xyz[0] - box.x) > box.sx / 2 + .002 or
                            abs(xyz[1] - box.y) > box.sy / 2 + .002 or
                            abs(xyz[2] - box.z) > box.sz / 2 + .002):
                        raise RuntimeError("native H contact outside physical Box")
                    if any(math.dist(xyz, own["point"]) <= 1e-6
                           for own in sample["contacts"]):
                        observed_hit = True
        if not observed_hit:
            raise RuntimeError("reciprocal native H physical contact absent")


def native_run(home, indexes, *, output_root=None):
    # Allow the required CI campaign to retain complete H evidence inside its
    # existing always-uploaded geometry artifact; keep manual runs unchanged.
    destination = OUT if output_root is None else Path(output_root)
    destination.mkdir(parents=True, exist_ok=True)
    invocation = Path(tempfile.mkdtemp(prefix="invocation-", dir=destination)).resolve()
    # R2025a CI runs as root in Docker; host Actions must read the evidence.
    invocation.chmod(0o755)
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
            check_contacts(record, course)
            witness = "GP_V2_H_NATIVE " + json.dumps(record, allow_nan=False,
                                                      sort_keys=True)
            if witness not in logs.splitlines():
                raise RuntimeError("H native trace and JSON evidence disagree")
            outcomes.append(dict(configuration=course.identifier,
                                 world_sha256=hashlib.sha256(source.encode()).hexdigest(),
                                 evidence_file=str(proof.relative_to(invocation)),
                                 evidence_sha256=hashlib.sha256(contents).hexdigest()))
            print("PASS native H rays, passage and beam/panel contact (not flight) " +
                  course.identifier, flush=True)
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            world.unlink(missing_ok=True)
            # Webots writes a dot-prefixed project for each temporary world.
            world.with_name("." + world.stem + ".wbproj").unlink(missing_ok=True)
    summary = dict(claim=CLAIM, invocation=invocation.name,
                   webots="R2025a", results=outcomes)
    # An incomplete attempt never publishes a PASSED summary. Concurrent
    # invocations cannot reuse another invocation's proof files.
    with tempfile.NamedTemporaryFile(
            mode="w", prefix=".summary-", suffix=".tmp",
            dir=invocation, encoding="utf-8", delete=False) as tmp:
        pending = Path(tmp.name)
        tmp.write(json.dumps(summary, indent=2) + "\n")
    # tempfile uses mode 0600 inside the container, hidden from the uploader.
    pending.chmod(0o644)
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
