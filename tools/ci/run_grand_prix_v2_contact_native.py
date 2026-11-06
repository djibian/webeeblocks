#!/usr/bin/env python3
"""Strict Webots R2025a contact witness for #825, never flight PASS.

No synthetic success, no pooled result files, no motorized commands. Requires
reciprocal vehicle/L contact points after forced overlap in the full course.
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
from tools.grand_prix.route_solid_v2 import corner_boxes, HEIGHT

CLAIM = "full-course-native-L-contact-teleport-no-flight"
DEFAULT_INDICES = (0, 5, 6, 11)
# Kept inside the existing required geometry job's always-uploaded artifact.
OUT = ROOT / "ci-artifacts/grand-prix-u-geometry/route-contact-native"


def probe_scene(index):
    course = reference_course(index)
    scene = static_course_world(course)
    if (scene.count('controller "<none>"') != 1 or
            scene.count('window "<none>"') != 1 or
            scene.count("DEF GP_V2_L_") != 4 or
            scene.count("DEF GP_V2_H_") != 3 * course.count or
            scene.count("DEF GP_V2_FINAL_") != 4 or
            scene.count("boundingObject Box { size ") != 8 + 3 * course.count or
            "GP_ROUTE_EVALUATOR" in scene or "controllerArgs" in scene or
            'controller "grand_prix_route_flight"' in scene):
        raise RuntimeError("refusing noncanonical/in-flight native contact scene")
    return scene.replace('controller "<none>"',
                         'controller "grand_prix_v2_contact_probe"', 1)


def _check_arm(record, course, arm_index):
    target = corner_boxes(course.route)[arm_index]
    if (type(record) is not dict or record.get("claim") != CLAIM or
            record.get("configuration") != course.identifier or
            record.get("webots") != "R2025a" or
            record.get("timestep_ms") != 8 or
            record.get("source") != "Robot.getContactPoints(includeDescendants=True)" or
            record.get("target_source") != "Solid.getContactPoints(includeDescendants=False)" or
            record.get("target") != target.name):
        raise RuntimeError("native L contact witness identity mismatch")
    target_id = record.get("target_node_id")
    if type(target_id) is not int or target_id <= 0:
        raise RuntimeError("invalid native target ID")
    previous = -1
    seen_hit = False
    for phase in ("free", "collision"):
        observations = record.get(phase)
        if type(observations) is not list or len(observations) != 3:
            raise RuntimeError("incomplete native contact acquisition")
        for item in observations:
            if type(item) is not dict or set(item) != {"time_ms", "contacts", "target_contacts"}:
                raise RuntimeError("noncanonical native contact sample")
            clock, contacts = item["time_ms"], item["contacts"]
            target_contacts = item["target_contacts"]
            if (type(clock) is not int or clock <= previous or clock % 8 or
                    type(contacts) is not list or len(contacts) > 2048 or
                    type(target_contacts) is not list or len(target_contacts) > 2048):
                raise RuntimeError("stale/invalid native contact clock or collection")
            previous = clock
            for point in contacts + target_contacts:
                if (type(point) is not dict or set(point) != {"node_id", "point"} or
                        type(point["node_id"]) is not int or
                        not -(2**31) <= point["node_id"] < 2**31 or
                        type(point["point"]) is not list or len(point["point"]) != 3 or
                        any(type(v) not in (int, float) or not math.isfinite(v)
                            for v in point["point"])):
                    raise RuntimeError("invalid native contact value")
            for point in target_contacts:
                if point["node_id"] != target_id:
                    raise RuntimeError("target contact ID differs from queried Solid")
                if (abs(point["point"][0] - target.x) > target.sx / 2 + .002 or
                        abs(point["point"][1] - target.y) > target.sy / 2 + .002 or
                        abs(point["point"][2] - HEIGHT / 2) > HEIGHT / 2 + .002):
                    raise RuntimeError("native contact unrelated to target location")
                if any(math.dist(point["point"], own["point"]) <= 1e-6
                       for own in contacts):
                    seen_hit = True
            if phase == "free" and (contacts or target_contacts):
                raise RuntimeError("native contact at free-space baseline")
    if not seen_hit:
        raise RuntimeError("reciprocal real L contact not observed")


def check_native(record, course):
    """Falsify all four L-arm contacts in the same native course invocation.

    The first corner retains its established top-level and additional-arm proof.
    The other corner must contribute two further independent, chronologically
    fresh, reciprocal Solid/vehicle witnesses. No test-only contact is minted.
    """
    if type(record) is not dict:
        raise RuntimeError("missing native L contact record")
    extra = record.get("additional")
    second = record.get("second_corner")
    if (type(extra) is not dict or
            set(extra) != {"target", "target_node_id", "free", "collision"} or
            type(second) is not list or len(second) != 2 or
            any(type(item) is not dict or
                set(item) != {"target", "target_node_id", "free", "collision"}
                for item in second)):
        raise RuntimeError("incomplete four-arm native L contact witness")
    witnesses = (record, extra, *second)
    identities = set()
    last_time = -1
    for arm_index, item in enumerate(witnesses):
        # The arm-specific verifier checks all real samples, the exact
        # canonical Solid name, own node ID, position, reciprocal point and
        # three independent collision/free observations.
        _check_arm({**record, **item}, course, arm_index)
        identity = item["target_node_id"]
        if identity in identities:
            raise RuntimeError("native L arms share collider identity")
        identities.add(identity)
        if item["free"][0]["time_ms"] <= last_time:
            raise RuntimeError("stale or interleaved L-arm native contact clock")
        last_time = item["collision"][-1]["time_ms"]
    if len(identities) != 4:
        raise RuntimeError("incomplete L collider identity coverage")


def native_run(home, indexes):
    OUT.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="invocation-", dir=OUT)).resolve()
    # Docker runs as root while Actions uploads from the host uid. Preserve
    # native failure logs as readable evidence without altering validation.
    folder.chmod(0o755)
    print("GP_V2_CONTACT_NATIVE_RUN_DIR " + str(folder), flush=True)
    version = home / "resources/version.txt"
    executable = home / "webots"
    if (not version.is_file() or version.read_text().strip() != "R2025a" or
            not executable.is_file() or not os.access(executable, os.X_OK)):
        raise RuntimeError("complete Webots R2025a required")
    results = []
    for position, index in enumerate(indexes):
        course = reference_course(index)
        case = folder / f"{position:02d}-{course.identifier}"
        case.mkdir()
        scene = probe_scene(index)
        with tempfile.NamedTemporaryFile(
                mode="w", prefix="ci_gp_v2_contact_", suffix=".wbt",
                dir=ROOT / "worlds", encoding="utf-8", delete=False) as target:
            target.write(scene)
            world = Path(target.name)
        evidence = case / "native.json"
        log = case / "native.log"
        env = dict(os.environ, WEBOTS_HOME=str(home),
                   GP_V2_CONTACT_INDEX=str(index), GP_V2_CONTACT_OUT=str(evidence),
                   LIBGL_ALWAYS_SOFTWARE="true",
                   WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE="true")
        process = None
        try:
            with log.open("w") as stream:
                process = subprocess.Popen(
                    [str(executable), "--stdout", "--stderr", "--batch",
                     "--mode=fast", "--minimize", str(world)],
                    cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
                status = process.wait(timeout=120)
            output = log.read_text(errors="replace")
            if (status != 0 or "Traceback (most recent call last)" in output or
                    any(line.startswith("ERROR:") for line in output.splitlines())):
                raise RuntimeError("native contact Webots failure (exit=" +
                                   str(status) + "): " + str(log))
            if not evidence.is_file():
                raise RuntimeError("missing native contact output")
            data = evidence.read_bytes()
            record = json.loads(data)
            check_native(record, course)
            witness = "GP_V2_CONTACT_NATIVE " + json.dumps(
                record, sort_keys=True, allow_nan=False)
            if output.splitlines().count(witness) != 1:
                raise RuntimeError("native JSON and stdout contact evidence disagree")
            results.append(dict(configuration=course.identifier,
                                world_sha256=hashlib.sha256(scene.encode()).hexdigest(),
                                evidence_file=str(evidence.relative_to(folder)),
                                evidence_sha256=hashlib.sha256(data).hexdigest()))
            print("PASS bounded native four-arm L-contact witness (not mission/flight) " +
                  course.identifier, flush=True)
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            world.unlink(missing_ok=True)
            world.with_name("." + world.stem + ".wbproj").unlink(missing_ok=True)
    summary = dict(claim=CLAIM, invocation=folder.name, webots="R2025a",
                   results=results)
    with tempfile.NamedTemporaryFile(
            mode="w", prefix=".summary-", suffix=".tmp",
            dir=folder, encoding="utf-8", delete=False) as target:
        pending = Path(target.name)
        target.write(json.dumps(summary, indent=2) + "\n")
    # NamedTemporaryFile defaults to 0600 under root in the R2025a container.
    # The exact atomic summary must also be readable by the artifact uploader.
    pending.chmod(0o644)
    try:
        os.replace(pending, folder / "summary.json")
    finally:
        pending.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="R2025a contact témoin natif, SANS VOL NI ADMISSION")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--index", action="append", type=int, default=[])
    parser.add_argument("--all-12", action="store_true")
    args = parser.parse_args(argv)
    if not args.native:
        parser.error("--native mandatory: no synthetic contact PASS")
    if args.all_12 and args.index:
        parser.error("--all-12 and --index cannot be combined")
    indexes = (tuple(range(12)) if args.all_12 else
               tuple(args.index) if args.index else DEFAULT_INDICES)
    for index in indexes:
        reference_course(index)
    home = os.environ.get("WEBOTS_HOME")
    if not home:
        parser.error("WEBOTS_HOME must be an isolated official R2025a installation")
    native_run(Path(home), indexes)


if __name__ == "__main__":
    main()
