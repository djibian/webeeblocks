"""Strict, source-independent verifier for native R2025a PAUSE/RESUME evidence.

This does not control Webots. It consumes the isolated supervisor's fsync'd
controller-sidecar plus its earlier WWI/PAUSE stdout attestations. Neither the
presence of NATIVE_PASS nor a Webots exit=0 alone can qualify a test.
"""
import json
import math
from pathlib import Path
import re


SCHEMA = "webeeblocks-webots-pause-controller-sidecar-v1"
STAGES = (
    "CONTROLLER_ENTRY", "SUPERVISOR_CONSTRUCTED", "BEFORE_STEP_32",
    "AFTER_STEP_32", "SIMULATED_TIME_AFTER_STEP_32", "NATIVE_PASS",
    "PYTHON_ATEXIT",
)
REQUIRED_CONSOLE = (
    "CONTROLLER_START", "READY_SENT", "BEGIN_RECEIVED",
    "PAUSE_REQUESTED", "PAUSE_ATTESTED", "RESUME_RECEIVED",
    "MODE_REALTIME_REQUESTED", "MODE_REALTIME_CALL_RETURNED",
    "STEP_ZERO_AFTER_RESUME_REQUESTED", "STEP_ZERO_AFTER_RESUME_RETURNED",
    "MODE_REALTIME_ATTESTED", "STEP_32_AFTER_RESUME_REQUESTED",
)
PROOF_FIELDS = {
    "schema", "simulated_frozen_ms", "frozen_delta_ms", "pause_wall_seconds",
    "resumed_simulated_ms", "resume_via_robot_window_wwi",
    "wrong_token_rejected", "steps_while_paused", "simulation",
}


def _reject_duplicate_keys(items):
    value = {}
    for name, content in items:
        if name in value:
            raise ValueError("duplicate JSON key: " + name)
        value[name] = content
    return value


def _exact_integer(value, low=None, high=None):
    if type(value) is not int:
        return False
    return (low is None or value >= low) and (high is None or value <= high)


def _one_match(pattern, lines, label):
    matches = []
    for line in lines:
        match = re.fullmatch(pattern, line)
        if match:
            matches.append(match)
    if len(matches) != 1:
        raise ValueError("missing/duplicate native console attestation: " + label)
    return matches[0]


def verify_native_pause_evidence(sidecar_path, stdout, browser_text, webots_code):
    """Return original native JSON proof, or reject any missing/ambiguous step.

    The test runner calls this only after its external 45 s timeout check.
    The browser must have launched the actual isolated Robot Window.
    """
    if webots_code != 0:
        raise ValueError("Webots did not exit normally")
    if "BROWSER_LAUNCHED args=" not in browser_text or (
        "/robot_windows/ci_webots_pause_wwi/ci_webots_pause_wwi.html"
        not in browser_text
    ):
        raise ValueError("real isolated Robot Window launch missing")
    if "Segmentation fault" in stdout or "Traceback (most recent call last)" in stdout:
        raise ValueError("native crash in Webots console")
    path = Path(sidecar_path)
    raw = path.read_bytes()
    if not raw or len(raw) > 16384:
        raise ValueError("missing/unbounded native controller sidecar")
    if not raw.endswith(b"\n"):
        raise ValueError("incomplete controller sidecar final record")
    lines = raw.decode("utf-8").splitlines()
    if len(lines) != len(STAGES):
        raise ValueError("missing/extra/duplicate native controller stages")
    rows = [json.loads(line, object_pairs_hook=_reject_duplicate_keys) for line in lines]
    if any(type(row) is not dict or row.get("schema") != SCHEMA
           for row in rows):
        raise ValueError("controller sidecar schema mismatch")
    if tuple(row.get("stage") for row in rows) != STAGES:
        raise ValueError("unexpected controller stage order or ABORT")
    timestamps = [row.get("wall_monotonic_seconds") for row in rows]
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in timestamps):
        raise ValueError("invalid controller monotonic timestamps")
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError("non-monotonic controller stage order")

    before, after, advanced, native_pass = rows[2:6]
    frozen = before.get("frozen_simulated_ms")
    delta = advanced.get("delta_ms")
    if (not _exact_integer(frozen, 0)
        or before.get("mode") != 1
        or not _exact_integer(after.get("return_code"), 0, 0)
        or not _exact_integer(delta, 32, 64)
        or advanced.get("mode") != 1
        or native_pass.get("delta_ms") != delta):
        raise ValueError("native step(32) result/time/mode mismatch")

    console_lines = stdout.splitlines()
    prefix = "GP_PAUSE_WWI_"
    for name in REQUIRED_CONSOLE:
        if console_lines.count(prefix + name) != 1:
            raise ValueError("missing/duplicate WWI/PAUSE attestation: " + name)
    stale = _one_match(r"GP_PAUSE_WWI_STALE_RESUME_REJECTED count=(\d+)",
                       console_lines, "stale RESUME rejected")
    wrong_count = int(stale.group(1))
    clock = _one_match(
        r"GP_PAUSE_WWI_CLOCK_PRE_RESUME frozen_ms=(\d+) now_ms=(\d+) wall_seconds=(\d+(?:\.\d+)?)",
        console_lines, "clock frozen across actual PAUSE")
    frozen_console, now_console, wall_console = (
        int(clock.group(1)), int(clock.group(2)), float(clock.group(3)))
    if (wrong_count < 1 or frozen_console != frozen or now_console != frozen
        or not 1.0 <= wall_console < 8.5):
        raise ValueError("native clock/epoch proof missing or contradictory")

    proof = native_pass.get("proof")
    if type(proof) is not dict or set(proof) != PROOF_FIELDS:
        raise ValueError("native sidecar lacks complete canonical proof")
    if (proof.get("schema") != "webeeblocks-webots-pause-wwi-v1"
        or proof.get("simulation") != "isolated-r2025a-only"
        or not _exact_integer(proof.get("simulated_frozen_ms"), 0)
        or proof["simulated_frozen_ms"] != frozen
        or not _exact_integer(proof.get("frozen_delta_ms"), 0, 0)
        or not _exact_integer(proof.get("resumed_simulated_ms"), 32, 64)
        or proof["resumed_simulated_ms"] != delta
        or proof.get("resume_via_robot_window_wwi") is not True
        or not _exact_integer(proof.get("wrong_token_rejected"), 1)
        or proof["wrong_token_rejected"] != wrong_count
        or not _exact_integer(proof.get("steps_while_paused"), 0, 0)
        or type(proof.get("pause_wall_seconds")) not in (int, float)
        or not 1.0 <= proof["pause_wall_seconds"] < 8.5
        or abs(proof["pause_wall_seconds"] - wall_console) > 0.003):
        raise ValueError("native PAUSE/WWI proof values inconsistent")

    # Webots may stop forwarding controller stdout during simulationQuit(0).
    # When it does forward late messages, require exact consistency with disk.
    optional_exact = {
        "STEP_32_AFTER_RESUME_RETURNED": prefix + "STEP_32_AFTER_RESUME_RETURNED",
        "CLOCK_RESUMED_DELTA_MS": prefix + "CLOCK_RESUMED_DELTA_MS " + str(delta),
    }
    for name, expected in optional_exact.items():
        forwarded = [line for line in console_lines if line.startswith(prefix + name)]
        if forwarded and forwarded != [expected]:
            raise ValueError("contradictory/duplicate native stdout: " + name)
    forwarded_pass = [
        line[len(prefix + "PASS "):] for line in console_lines
        if line.startswith(prefix + "PASS ")
    ]
    if forwarded_pass:
        if len(forwarded_pass) != 1:
            raise ValueError("ambiguous native stdout PASS")
        if json.loads(forwarded_pass[0],
                      object_pairs_hook=_reject_duplicate_keys) != proof:
            raise ValueError("stdout PASS disagrees with native fsync sidecar")
    if any(line.startswith(prefix + "FAIL ") for line in console_lines):
        raise ValueError("native controller reported FAIL")
    return proof
