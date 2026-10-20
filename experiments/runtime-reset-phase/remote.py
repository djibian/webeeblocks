#!/usr/bin/env python3
"""Bounded #637 acquisition/byte verification. Never a CI Gate or health verdict."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/ci"))
sys.path.insert(0, str(HERE))
from analyze import fields, summarize
from instrument import instrument
from tools.ci import run_progression_autonomous_mission as runner

OUT = ROOT / "ci-artifacts/reset637-variability"
ORIGINAL_HEAD = "635343ebc9f715c3deff894889d6309c84acac9f"
REPOSITORY = "djibian/webeeblocks"


def emit(label, value):
    print(label + " " + json.dumps(value, sort_keys=True, allow_nan=False), flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def child_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("unsafe artifact/manifest path")
    return root.joinpath(*path.parts)


def verify_manifest(directory):
    manifest = json.loads((directory / "sha256.json").read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("missing/empty manifest")
    for name, expected in manifest.items():
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError("malformed digest")
        if digest(child_path(directory, name)) != expected:
            raise ValueError("byte mismatch: " + name)
    return len(manifest)


def compare(directory, summary):
    native = {round(row["time"], 9): row for row in
              map(json.loads, (directory / "native-reset-state.jsonl").read_text().splitlines()[1:])}
    beginnings, samples = {}, {}
    for line in (directory / "webots.log").read_text().splitlines():
        if " RESET_PHASE_BEGIN " in line:
            row = fields(line)
            beginnings[int(row["id"])] = row
        elif " RESET_PHASE_SAMPLE " in line:
            row = fields(line)
            samples.setdefault(int(row["id"]), []).append(row)
    results = []
    for case in summary["resets"]:
        identity = case["id"]
        origin = beginnings[identity]
        result = {"id": identity, "receipt_time": case["begin_time"],
                  "terminal": case["terminal"], "elapsed": case["last_sample_elapsed"],
                  "receipt_sample": samples[identity][0], "compared": 0,
                  "runtime_false_native_true": [], "runtime_true_native_false": [],
                  "max_position_error": 0.0, "max_velocity_error": 0.0, "max_gyro_error": 0.0}
        for row in samples[identity]:
            if row["elapsed"] < .064 - 1e-8:
                continue
            n = native.get(round(row["time"], 9))
            if n is None:
                raise ValueError("missing native timestamp")
            matrix, velocity = n["orientation"], n["velocity"]
            rpy = [math.atan2(matrix[7], matrix[8]),
                   math.atan2(-matrix[6], math.hypot(matrix[7], matrix[8])),
                   math.atan2(matrix[3], matrix[0])]
            gyro = [sum(matrix[k * 3 + i] * velocity[3 + k] for k in range(3)) for i in range(3)]
            pose = (all(abs(a-b) < tol for a,b,tol in
                        zip(n["position"], origin["origin"], (.03, .03, .05)))
                    and all(abs(a-b) < math.pi/90 for a,b in zip(rpy[:2], origin["origin_rpy"][:2]))
                    and abs(math.remainder(rpy[2]-origin["origin_rpy"][2], 2*math.pi)) < math.pi/90)
            motion = math.hypot(*velocity[:2]) < .12 and abs(velocity[2]) < .15 and abs(gyro[2]) < .10
            internal = bool(row["pose_ready"] and row["motion_ready"])
            physical = pose and motion
            if not internal and physical:
                result["runtime_false_native_true"].append(row["elapsed"])
            if internal and not physical:
                result["runtime_true_native_false"].append(row["elapsed"])
            for label, values, other in (("position", row["position"], n["position"]),
                                         ("velocity", row["velocity"], velocity[:3]),
                                         ("gyro", row["gyro"], gyro)):
                result["max_" + label + "_error"] = max(result["max_" + label + "_error"],
                                                         max(abs(a-b) for a,b in zip(values, other)))
            result["compared"] += 1
        results.append(result)
        if case["terminal"].endswith("ERR RESET_TIMEOUT"):
            # Archive contains the entire acquisition. Also expose the complete
            # failing RESET and one preceding second through readable Actions logs.
            for row in samples[identity]:
                emit("FAILED_INTERNAL_SAMPLE", row)
            for t, row in sorted(native.items()):
                if origin["time"] - 1 <= t <= origin["time"] + case["last_sample_elapsed"] + .064:
                    emit("FAILED_NATIVE_SAMPLE", row)
    return {"scope": "aligned observations after +64ms; timestamp equality is not read simultaneity",
            "resets": results}


def analyze(directory, require_success, expected_head=None):
    count = verify_manifest(directory)
    original = (directory / "runtime-original.c").read_bytes()
    modified = (directory / "runtime-instrumented.c").read_bytes()
    if instrument(original.decode()).encode() != modified:
        raise ValueError("not the original two-print-only transform")
    provenance = json.loads((directory / "reset-phase-provenance.json").read_text())
    if expected_head is not None and provenance["git_head"] != expected_head:
        raise ValueError("candidate HEAD differs from acquisition provenance")
    if provenance["image"] != runner.WEBOTS_IMAGE:
        raise ValueError("unexpected Webots image")
    if provenance["defer_steps"] != 0 or provenance["source_restored"] is not True:
        raise ValueError("delayed receiver or unrestored source")
    if provenance["sha256"]["runtime-original.c"] != hashlib.sha256(original).hexdigest():
        raise ValueError("original source identity mismatch")
    if provenance["sha256"]["runtime-instrumented.c"] != hashlib.sha256(modified).hexdigest():
        raise ValueError("instrumented source identity mismatch")
    summary = summarize((directory / "webots.log").read_text())
    if summary != json.loads((directory / "reset-phase-summary.json").read_text()):
        raise ValueError("phase summary differs from raw samples")
    if require_success:
        if len(summary["resets"]) != 14 or any(not r["terminal"].endswith(" OK") for r in summary["resets"]):
            raise ValueError("not fourteen strict accepted RESETs")
        runner.validate_observer_trace(directory / "native-reset-state.jsonl", required_attempts=(7, 8))
    comparison = compare(directory, summary)
    report = {"files_verified": count, "provenance": provenance, "summary": summary, "comparison": comparison}
    emit("BYTE_VERIFIED_ANALYSIS", report)
    return report


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        target = super().redirect_request(request, response, code, message, headers, new_url)
        if target is not None:
            for name in list(target.headers):
                if name.lower() == "authorization":
                    target.remove_header(name)
        return target


def download_and_verify(artifact, expected, head, run_id, directory):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    token = os.environ["GITHUB_TOKEN"]
    api = "https://api.github.com/repos/" + REPOSITORY + "/actions/artifacts/" + str(artifact)
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=60) as response:
        metadata = json.load(response)
    if (metadata["id"] != artifact or metadata["expired"]
            or metadata["workflow_run"]["head_sha"] != head
            or metadata["workflow_run"]["id"] != run_id
            or metadata["digest"] != "sha256:" + expected):
        raise ValueError("artifact provenance/digest mismatch")
    opener = urllib.request.build_opener(SafeRedirect())
    with opener.open(urllib.request.Request(api + "/zip", headers=headers), timeout=120) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("downloaded ZIP digest mismatch")
    archive = directory / "downloaded.zip"
    archive.write_bytes(payload)
    unpacked = directory / "payload"
    unpacked.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = child_path(unpacked, member.filename)
            if member.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("artifact symlink refused")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(bundle.read(member))
    phase_directories = sorted({p.parent for p in unpacked.rglob("reset-phase-provenance.json")})
    outer_manifests = [p for p in unpacked.rglob("sha256.json")
                       if p.parent not in phase_directories and (p.parent / "campaign.json").exists()]
    for manifest in outer_manifests:
        verify_manifest(manifest.parent)
    if not phase_directories and not outer_manifests:
        raise ValueError("no internal acquisition or manifested stopped campaign in ZIP")
    reports = []
    for path in phase_directories:
        outer_result = path / "outer-result.json"
        if outer_result.exists():
            code = json.loads(outer_result.read_text())["effective_exit"]
        else:
            code = int((path / "exit-code.txt").read_text()) if (path / "exit-code.txt").exists() else 1
        # Byte verification remains mandatory for successful and failed cases.
        try:
            reports.append(analyze(path, code == 0, head))
        except Exception as exc:
            if code == 0:
                raise
            emit("FAILED_ACQUISITION_ANALYSIS_UNPROVEN", {"path": str(path), "error": str(exc)})
            reports.append({"status": "UNPROVEN", "error": str(exc), "files_verified": verify_manifest(path)})
    report = {"artifact": artifact, "zip_sha256": expected, "metadata": metadata,
              "phase_acquisitions": len(reports), "outer_manifests": len(outer_manifests)}
    write_json(directory / "verification.json", report)
    emit("DOWNLOADED_ZIP_VERIFIED", report)


def acquire(count, cpu_limit=None):
    if (count, cpu_limit) not in ((8, None), (1, 1.0)):
        raise ValueError("only preregistered eight baseline trials or one CPU=1 trial")
    OUT.mkdir(parents=True, exist_ok=False)
    configuration = {"question": ("CPU quota influence on original browser RESET receipt phase" if cpu_limit else
                                  "variability of unchanged native browser path, first actual refusal"),
                     "native_cpu_limit": cpu_limit,
                     "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                     "source_candidate": ORIGINAL_HEAD, "planned": count, "started": [],
                     "stop_rule": "first refusal/preparation error, otherwise exactly " + str(count) + "; no retry",
                     "defer_steps": 0, "scope": "diagnostic-only; never repair or main-health"}
    write_json(OUT / "campaign.json", configuration)
    shutil.copyfile(__file__, OUT / "executed-remote.py")
    shutil.copyfile(HERE / ("CPU_PROTOCOL.md" if cpu_limit else "VARIABILITY_PROTOCOL.md"), OUT / "EXECUTED_PROTOCOL.md")
    shutil.copyfile(ROOT / ".github/workflows/reset637-variability.yml", OUT / "executed-workflow.yml")
    (OUT / "cpuinfo.txt").write_text(Path("/proc/cpuinfo").read_text())
    original_c = (ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c").read_bytes()
    old_run = subprocess.run
    old_env = {key: os.environ.get(key) for key in
               ("WEBEEBLOCKS_RESET_PHASE_TRACE", "WEBEEBLOCKS_RESET_PHASE_DEFER_STEPS")}
    os.environ.update(WEBEEBLOCKS_RESET_PHASE_TRACE="1", WEBEEBLOCKS_RESET_PHASE_DEFER_STEPS="0")
    try:
        for trial in range(1, count + 1):
            configuration["started"].append(trial)
            write_json(OUT / "campaign.json", configuration)
            emit("TRIAL_START", {"trial": trial, "head": configuration["head"]})
            preparation_captures = []
            def measured_run(*args, **kwargs):
                arguments = list(args)
                command = arguments[0] if arguments else kwargs.get("args")
                anchor = "DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/google-chrome.deb >/dev/null"
                if isinstance(command, list) and command and command[0] == "docker" and anchor in command[-1]:
                    if command[-1].count(anchor) != 1:
                        raise ValueError("ambiguous Chrome preparation anchor")
                    before = command[-1]
                    after = before.replace(anchor, anchor + "\n"
                        "google-chrome --version > /workspace/ci-artifacts/progression-autonomous-mission/browser-version.txt\n"
                        "sha256sum /tmp/google-chrome.deb /opt/google/chrome/chrome > /workspace/ci-artifacts/progression-autonomous-mission/browser-sha256.txt")
                    if cpu_limit:
                        after += "\n" if not after.endswith("\n") else ""
                        # Insert before Webots starts; this branch requires cgroup v2 evidence.
                        after = after.replace(anchor, anchor + "\ncat /sys/fs/cgroup/cpu.max > /workspace/ci-artifacts/progression-autonomous-mission/native-cpu-max.txt", 1)
                    (runner.ARTIFACT_ROOT / "browser-command-original.sh").write_text(before)
                    (runner.ARTIFACT_ROOT / "browser-command-measured.sh").write_text(after)
                    preparation_captures.append(1)
                    command = [*command[:-1], after]
                    if cpu_limit:
                        if command[1] != "run":
                            raise ValueError("not the native Docker run")
                        command = [*command[:2], "--cpus=" + str(cpu_limit), *command[2:]]
                    (runner.ARTIFACT_ROOT / "native-docker-command.json").write_text(json.dumps(command, indent=2) + "\n")
                    if arguments:
                        arguments[0] = command
                    else:
                        kwargs["args"] = command
                return old_run(*arguments, **kwargs)
            status, exception = 1, None
            subprocess.run = measured_run
            try:
                status = runner.main()
            except Exception as exc:
                exception = repr(exc)
            finally:
                subprocess.run = old_run
            destination = OUT / ("trial-%02d" % trial)
            if runner.ARTIFACT_ROOT.exists():
                shutil.move(str(runner.ARTIFACT_ROOT), destination)
            else:
                destination.mkdir()
            result = {"trial": trial, "exit": status, "exception": exception,
                      "browser_preparation_captures": len(preparation_captures),
                      "source_restored": (ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c").read_bytes() == original_c}
            if (destination / "browser-version.txt").exists():
                result["browser_version"] = (destination / "browser-version.txt").read_text().strip()
                result["browser_sha256"] = (destination / "browser-sha256.txt").read_text().splitlines()
            # These outer result/analysis files are covered by the campaign manifest,
            # not retroactively inserted into the original acquisition manifest.
            try:
                if cpu_limit:
                    quota = (destination / "native-cpu-max.txt").read_text().split()
                    if len(quota) != 2 or quota[0] == "max" or abs(int(quota[0]) / int(quota[1]) - cpu_limit) > 1e-9:
                        raise ValueError("actual native cgroup CPU quota not established")
                    result["native_cpu_max"] = quota
                report = analyze(destination, status == 0, configuration["head"])
                write_json(destination / "recalculated-analysis.json", report)
                if status == 0 and len(preparation_captures) != 1:
                    raise ValueError("actual Chrome identity not captured")
            except Exception as exc:
                result["analysis_error"] = repr(exc)
                status = 1
            if not result["source_restored"]:
                status = 1
            result["effective_exit"] = status
            write_json(destination / "outer-result.json", result)
            emit("TRIAL_END", result)
            configuration["last_result"] = result
            write_json(OUT / "campaign.json", configuration)
            if status:
                configuration["stopped"] = "first refusal or preparation/verification error"
                write_json(OUT / "campaign.json", configuration)
                return 1
        configuration["stopped"] = str(count) + " trials completed; no disappearance/health claim"
        write_json(OUT / "campaign.json", configuration)
        return 0
    finally:
        subprocess.run = old_run
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        write_json(OUT / "sha256.json", {str(p.relative_to(OUT)): digest(p)
                   for p in OUT.rglob("*") if p.is_file() and p != OUT / "sha256.json"})


def self_test():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "sample").write_bytes(b"native evidence\n")
        write_json(root / "sha256.json", {"sample": digest(root / "sample")})
        assert verify_manifest(root) == 1
        (root / "sample").write_bytes(b"changed")
        try:
            verify_manifest(root)
        except ValueError:
            pass
        else:
            raise AssertionError("changed bytes accepted")
        for bad in ("../escape", "/absolute", "a/../../escape", "a\\b"):
            try:
                child_path(root, bad)
            except ValueError:
                pass
            else:
                raise AssertionError("unsafe path accepted")
        request = urllib.request.Request("https://api.github.com/test", headers={"Authorization": "Bearer sentinel"})
        redirected = SafeRedirect().redirect_request(request, None, 302, "Found", {},
                                                      "https://example.invalid/signed")
        assert not any(k.lower() == "authorization" for k in redirected.headers)
    emit("REMOTE_VERIFIER_SELF_TEST", {"modified_bytes": "refused", "unsafe_paths": "refused",
                                      "redirect_credentials": "removed"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    run = sub.add_parser("run")
    run.add_argument("--count", type=int, required=True)
    run.add_argument("--cpu-limit", type=float, choices=(1.0,))
    verify = sub.add_parser("verify")
    verify.add_argument("--artifact", type=int, required=True)
    verify.add_argument("--sha256", required=True)
    verify.add_argument("--head", required=True)
    verify.add_argument("--run", type=int, required=True)
    verify.add_argument("--directory", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "self-test":
        self_test()
        return 0
    if arguments.command == "run":
        return acquire(arguments.count, arguments.cpu_limit)
    download_and_verify(arguments.artifact, arguments.sha256, arguments.head, arguments.run, arguments.directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
