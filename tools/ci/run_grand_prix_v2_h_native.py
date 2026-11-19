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
from tools.grand_prix.progression_courses import progression_course
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.route_open_h_v2 import open_h_boxes
from tools.grand_prix.route_terminal_v2 import terminal_boxes

DEFAULT_INDICES = (0, 5, 6, 11)
OUT = ROOT / "ci-artifacts/grand-prix-v2-h-native"
CLAIM = "full-course-native-H-rays-and-contact-no-flight"
DIRECTIONS = {"front", "back", "left", "right"}


def probe_scene(index, *, activity=None):
    course = reference_course(index) if activity is None else progression_course(activity, index)
    text = static_course_world(course)
    corners = 2 * len(course.route.corners)
    count = corners + 4 + 3 * course.count
    if (text.count('controller "<none>"') != 1 or
            text.count('window "<none>"') != 1 or
            text.count("DEF GP_V2_L_") != corners or
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
    if course.progression is not None and course.progression[0] == 5:
        memory = result.get("a5_memory")
        if type(memory) is not dict or set(memory) != {"at_turn", "at_choice"}:
            raise RuntimeError("missing A5 native memory evidence")
        at_turn, at_choice = memory["at_turn"], memory["at_choice"]
        detected, clear = ("right", "left") if course.route.turns == ("G",) else ("left", "right")
        if (not _rays(at_turn) or not .20 < at_turn[detected] < .35 or
                at_turn[clear] < 1.999):
            raise RuntimeError("A5 turn cue not visible from the native lateral rays")
        if (type(at_choice) is not list or len(at_choice) != 3 or
                any(not _rays(rays) or rays["back"] < 1.999 or
                    not .07 < rays["front"] < .30 for rays in at_choice)):
            raise RuntimeError("A5 terminal range exposes the turn cue or misses the terminal H")
    if course.progression is not None and course.progression[0] == 6:
        check_a6_discrimination(result.get("a6_discrimination"), bool(course.gates))


def check_a6_discrimination(data, has_open_h):
    expected = {"start", "closed", "open", "after"} if has_open_h else {"start", "closed"}
    if type(data) is not dict or set(data) != expected:
        raise RuntimeError("missing or noncanonical A6 native rays")
    first = data["start"]
    # 25-mm measured margin at the nominal aligned 0.75 m pose. This
    # stopped-vehicle witness says nothing about the pilot's takeoff error.
    limit = 1.25 if has_open_h else 1.975
    if not _rays(first) or not .10 < first["front"] < limit:
        raise RuntimeError("A6 first obstacle not visible with the expected frontal margin")
    if has_open_h:
        opened, after = data["open"], data["after"]
        if (not _rays(opened) or not _rays(after) or
                not all(.20 < opened[d] < .35 for d in ("left", "right")) or
                not .50 < after["front"] < 1.50):
            raise RuntimeError("A6 open-H side rays or post-traversal frontal ray missing")
    closed = data["closed"]
    if type(closed) is not list or len(closed) != 3 or not all(map(_rays, closed)):
        raise RuntimeError("A6 terminal counterexamples missing")
    for rays, pattern in zip(closed, ((True, False), (False, False), (False, True))):
        if (not .10 < rays["front"] < .40 or
                tuple(.20 < rays[d] < .35 for d in ("left", "right")) != pattern or
                any(rays[d] < 1.999 for d, close in zip(("left", "right"), pattern) if not close)):
            raise RuntimeError("A6 one-sided terminal H counterexample missing")


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

    # In addition to the beam/panel proof above, each real upright must
    # remain physically solid. Both lateral posts of each present gate are
    # required; neither the centreline nor an unrelated collider may qualify.
    posts = {box.name: box for box in open_h_boxes(course)}
    expected = [posts[f"GP_V2_H_{gate.leg_index}_{part}"]
                for gate in course.gates for part in ("LEFT", "RIGHT")]
    records = result.get("post_witnesses")
    if type(records) is not list or len(records) != len(expected):
        raise RuntimeError("missing native open-H upright evidence")
    for box, record in zip(expected, records):
        if (type(record) is not dict or set(record) !=
                {"target", "target_node_id", "free", "collision"} or
                record["target"] != box.name or
                type(record["target_node_id"]) is not int or
                record["target_node_id"] <= 0 or
                record["target_node_id"] in used_ids):
            raise RuntimeError("wrong native open-H upright identity")
        used_ids.add(record["target_node_id"])
        reciprocal = False
        for phase in ("free", "collision"):
            observations = record[phase]
            if type(observations) is not list or len(observations) != 3:
                raise RuntimeError("incomplete native open-H upright phase")
            for sample in observations:
                if (type(sample) is not dict or set(sample) !=
                        {"time_ms", "contacts", "target_contacts"} or
                        type(sample["time_ms"]) is not int or
                        sample["time_ms"] <= last_ms or sample["time_ms"] % 8 or
                        type(sample["contacts"]) is not list or
                        type(sample["target_contacts"]) is not list or
                        len(sample["contacts"]) > 2048 or
                        len(sample["target_contacts"]) > 2048):
                    raise RuntimeError("stale or malformed native upright tick")
                last_ms = sample["time_ms"]
                for point in sample["contacts"] + sample["target_contacts"]:
                    if (type(point) is not dict or set(point) !=
                            {"point", "node_id"} or
                            type(point["node_id"]) is not int or
                            not -(2**31) <= point["node_id"] < 2**31 or
                            type(point["point"]) is not list or
                            len(point["point"]) != 3 or
                            any(type(value) not in (int, float) or
                                not math.isfinite(value)
                                for value in point["point"])):
                        raise RuntimeError("invalid native upright contact point")
                if phase == "free":
                    if sample["contacts"] or sample["target_contacts"]:
                        raise RuntimeError("native upright centre passage not free")
                    continue
                for point in sample["target_contacts"]:
                    if point["node_id"] != record["target_node_id"]:
                        raise RuntimeError("native upright Solid contact ID mismatch")
                    xyz = point["point"]
                    if (abs(xyz[0] - box.x) > box.sx / 2 + .002 or
                            abs(xyz[1] - box.y) > box.sy / 2 + .002 or
                            abs(xyz[2] - box.z) > box.sz / 2 + .002):
                        raise RuntimeError("native upright contact outside Box")
                    if any(math.dist(xyz, own["point"]) <= 1e-6
                           for own in sample["contacts"]):
                        reciprocal = True
        if not reciprocal:
            raise RuntimeError("reciprocal native open-H upright contact absent")


def native_run(home, indexes, *, output_root=None, activity=None):
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
        course = reference_course(index) if activity is None else progression_course(activity, index)
        case = invocation / f"{position:02d}-{course.identifier}"
        case.mkdir()
        source = probe_scene(index, activity=activity)
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
        env.pop("GP_V2_H_NATIVE_ACTIVITY", None)
        if activity is not None:
            env["GP_V2_H_NATIVE_ACTIVITY"] = str(activity)
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
            print("PASS native H rays, passage and beam/panel/upright contacts (not flight) " +
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
    parser.add_argument("--activity", type=int, choices=range(1, 8),
                        help="check a progression activity using its one-based --index")
    args = parser.parse_args(argv)
    if not args.native:
        parser.error("--native required: static checks are never a sensor PASS")
    if args.all_12 and args.index:
        parser.error("--all-12 cannot be combined with --index")
    if args.activity is not None and (args.all_12 or not args.index):
        parser.error("--activity requires at least one --index and excludes --all-12")
    indices = tuple(range(12)) if args.all_12 else (
        tuple(args.index) if args.index else DEFAULT_INDICES)
    for index in indices:
        if args.activity is None:
            reference_course(index)
        else:
            progression_course(args.activity, index)
    home = os.environ.get("WEBOTS_HOME")
    if not home:
        parser.error("WEBOTS_HOME must point to isolated Webots R2025a")
    native_run(Path(home), indices, activity=args.activity)


if __name__ == "__main__":
    main()
