"""Align native Webots contact/velocity with exact instrumented RESET receipts.

Read-only #637 forensics: post-teleport observations are NOT RESET success,
causality, or permission to bypass the original oracle. Retain all raw traces.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HEADER = {"type": "header", "version": 1, "step_ms": 32,
          "scope": "read-only-native-state-not-runtime-ack"}
STEPS = (-1, 0, 1, 2, 3)


def _finite(number):
    return type(number) in (int, float) and math.isfinite(number)


def _vector(row, key, length):
    value = row.get(key)
    if not isinstance(value, list) or len(value) != length or not all(map(_finite, value)):
        raise ValueError(f"invalid native {key}")
    return value


def _validate_native(row):
    if row.get("type") != "sample" or not _finite(row.get("time")):
        raise ValueError("invalid native sample/time")
    pos = _vector(row, "position", 3)
    velocity = _vector(row, "velocity", 6)
    orientation = _vector(row, "orientation", 9)
    contacts = row.get("contacts")
    if not isinstance(contacts, list):
        raise ValueError("invalid native contacts")
    for contact in contacts:
        if not isinstance(contact, dict) or type(contact.get("node_id")) is not int:
            raise ValueError("invalid native contact identity")
        _vector(contact, "point", 3)
    if not isinstance(row.get("custom_data"), str):
        raise ValueError("invalid native customData")
    return {"time": row["time"], "position": pos, "orientation": orientation,
            "velocity": velocity, "angular_speed_rad_s": math.hypot(*velocity[3:]),
            "contact_count": len(contacts), "contacts": contacts,
            "custom_data": row["custom_data"]}


def analyze(native_path: Path, phase_summary: dict) -> dict:
    """Require exact native 32ms frames for each reported internal RESET.

    Native Supervisor sampling is independently scheduled, so a missing or
    ambiguous frame is UNPROVEN; never interpolate, infer an ACK, or fail open.
    """
    if not isinstance(phase_summary, dict) or not isinstance(phase_summary.get("resets"), list):
        raise ValueError("missing/incomplete internal RESET receipts")
    resets = phase_summary["resets"]
    if not resets:
        raise ValueError("missing RESET receipts")
    receipt_frames = {}
    ids = set()
    previous_begin = -1.
    for reset in resets:
        if not isinstance(reset, dict):
            raise ValueError("invalid RESET receipt")
        identifier, begin, terminal = reset.get("id"), reset.get("begin_time"), reset.get("terminal")
        if type(identifier) is not int or identifier < 1 or not _finite(begin) or begin <= previous_begin:
            raise ValueError("invalid/non-monotonic RESET receipt identity/time")
        if identifier in ids or not isinstance(terminal, str) or not terminal.startswith(
                f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE {identifier} "):
            raise ValueError("duplicate RESET or mismatched terminal")
        if terminal not in (f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE {identifier} OK",
                            f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE {identifier} ERR RESET_TIMEOUT"):
            raise ValueError("unrecognized RESET terminal")
        frame = round(begin / .032)
        if abs(frame * .032 - begin) > 2e-7:
            raise ValueError("RESET receipt off native time grid")
        receipt_frames[identifier] = {"id": identifier, "begin_time": begin,
                                      "terminal": terminal, "frame": frame, "steps": {}}
        ids.add(identifier)
        previous_begin = begin
    wanted = {}
    for case in receipt_frames.values():
        for offset in STEPS:
            frame = case["frame"] + offset
            if frame in wanted:
                raise ValueError("overlapping RESET observation frames")
            wanted[frame] = (case, offset)
    digest = hashlib.sha256()
    seen = set()
    count = 0
    previous_time = 0.0
    with Path(native_path).open("rb") as stream:
        for line_no, raw in enumerate(stream, 1):
            digest.update(raw)
            try:
                row = json.loads(raw)
            except (UnicodeDecodeError, ValueError) as exc:
                raise ValueError(f"invalid native JSONL line {line_no}: {exc}") from exc
            if line_no == 1:
                if row != HEADER:
                    raise ValueError("incorrect native observer header")
                continue
            if not isinstance(row, dict):
                raise ValueError("invalid native sample")
            now = row.get("time")
            if not _finite(now) or now <= previous_time:
                raise ValueError("non-finite/non-increasing native time")
            frame = round(now / .032)
            if abs(frame * .032 - now) > 2e-7:
                raise ValueError("native sample off 32ms grid")
            if frame in seen:
                raise ValueError("duplicate native frame")
            seen.add(frame)
            previous_time = now
            count += 1
            if frame in wanted:
                case, offset = wanted[frame]
                case["steps"][str(offset)] = _validate_native(row)
    if not count:
        raise ValueError("native observer empty")
    complete = []
    for case in receipt_frames.values():
        missing = [offset for offset in STEPS if str(offset) not in case["steps"]]
        if missing:
            raise ValueError(f"native samples absent for RESET {case['id']} at offsets {missing}")
        complete.append({k: v for k, v in case.items() if k != "frame"})
    return {"schema": "webeeblocks-reset-post-teleport-forensics-v1",
            "scope": "native velocity/contacts at fixed receipt-relative steps; no RESET ACK or causality",
            "native_sha256": digest.hexdigest(), "native_samples": count,
            "step_ms": 32, "offsets": list(STEPS), "resets": complete}
