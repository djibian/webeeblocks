"""Fail-closed, outside-simulation evidence envelope for #637 autonomous RESETs.

This module does not control Webots, classify an oracle, or infer a physical
root cause. A digest describes observed bytes, not an exact ODE replay.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

SCHEMA = "webeeblocks-autonomous-incident-p1-v1"
RUN_KEYS = ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB",
            "GITHUB_SHA", "GITHUB_REF", "GITHUB_HEAD_REF")
EVIDENCE = ("world.wbt", "native-host.log", "webots.log", "browser-events.jsonl",
            "native-reset-state.jsonl", "native-reset-summary.json",
            "reset-phase-summary.json", "reset-post-teleport.json",
            "normal-quit.json", "exit-code.txt")


def _describe(path):
    """Hash existing bytes; 'unknown' always remains explicit."""
    path = Path(path)
    try:
        digest = hashlib.sha256()
        size = 0
        tail = b""
        with path.open("rb") as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
                size += len(block)
                tail = block[-1:]
        result = {"status": "available", "size": size, "sha256": digest.hexdigest()}
        if path.suffix == ".jsonl":
            result["newline_terminated"] = tail == b"\n"
        return result
    except OSError as exc:
        return {"status": "unknown", "reason": type(exc).__name__}


def _exclusive_json(path, payload):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def checkout_head(root):
    """The worktree identity is recorded separately from GitHub event SHA."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
            stderr=subprocess.DEVNULL).strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def record_prelaunch(directory, *, image, command, inner_script, input_files, head):
    """Persist expected inputs and explicit unknowns before the long native run."""
    directory = Path(directory)
    if not directory.is_dir() or not isinstance(command, list) or not command:
        raise ValueError("invalid autonomous incident launch envelope")
    payload = {
        "schema": SCHEMA, "phase": "before-native-launch",
        "git_checkout_head": head or "unknown",
        "github": {key: os.environ.get(key) or "unknown" for key in RUN_KEYS},
        "webots_image_requested": image,
        "webots_image_loaded": "unknown",
        "webots_bin_and_libode_mappings": "unknown",
        "command": command,
        "inner_script": inner_script,
        "inner_script_sha256": hashlib.sha256(inner_script.encode("utf-8")).hexdigest(),
        "inputs": {name: {"path": str(Path(path).resolve()), **_describe(path)}
                   for name, path in sorted(input_files.items())},
        "native_result": "unobserved",
        "causal_attribution": "UNPROVEN",
    }
    _exclusive_json(directory / "incident-provenance.json", payload)
    return payload


def run_host_streamed(command, log_path, *, cwd, env):
    """Keep Docker/Xvfb stdout on disk even when subprocess.run raises."""
    with Path(log_path).open("xb") as stream:
        return subprocess.run(command, cwd=cwd, env=env, check=False,
                              stdout=stream, stderr=subprocess.STDOUT)


def record_completion(directory, *, docker_returncode):
    """Post-run capture inventory, strictly distinct from mission success."""
    directory = Path(directory)
    report_path = directory / "normal-quit.json"
    native = {"status": "unknown"}
    try:
        decoded = json.loads(report_path.read_text(encoding="utf-8"))
        if isinstance(decoded, dict):
            native = {
                "status": "observed",
                "normal_success_reported": decoded.get("normal_success", "unknown"),
                "native_exit_code_reported": decoded.get("native_exit_code", "unknown"),
                "stdout_eof_reported": decoded.get("stdout_eof", "unknown"),
                "failure_log_capture": decoded.get("failure_log_capture", "unknown"),
                "fallback_used": decoded.get("fallback_used", "unknown"),
            }
    except (OSError, UnicodeError, ValueError):
        pass
    envelope = {
        "schema": SCHEMA, "phase": "after-native-run",
        "docker_returncode": docker_returncode if type(docker_returncode) is int else "unknown",
        "native_report": native,
        "files": {name: _describe(directory / name) for name in EVIDENCE},
        "seal": "observed_bytes_only_not_complete_state",
        "oracle_verdict": "not_assigned_by_diagnostics",
        "causal_attribution": "UNPROVEN",
    }
    _exclusive_json(directory / "incident-capture.json", envelope)
    return envelope
